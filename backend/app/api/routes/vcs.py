"""
Version-control routes — the "push" flow and commit browsing.

    POST /api/repos/{repo_id}/push                    push files (creates a commit)
    GET  /api/repos/{repo_id}/commits                 paginated commit history
    GET  /api/repos/{repo_id}/commits/{commit_hash}   one commit + diff + AI review
    GET  /api/repos/{repo_id}/status                  repo/git/index status
    POST /api/repos/{repo_id}/reindex                 rebuild the vector index
"""

from __future__ import annotations

import fnmatch
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession, OptionalUser, PageParams, can_view, get_writable_repo
from app.api.serializers import serialize_commit, serialize_commit_detail
from app.core.config import settings
from app.core.logging import get_logger
from app.models import Commit, File, Repository
from app.schemas import (
    ChangeType,
    CommitDetail,
    CommitListResponse,
    PushFileResult,
    PushRequest,
    PushResponse,
)
from app.services.ai.commit_message import generate_commit_message
from app.services.language import detect_language, is_binary_bytes, is_binary_path
from app.services.vcs import Author, engine_for
from app.workers.tasks import index_repository_task, post_push_pipeline

logger = get_logger("api.vcs")

router = APIRouter(prefix="/repos", tags=["Version Control"])


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _normalize_path(path: str) -> str:
    """Same normalisation the ``PushFile`` validator applies."""
    cleaned = path.replace("\\", "/").lstrip("/")
    return "/".join(part for part in cleaned.split("/") if part not in ("", "."))


def _looks_binary(path: str, content: str) -> bool:
    """Decide whether a pushed file should be treated as binary."""
    if is_binary_path(path):
        return True
    return is_binary_bytes(content.encode("utf-8", "replace")[:4096])


def _is_ignored(path: str) -> bool:
    """
    True when ``path`` matches one of the configured ``IGNORED_PATHS`` patterns.

    Patterns are either a directory (``node_modules/``), a glob (``*.min.js``)
    or a bare name. Directory patterns match any path segment; globs are tested
    against both the full path and the basename.
    """
    parts = path.split("/")
    for pattern in settings.ignored_patterns:
        if pattern.endswith("/"):
            directory = pattern[:-1]
            if directory in parts:
                return True
        elif fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(parts[-1], pattern):
            return True
    return False


def _upsert_file_row(
    db: DbSession,
    repo: Repository,
    path: str,
    content: str,
    commit_id: uuid.UUID,
    blob_hash: str,
) -> File:
    """Insert or update the ``files`` row for one path."""
    row = db.execute(
        select(File).where(File.repo_id == repo.id, File.file_path == path)
    ).scalar_one_or_none()

    binary = _looks_binary(path, content)
    payload = "" if binary else content
    language = detect_language(path)

    if row is None:
        row = File(
            repo_id=repo.id,
            file_path=path,
            content=payload,
            blob_hash=blob_hash,
            size_bytes=len(content.encode("utf-8", "replace")),
            line_count=0 if binary else content.count("\n") + 1,
            language=language,
            is_binary=1 if binary else 0,
            last_modified_commit_id=commit_id,
        )
        db.add(row)
    else:
        row.content = payload
        row.blob_hash = blob_hash
        row.size_bytes = len(content.encode("utf-8", "replace"))
        row.line_count = 0 if binary else content.count("\n") + 1
        row.language = language
        row.is_binary = 1 if binary else 0
        row.last_modified_commit_id = commit_id

    return row


def _recompute_primary_language(db: DbSession, repo: Repository) -> None:
    """Set ``primary_language`` to the language with the most bytes."""
    rows = db.execute(
        select(File.language, func.sum(File.size_bytes))
        .where(File.repo_id == repo.id, File.language.is_not(None))
        .group_by(File.language)
        .order_by(func.sum(File.size_bytes).desc())
        .limit(1)
    ).first()
    if rows and rows[0]:
        repo.primary_language = str(rows[0])


# --------------------------------------------------------------------------- #
# Push
# --------------------------------------------------------------------------- #
@router.post(
    "/{repo_id}/push",
    response_model=PushResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Push files and create a commit",
)
def push(
    repo_id: uuid.UUID,
    payload: PushRequest,
    current_user: CurrentUser,
    db: DbSession,
    background_tasks: BackgroundTasks,
) -> PushResponse:
    """
    The GitFolio "push".

    Pipeline:

    1. Load the current file state from PostgreSQL.
    2. Apply the incoming files/deletions to build the new state.
    3. Diff old vs new (``pygit2`` object store + unified diff).
    4. Generate a commit message if none was supplied (Llama 3.2, with a
       deterministic fallback).
    5. Write the Git commit (real SHA-1), persist ``files``/``commits`` rows
       and update the denormalised counters.
    6. Queue the AI pipeline: incremental embedding, code review, skill refresh.
    """
    repo = get_writable_repo(db, repo_id, current_user)

    deleted = {_normalize_path(p) for p in payload.deleted_paths}
    incoming = {_normalize_path(f.path): f.content for f in payload.files}

    # Drop anything matching IGNORED_PATHS (build output, vendored deps, binaries…)
    # so the server enforces the same rules the CLI applies locally.
    ignored = {path for path in incoming if _is_ignored(path)}
    if ignored:
        logger.info(
            "Push for repo %s skipped %d ignored path(s): %s",
            repo.id,
            len(ignored),
            ", ".join(sorted(ignored)[:10]),
        )
        incoming = {path: content for path, content in incoming.items() if path not in ignored}

    if not incoming and not deleted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Push rejected: provide at least one file or deletion.",
        )

    # --- 1. current state ------------------------------------------------- #
    existing_rows = list(db.execute(select(File).where(File.repo_id == repo.id)).scalars())
    old_state = {row.file_path: row.content for row in existing_rows}

    # --- 2. desired state ------------------------------------------------- #
    new_state = dict(old_state)
    new_state.update(incoming)
    for path in deleted:
        new_state.pop(path, None)

    # --- 3. engine + diff ------------------------------------------------- #
    branch = payload.branch or repo.default_branch or "main"
    engine = engine_for(repo_id=str(repo.id), user_id=str(repo.user_id), branch=branch)

    diffs = engine.diff_against(new_state, old_state, deleted)
    if not diffs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nothing to commit — the pushed files are identical to the current HEAD.",
        )

    unified = "".join(entry.diff_text for entry in diffs)
    total_additions = sum(entry.additions for entry in diffs)
    total_deletions = sum(entry.deletions for entry in diffs)

    # --- 4. commit message ------------------------------------------------ #
    message = (payload.commit_message or "").strip()
    message_generated = False
    if not message:
        message = generate_commit_message(
            unified,
            files_changed=len(diffs),
            additions=total_additions,
            deletions=total_deletions,
        )
        message_generated = True

    # --- 5. write the commit --------------------------------------------- #
    try:
        result = engine.commit(
            files=incoming,
            deleted=sorted(deleted),
            message=message,
            author=Author(name=current_user.username, email=current_user.email),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - filesystem corruption
        logger.exception("Git commit failed for repo %s", repo.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Version-control engine error: {exc}",
        ) from exc

    commit_row = Commit(
        repo_id=repo.id,
        author_id=current_user.id,
        commit_hash=result.commit_hash,
        parent_hash=result.parent_hash,
        message=result.message,
        diff=unified,
        files_changed=len(diffs),
        additions=total_additions,
        deletions=total_deletions,
        message_generated=message_generated,
        ai_reviewed=False,
    )
    db.add(commit_row)
    db.flush()  # assign commit_row.id for the file rows below

    # --- persist file rows ----------------------------------------------- #
    file_results: list[PushFileResult] = []
    for entry in diffs:
        if entry.change_type == ChangeType.DELETED:
            row = db.execute(
                select(File).where(File.repo_id == repo.id, File.file_path == entry.path)
            ).scalar_one_or_none()
            if row is not None:
                db.delete(row)
        else:
            _upsert_file_row(
                db,
                repo,
                entry.path,
                entry.new_content,
                commit_row.id,
                entry.blob_hash,
            )

        file_results.append(
            PushFileResult(
                path=entry.path,
                change_type=entry.change_type,
                additions=entry.additions,
                deletions=entry.deletions,
                blob_hash=entry.blob_hash,
            )
        )

    # --- counters --------------------------------------------------------- #
    db.flush()
    repo.commit_count = int(repo.commit_count or 0) + 1
    repo.file_count = int(
        db.execute(select(func.count(File.id)).where(File.repo_id == repo.id)).scalar_one()
    )
    _recompute_primary_language(db, repo)
    db.add(repo)
    db.commit()
    db.refresh(commit_row)

    # --- 6. AI pipeline --------------------------------------------------- #
    ai_queued = False
    if payload.run_ai and settings.ENABLE_BACKGROUND_AI and settings.AI_ENABLED:
        background_tasks.add_task(
            post_push_pipeline,
            str(repo.id),
            str(commit_row.id),
            [entry.path for entry in diffs],
            str(current_user.id),
        )
        ai_queued = True

    logger.info(
        "Push accepted: %s/%s %s (+%d/-%d) by @%s",
        repo.owner.username if repo.owner else "?",
        repo.name,
        result.short_hash,
        total_additions,
        total_deletions,
        current_user.username,
    )

    return PushResponse(
        commit_hash=result.commit_hash,
        short_hash=result.short_hash,
        message=result.message,
        message_generated=message_generated,
        files_changed=len(diffs),
        additions=total_additions,
        deletions=total_deletions,
        files=file_results,
        ai_queued=ai_queued,
    )


# --------------------------------------------------------------------------- #
# History
# --------------------------------------------------------------------------- #
@router.get(
    "/{repo_id}/commits",
    response_model=CommitListResponse,
    summary="Paginated commit history",
)
def list_commits(
    repo_id: uuid.UUID,
    db: DbSession,
    viewer: OptionalUser,
    page: PageParams,
    branch: str | None = Query(default=None, max_length=100),
    author: str | None = Query(default=None, max_length=39, description="Filter by username"),
) -> CommitListResponse:
    """Commit history, newest first, with per-commit diff statistics."""
    repo = db.get(Repository, repo_id)
    if repo is None or not can_view(repo, viewer):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found.")

    statement = select(Commit).where(Commit.repo_id == repo.id)
    count_statement = select(func.count(Commit.id)).where(Commit.repo_id == repo.id)

    if author:
        from app.models import User

        statement = statement.join(User, Commit.author_id == User.id).where(
            func.lower(User.username) == author.lower()
        )

    total = int(db.execute(count_statement).scalar_one())

    commits = list(
        db.execute(
            statement.order_by(Commit.timestamp.desc()).offset(page.offset).limit(page.limit)
        ).scalars()
    )

    return CommitListResponse(
        items=[serialize_commit(c) for c in commits],
        total=total,
        page=page.page,
        per_page=page.per_page,
    )


@router.get(
    "/{repo_id}/commits/{commit_hash}",
    response_model=CommitDetail,
    summary="Commit detail with diff and AI review",
)
def get_commit(
    repo_id: uuid.UUID,
    commit_hash: str,
    db: DbSession,
    viewer: OptionalUser,
) -> CommitDetail:
    """Everything the commit page renders: message, diff and AI comments."""
    repo = db.get(Repository, repo_id)
    if repo is None or not can_view(repo, viewer):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found.")

    commit = db.execute(
        select(Commit).where(
            Commit.repo_id == repo.id,
            Commit.commit_hash.like(f"{commit_hash}%"),
        )
    ).scalars().first()

    if commit is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Commit '{commit_hash}' not found in this repository.",
        )

    return serialize_commit_detail(commit)


# --------------------------------------------------------------------------- #
# Status
# --------------------------------------------------------------------------- #
@router.get(
    "/{repo_id}/status",
    summary="Repository synchronisation status",
)
def repo_status(
    repo_id: uuid.UUID,
    db: DbSession,
    viewer: OptionalUser,
) -> dict[str, object]:
    """Git HEAD, DB counters and vector-index state for one repository."""
    repo = db.get(Repository, repo_id)
    if repo is None or not can_view(repo, viewer):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found.")

    head = None
    try:
        engine = engine_for(repo_id=str(repo.id), user_id=str(repo.user_id), branch=repo.default_branch)
        head_oid = engine.head_oid()
        head = str(head_oid) if head_oid else None
    except Exception as exc:  # pragma: no cover
        logger.warning("Could not read Git HEAD for %s: %s", repo.id, exc)

    chunk_count = 0
    try:
        from app.services.vectorstore import get_vector_store

        chunk_count = get_vector_store().count(str(repo.id))
    except Exception:  # pragma: no cover - AI stack optional
        chunk_count = 0

    return {
        "repo_id": str(repo.id),
        "full_name": repo.full_name,
        "branch": repo.default_branch,
        "head_commit": head,
        "commit_count": repo.commit_count,
        "file_count": repo.file_count,
        "primary_language": repo.primary_language,
        "indexed_at": repo.indexed_at.isoformat() if repo.indexed_at else None,
        "indexed_chunks": chunk_count,
    }


@router.post(
    "/{repo_id}/reindex",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue a full re-index of the repository",
)
def reindex(
    repo_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    background_tasks: BackgroundTasks,
    force: bool = Query(default=True, description="Drop existing vectors first"),
) -> dict[str, str]:
    """Rebuild the ChromaDB collection for this repository."""
    repo = get_writable_repo(db, repo_id, current_user)
    background_tasks.add_task(index_repository_task, str(repo.id), force)
    return {"status": "queued", "repo_id": str(repo.id)}


__all__ = ["router"]
