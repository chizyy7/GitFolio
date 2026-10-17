"""
Background AI workers.

Each function opens its **own** database session (the request-scoped session is
already closed by the time these run) and is safe to hand to FastAPI's
``BackgroundTasks``.

Pipeline after a push::

    index changed files -> review the commit -> (maybe) refresh skills

Every stage is isolated: a missing Ollama daemon degrades the feature instead
of failing the push.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import session_scope
from app.models import Commit, Repository, User
from app.services.ai import ingestion, rag, reviewer, skills

logger = get_logger("workers")

SKILLS_REFRESH_INTERVAL = timedelta(hours=12)


# --------------------------------------------------------------------------- #
# Guards
# --------------------------------------------------------------------------- #
def _ai_disabled() -> bool:
    """True when the AI pipeline should be skipped entirely."""
    if not settings.AI_ENABLED:
        logger.info("AI pipeline disabled (AI_ENABLED=false); skipping task")
        return True
    return False


# --------------------------------------------------------------------------- #
# Tasks
# --------------------------------------------------------------------------- #
def index_repository_task(repo_id: str, force: bool = True) -> None:
    """Full (re)index of a repository into ChromaDB."""
    if _ai_disabled():
        return

    try:
        with session_scope() as db:
            repo = db.get(Repository, uuid.UUID(str(repo_id)))
            if repo is None:
                logger.warning("index_repository_task: repo %s no longer exists", repo_id)
                return
            status = ingestion.index_repository(db, repo, force=force)
            rag.invalidate_repo_cache(repo_id)
            logger.info(
                "Indexed repo %s: %d chunks from %d files",
                repo.name,
                status.indexed_chunks,
                status.indexed_files,
            )
    except Exception as exc:  # pragma: no cover - infra dependent
        logger.error("index_repository_task failed for %s: %s", repo_id, exc)


def index_paths_task(repo_id: str, paths: list[str]) -> None:
    """Incremental reindex of the files touched by a push."""
    if _ai_disabled() or not paths:
        return

    try:
        with session_scope() as db:
            repo = db.get(Repository, uuid.UUID(str(repo_id)))
            if repo is None:
                return
            written = ingestion.index_paths(db, repo, paths)
            rag.invalidate_repo_cache(repo_id)
            logger.info("Incrementally indexed %d chunks for repo %s", written, repo.name)
    except Exception as exc:  # pragma: no cover - infra dependent
        logger.error("index_paths_task failed for %s: %s", repo_id, exc)


def review_commit_task(commit_id: str, force: bool = False) -> None:
    """Run the AI code reviewer over one commit."""
    if _ai_disabled():
        return

    try:
        with session_scope() as db:
            commit = db.get(Commit, uuid.UUID(str(commit_id)))
            if commit is None:
                return
            rows = reviewer.review_commit(db, commit, force=force)
            logger.info("Reviewed commit %s: %d comments", commit.short_hash, len(rows))
    except Exception as exc:  # pragma: no cover - infra dependent
        logger.error("review_commit_task failed for %s: %s", commit_id, exc)


def refresh_skills_task(user_id: str, force: bool = False) -> None:
    """Regenerate the AI skill profile for a user."""
    if _ai_disabled():
        return

    try:
        with session_scope() as db:
            user = db.get(User, uuid.UUID(str(user_id)))
            if user is None:
                return

            if not force and user.skills_analyzed_at is not None:
                age = datetime.now(timezone.utc) - _ensure_aware(user.skills_analyzed_at)
                if age < SKILLS_REFRESH_INTERVAL:
                    logger.debug("Skipping skills refresh for @%s (fresh)", user.username)
                    return

            stored = skills.refresh_user_skills(db, user.id)
            logger.info("Refreshed %d skills for @%s", len(stored), user.username)
    except Exception as exc:  # pragma: no cover - infra dependent
        logger.error("refresh_skills_task failed for %s: %s", user_id, exc)


def post_push_pipeline(
    repo_id: str,
    commit_id: str,
    changed_paths: list[str],
    user_id: str,
) -> None:
    """
    The full post-push pipeline, wired to ``BackgroundTasks``.

    Order matters: vectors first (so chat works immediately), then the review,
    then skills.
    """
    if _ai_disabled():
        return

    logger.info(
        "Post-push pipeline starting: repo=%s commit=%s files=%d",
        repo_id,
        commit_id[:8],
        len(changed_paths),
    )

    index_paths_task(repo_id, changed_paths)
    review_commit_task(commit_id)
    refresh_skills_task(user_id)

    logger.info("Post-push pipeline finished for repo=%s", repo_id)


def _ensure_aware(value: datetime) -> datetime:
    """SQLite returns naive datetimes; normalise before comparing."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


__all__ = [
    "index_paths_task",
    "index_repository_task",
    "post_push_pipeline",
    "refresh_skills_task",
    "review_commit_task",
]
