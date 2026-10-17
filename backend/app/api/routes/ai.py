"""
AI routes — RAG chat, semantic search, code review and the skill mapper.

    POST /api/ai/chat                    ask a question about a repository
    POST /api/ai/search                  semantic code search
    GET  /api/ai/reviews/{commit_id}     AI review for a commit
    POST /api/ai/reviews/{commit_id}     re-run the review
    POST /api/ai/index/{repo_id}         (re)build the vector index
    POST /api/ai/skills/refresh          regenerate the user's skill badges
    GET  /api/ai/health                  Ollama + ChromaDB availability
"""

from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession, OptionalUser, can_view
from app.core.config import settings
from app.core.logging import get_logger
from app.models import Commit, Repository
from app.schemas import (
    ChatRequest,
    ChatResponse,
    IndexStatus,
    ReviewResponse,
    SearchHit,
    SearchRequest,
    SearchResponse,
    SkillProfileResponse,
)
from app.services.ai import rag, reviewer
from app.services.ai.ingestion import index_paths, index_repository, remove_repository_index
from app.services.ai.skills import generate_skill_profile, persist_skill_profile, refresh_user_skills
from app.services.llm import OllamaUnavailable, get_ollama
from app.services.vectorstore import VectorStoreUnavailable, get_vector_store
from app.workers.tasks import index_repository_task, review_commit_task

logger = get_logger("api.ai")

router = APIRouter(prefix="/ai", tags=["AI"])


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _viewable_repo(db: DbSession, repo_id: uuid.UUID, viewer) -> Repository:
    """Fetch a repository the viewer is allowed to read."""
    repo = db.get(Repository, repo_id)
    if repo is None or not can_view(repo, viewer):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found.",
        )
    return repo


def _accessible_commit(db: DbSession, commit_id: uuid.UUID, viewer) -> Commit:
    """Fetch a commit the viewer may read (via its repository)."""
    commit = db.get(Commit, commit_id)
    if commit is None or commit.repository is None or not can_view(commit.repository, viewer):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commit not found.")
    return commit


def _ai_unavailable(exc: Exception) -> HTTPException:
    """Translate AI-stack failures into actionable 503s."""
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"AI subsystem unavailable: {exc}. Check OLLAMA_HOST / CHROMA_HOST.",
    )


# --------------------------------------------------------------------------- #
# Chat (RAG)
# --------------------------------------------------------------------------- #
@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Ask Llama 3.2 a question about a repository",
)
def chat(
    payload: ChatRequest,
    db: DbSession,
    viewer: OptionalUser,
) -> ChatResponse:
    """
    Retrieval-augmented explanation of the user's own codebase.

    The question is embedded, the top-K matching code chunks are pulled from
    ChromaDB, and Llama 3.2 is instructed to answer **only** from that context
    while citing files, line numbers and symbols.
    """
    if not settings.AI_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI features are disabled (AI_ENABLED=false).",
        )

    repo = _viewable_repo(db, payload.repo_id, viewer)

    try:
        return rag.answer_question(
            db,
            repo,
            payload.question,
            top_k=payload.top_k,
            history=payload.history,
            file_filter=payload.file_filter,
        )
    except VectorStoreUnavailable as exc:
        # Nothing indexed yet is a very common, very recoverable situation.
        if get_vector_store().count(str(repo.id)) == 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This repository has not been indexed yet. "
                    "Push files or call POST /api/ai/index/{repo_id} first."
                ),
            ) from exc
        raise _ai_unavailable(exc) from exc
    except OllamaUnavailable as exc:
        raise _ai_unavailable(exc) from exc


# --------------------------------------------------------------------------- #
# Semantic search
# --------------------------------------------------------------------------- #
@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Semantic (embedding) search across a repository",
)
def semantic_search(
    payload: SearchRequest,
    db: DbSession,
    viewer: OptionalUser,
) -> SearchResponse:
    """
    Find code by *meaning* rather than by substring.

    Returns ranked file/line references plus an optional Llama 3.2 summary of
    what the best match does.
    """
    started = time.perf_counter()
    repo = _viewable_repo(db, payload.repo_id, viewer)

    try:
        hits = rag.retrieve(repo.id, payload.query, top_k=payload.top_k)
    except VectorStoreUnavailable as exc:
        raise _ai_unavailable(exc) from exc

    results: list[SearchHit] = []
    for hit in hits:
        meta = hit.get("metadata") or {}
        document = hit.get("document") or ""
        results.append(
            SearchHit(
                file_path=str(meta.get("file_path", "unknown")),
                start_line=int(meta.get("start_line", 0) or 0),
                end_line=int(meta.get("end_line", 0) or 0),
                language=str(meta.get("language") or "") or None,
                symbol=str(meta.get("symbol") or "") or None,
                score=round(float(hit.get("score", 0.0)), 4),
                snippet=document[:600],
            )
        )

    summary = None
    if payload.summarise and results:
        summary = rag.summarise_hits(repo, payload.query, hits)
        if summary:
            results[0].summary = summary

    return SearchResponse(
        query=payload.query,
        results=results,
        elapsed_ms=int((time.perf_counter() - started) * 1000),
    )


# --------------------------------------------------------------------------- #
# Code review
# --------------------------------------------------------------------------- #
@router.get(
    "/reviews/{commit_id}",
    response_model=ReviewResponse,
    summary="Fetch the AI review for a commit",
)
def get_reviews(commit_id: uuid.UUID, db: DbSession, viewer: OptionalUser) -> ReviewResponse:
    """
    AI review comments for one commit.

    ``status`` is ``pending`` while the background reviewer is still running,
    ``failed`` when Ollama was unreachable (the error is included), and
    ``complete`` once comments (possibly zero) are stored.
    """
    commit = _accessible_commit(db, commit_id, viewer)

    if not settings.AI_ENABLED:
        state = "disabled"
    elif commit.ai_review_error:
        state = "failed"
    elif commit.ai_reviewed:
        state = "complete"
    else:
        state = "pending"

    return ReviewResponse(
        commit_id=commit.id,
        commit_hash=commit.commit_hash,
        status=state,
        reviews=[
            {
                "id": r.id,
                "review_text": r.review_text,
                "line_number": r.line_number,
                "file_path": r.file_path,
                "severity": r.severity.value if hasattr(r.severity, "value") else str(r.severity),
                "title": r.title,
            }
            for r in commit.reviews
        ],
        error=commit.ai_review_error,
    )


@router.post(
    "/reviews/{commit_id}",
    response_model=ReviewResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Re-run the AI code review for a commit",
)
def rerun_review(
    commit_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    background_tasks: BackgroundTasks,
    sync: bool = Query(default=False, description="Run inline instead of in the background"),
) -> ReviewResponse:
    """Force a fresh review of a commit's diff."""
    commit = _accessible_commit(db, commit_id, current_user)
    if commit.repository is None or commit.repository.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the repository owner can re-run reviews.",
        )

    if sync:
        try:
            rows = reviewer.review_commit(db, commit, force=True)
        except OllamaUnavailable as exc:
            raise _ai_unavailable(exc) from exc
        return ReviewResponse(
            commit_id=commit.id,
            commit_hash=commit.commit_hash,
            status="complete" if rows is not None else "failed",
            reviews=[
                {
                    "id": r.id,
                    "review_text": r.review_text,
                    "line_number": r.line_number,
                    "file_path": r.file_path,
                    "severity": r.severity.value if hasattr(r.severity, "value") else str(r.severity),
                    "title": r.title,
                }
                for r in commit.reviews
            ],
            error=commit.ai_review_error,
        )

    background_tasks.add_task(review_commit_task, str(commit.id), True)
    return ReviewResponse(
        commit_id=commit.id,
        commit_hash=commit.commit_hash,
        status="pending",
        reviews=[],
        error=None,
    )


# --------------------------------------------------------------------------- #
# Indexing
# --------------------------------------------------------------------------- #
@router.post(
    "/index/{repo_id}",
    response_model=IndexStatus,
    summary="Build or rebuild the repository's vector index",
)
def build_index(
    repo_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    background_tasks: BackgroundTasks,
    sync: bool = Query(default=False, description="Run inline (blocks until finished)"),
    force: bool = Query(default=True, description="Drop existing vectors first"),
    paths: list[str] | None = Query(default=None, description="Index only these paths"),
) -> IndexStatus:
    """
    Embed the repository's code into ChromaDB.

    By default this is queued as a background task (HTTP 202); pass
    ``?sync=true`` to block and receive the resulting :class:`IndexStatus`.
    """
    repo = _viewable_repo(db, repo_id, current_user)
    if repo.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the repository owner can re-index it.",
        )

    if not sync:
        background_tasks.add_task(index_repository_task, str(repo.id), force)
        return IndexStatus(
            repo_id=repo.id,
            indexed_files=0,
            indexed_chunks=0,
            collection=f"repo_{str(repo.id).replace('-', '')}",
            elapsed_ms=0,
        )

    started = time.perf_counter()
    try:
        if paths:
            written = index_paths(db, repo, list(paths))
            return IndexStatus(
                repo_id=repo.id,
                indexed_files=len(paths),
                indexed_chunks=written,
                collection=f"repo_{str(repo.id).replace('-', '')}",
                elapsed_ms=int((time.perf_counter() - started) * 1000),
            )
        return index_repository(db, repo, force=force)
    except (VectorStoreUnavailable, OllamaUnavailable) as exc:
        raise _ai_unavailable(exc) from exc


@router.delete(
    "/index/{repo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete the repository's vector index",
)
def drop_index(repo_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> None:
    """Remove all embeddings for a repository."""
    repo = _viewable_repo(db, repo_id, current_user)
    if repo.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your repository.")
    remove_repository_index(repo.id)
    repo.indexed_at = None
    db.add(repo)
    db.commit()


# --------------------------------------------------------------------------- #
# Skill mapper
# --------------------------------------------------------------------------- #
@router.post(
    "/skills/refresh",
    response_model=SkillProfileResponse,
    summary="Regenerate the AI skill profile for the current user",
)
def refresh_skills(
    current_user: CurrentUser,
    db: DbSession,
    background_tasks: BackgroundTasks,
    sync: bool = Query(default=True, description="Return the generated profile inline"),
) -> SkillProfileResponse:
    """
    Analyse all of the user's repositories (extensions + manifests) and turn
    the result into profile badges.
    """
    from datetime import datetime, timezone

    if not settings.AI_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI features are disabled (AI_ENABLED=false).",
        )

    if not sync:
        background_tasks.add_task(refresh_user_skills, current_user.id)
        # Immediately return the heuristic baseline; the LLM result lands shortly.
        from app.services.ai.skills import collect_evidence, heuristic_profile

        profile = heuristic_profile(collect_evidence(db, current_user))
    else:
        profile = generate_skill_profile(db, current_user)
        persist_skill_profile(db, current_user, profile)

    return SkillProfileResponse(
        **profile.model_dump(),
        username=current_user.username,
        generated_at=datetime.now(timezone.utc),
    )


@router.get(
    "/skills",
    response_model=list[str],
    summary="List the current user's skill names",
)
def list_skills(current_user: CurrentUser) -> list[str]:
    """Flat list of skill badge names (handy for the profile editor)."""
    return [skill.skill_name for skill in current_user.skills]


# --------------------------------------------------------------------------- #
# Health
# --------------------------------------------------------------------------- #
@router.get("/health", summary="AI subsystem health check")
def ai_health() -> dict[str, object]:
    """
    Report whether Ollama and ChromaDB are reachable.

    Always returns 200 — the frontend uses the flags to decide whether to show
    the AI panels or a "start Ollama" hint.
    """
    ollama = get_ollama()
    ollama_ok = ollama.is_available()
    store = get_vector_store()

    return {
        "ai_enabled": settings.AI_ENABLED,
        "ollama": {
            "available": ollama_ok,
            "host": ollama.host,
            "chat_model": ollama.chat_model,
            "embed_model": ollama.embed_model,
            "models": ollama.list_models() if ollama_ok else [],
        },
        "chroma": {
            "enabled": store.enabled,
            "available": store.heartbeat(),
            "host": settings.CHROMA_HOST,
            "port": settings.CHROMA_PORT,
        },
        "hint": (
            None
            if ollama_ok
            else "Run `ollama serve` and `ollama pull llama3.2 && ollama pull nomic-embed-text`."
        ),
    }


__all__ = ["router"]
