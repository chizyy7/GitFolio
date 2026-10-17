"""
Repository routes — create, browse, list and delete.

    POST   /api/repos                                   create
    GET    /api/repos/{username}                        list a user's repos
    GET    /api/repos/{username}/{repo_name}            detail + file tree
    GET    /api/repos/{username}/{repo_name}/blob       one file's content
    PATCH  /api/repos/{repo_id}                         update metadata / pin
    DELETE /api/repos/{repo_id}                         delete (owner only)
"""

from __future__ import annotations

import uuid
from collections import Counter

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from sqlalchemy import func, or_, select

from app.api.deps import (
    CurrentUser,
    DbSession,
    OptionalUser,
    PageParams,
    RepoNamePath,
    UsernamePath,
    get_owned_repo_or_404,
    get_repo_or_404,
    get_user_or_404,
)
from app.api.serializers import serialize_commit, serialize_file, serialize_repo
from app.core.config import settings
from app.core.logging import get_logger
from app.models import Commit, File, Repository
from app.schemas import (
    FileContent,
    RepoCreate,
    RepoDetail,
    RepoRead,
    RepoUpdate,
)
from app.services.language import detect_language
from app.services.tree import build_file_tree
from app.services.vcs import engine_for
from app.workers.tasks import index_repository_task

logger = get_logger("api.repos")

router = APIRouter(prefix="/repos", tags=["Repositories"])


# --------------------------------------------------------------------------- #
# Create
# --------------------------------------------------------------------------- #
@router.post(
    "",
    response_model=RepoRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a repository",
)
def create_repository(
    payload: RepoCreate,
    current_user: CurrentUser,
    db: DbSession,
    background_tasks: BackgroundTasks,
) -> RepoRead:
    """Create an empty repository and initialise its Git object database."""
    clash = db.execute(
        select(Repository.id).where(
            Repository.user_id == current_user.id,
            func.lower(Repository.name) == payload.name.lower(),
        )
    ).scalar_one_or_none()
    if clash is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"You already have a repository named '{payload.name}'.",
        )

    repo = Repository(
        user_id=current_user.id,
        name=payload.name,
        description=payload.description,
        visibility=payload.visibility,
        primary_language=payload.primary_language,
        topics=",".join(payload.topics) if payload.topics else None,
        default_branch="main",
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)

    # Materialise the on-disk Git object database immediately so a push is fast.
    try:
        engine_for(repo_id=str(repo.id), user_id=str(current_user.id))
    except Exception as exc:  # pragma: no cover - filesystem dependent
        logger.error("Could not initialise Git storage for %s: %s", repo.id, exc)

    # Honour `auto_index`: queue the first vector-index build so the repo is
    # ready for semantic search / chat without an extra manual step.
    if payload.auto_index and settings.ENABLE_BACKGROUND_AI and settings.AI_ENABLED:
        background_tasks.add_task(index_repository_task, str(repo.id), False)

    logger.info("Repository created: %s by @%s", repo.name, current_user.username)
    return serialize_repo(repo)


# --------------------------------------------------------------------------- #
# List
# --------------------------------------------------------------------------- #
@router.get(
    "/{username}",
    response_model=list[RepoRead],
    summary="List a user's repositories",
)
def list_repositories(
    username: UsernamePath,
    db: DbSession,
    viewer: OptionalUser,
    page: PageParams,
    q: str | None = Query(default=None, max_length=100, description="Search name/description"),
    language: str | None = Query(default=None, max_length=50),
    pinned_only: bool = Query(default=False),
    sort: str = Query(default="updated", pattern="^(updated|created|name|stars|commits)$"),
) -> list[RepoRead]:
    """
    List repositories owned by ``username``.

    Private repositories are only visible to their owner. Supports free-text
    search, language filtering, pinning and sorting.
    """
    owner = get_user_or_404(db, username)

    statement = select(Repository).where(Repository.user_id == owner.id)

    # Hide private repos from strangers.
    if viewer is None or (viewer.id != owner.id and not viewer.is_superuser):
        from app.models import Visibility

        statement = statement.where(Repository.visibility == Visibility.PUBLIC)

    if q:
        needle = f"%{q.lower()}%"
        statement = statement.where(
            or_(
                func.lower(Repository.name).like(needle),
                func.lower(func.coalesce(Repository.description, "")).like(needle),
                func.lower(func.coalesce(Repository.primary_language, "")).like(needle),
            )
        )
    if language:
        statement = statement.where(func.lower(Repository.primary_language) == language.lower())
    if pinned_only:
        statement = statement.where(Repository.is_pinned.is_(True))

    order_map = {
        "updated": Repository.updated_at.desc(),
        "created": Repository.created_at.desc(),
        "name": Repository.name.asc(),
        "stars": Repository.star_count.desc(),
        "commits": Repository.commit_count.desc(),
    }
    statement = statement.order_by(order_map[sort])

    statement = statement.offset(page.offset).limit(page.limit)

    repos = list(db.execute(statement).scalars())
    return [serialize_repo(repo) for repo in repos]


# --------------------------------------------------------------------------- #
# Detail
# --------------------------------------------------------------------------- #
@router.get(
    "/{username}/{repo_name}",
    response_model=RepoDetail,
    summary="Repository detail including the full file tree",
)
def get_repository(
    username: UsernamePath,
    repo_name: RepoNamePath,
    db: DbSession,
    viewer: OptionalUser,
) -> RepoDetail:
    """Repository metadata + nested file tree + latest commit."""
    repo = get_repo_or_404(db, username, repo_name, viewer)

    files = list(
        db.execute(select(File).where(File.repo_id == repo.id)).scalars()
    )
    tree = build_file_tree(
        {
            "file_path": f.file_path,
            "size_bytes": f.size_bytes,
            "language": f.language,
        }
        for f in files
    )

    latest = db.execute(
        select(Commit)
        .where(Commit.repo_id == repo.id)
        .order_by(Commit.timestamp.desc())
        .limit(1)
    ).scalar_one_or_none()

    base = serialize_repo(repo)
    return RepoDetail(
        **base.model_dump(),
        owner_avatar_url=repo.owner.avatar_url if repo.owner else None,
        tree=tree,
        latest_commit=serialize_commit(latest) if latest else None,
    )


@router.get(
    "/{username}/{repo_name}/blob",
    response_model=FileContent,
    summary="Read a single file from the working tree",
)
def get_file_content(
    username: UsernamePath,
    repo_name: RepoNamePath,
    db: DbSession,
    viewer: OptionalUser,
    path: str = Query(min_length=1, max_length=1024, description="Repository-relative file path"),
    ref: str | None = Query(default=None, max_length=100, description="Optional commit hash to read from"),
) -> FileContent:
    """
    Return one file's content.

    With ``ref`` supplied, the content is read from the Git object database at
    that commit instead of the current working tree.
    """
    repo = get_repo_or_404(db, username, repo_name, viewer)

    if ref:
        engine = engine_for(repo_id=str(repo.id), user_id=str(repo.user_id), branch=repo.default_branch)
        content = engine.read_blob(path, ref=ref)
        if content is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"'{path}' does not exist at {ref[:12]}.",
            )
        return FileContent(
            id=uuid.uuid5(uuid.NAMESPACE_URL, f"{repo.id}:{path}:{ref}"),
            file_path=path,
            content=content,
            size_bytes=len(content.encode("utf-8")),
            line_count=content.count("\n") + 1,
            language=detect_language(path),
            is_binary=False,
            blob_hash=None,
            updated_at=repo.updated_at,
        )

    file_row = db.execute(
        select(File).where(File.repo_id == repo.id, File.file_path == path)
    ).scalar_one_or_none()
    if file_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"'{path}' does not exist in this repository.",
        )

    return FileContent(**serialize_file(file_row, with_content=True))  # type: ignore[arg-type]


@router.get(
    "/{username}/{repo_name}/languages",
    summary="Language breakdown of a repository",
)
def get_repo_languages(
    username: UsernamePath,
    repo_name: RepoNamePath,
    db: DbSession,
    viewer: OptionalUser,
) -> dict[str, object]:
    """Byte-weighted language percentages used by the repo header bar."""
    repo = get_repo_or_404(db, username, repo_name, viewer)

    rows = db.execute(
        select(File.language, func.sum(File.size_bytes))
        .where(File.repo_id == repo.id, File.language.is_not(None))
        .group_by(File.language)
    ).all()

    total = sum(int(size or 0) for _lang, size in rows) or 1
    languages = Counter({str(lang): int(size or 0) for lang, size in rows})
    return {
        "total_bytes": total,
        "languages": [
            {"language": lang, "bytes": size, "percentage": round(size * 100 / total, 2)}
            for lang, size in languages.most_common()
        ],
    }


# --------------------------------------------------------------------------- #
# Update / delete
# --------------------------------------------------------------------------- #
@router.patch(
    "/{repo_id}",
    response_model=RepoRead,
    summary="Update repository metadata (owner only)",
)
def update_repository(
    repo_id: uuid.UUID,
    payload: RepoUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> RepoRead:
    """Patch description, visibility, topics or the pinned flag."""
    repo = get_owned_repo_or_404(db, repo_id, current_user)
    data = payload.model_dump(exclude_unset=True)

    if "topics" in data and data["topics"] is not None:
        topics = [str(t).strip() for t in data.pop("topics") if str(t).strip()]
        repo.topics = ",".join(topics[:20]) or None

    for field, value in data.items():
        if value is not None or field in ("description", "primary_language"):
            setattr(repo, field, value)

    db.add(repo)
    db.commit()
    db.refresh(repo)
    return serialize_repo(repo)


@router.delete(
    "/{repo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a repository and all of its data",
)
def delete_repository(
    repo_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    background_tasks: BackgroundTasks,
) -> None:
    """
    Delete a repository: Postgres rows (cascading), the Git object database and
    the vector collection.
    """
    from app.services.ai.ingestion import remove_repository_index

    repo = get_owned_repo_or_404(db, repo_id, current_user)
    name = repo.name

    # Remove vectors synchronously-ish (fast, and must not leak on failure).
    try:
        remove_repository_index(repo.id)
    except Exception as exc:  # pragma: no cover
        logger.warning("Vector cleanup failed for %s: %s", repo_id, exc)

    db.delete(repo)
    db.commit()

    try:
        engine_for(repo_id=str(repo_id), user_id=str(current_user.id)).delete()
    except Exception as exc:  # pragma: no cover
        logger.warning("Git storage cleanup failed for %s: %s", repo_id, exc)

    logger.info("Repository deleted: %s (@%s)", name, current_user.username)


@router.post(
    "/{repo_id}/index",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue a full re-index of the repository for AI search",
)
def trigger_index(
    repo_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """Kick off embedding generation in the background."""
    repo = get_owned_repo_or_404(db, repo_id, current_user)
    background_tasks.add_task(index_repository_task, str(repo.id), True)
    return {"status": "queued", "repo_id": str(repo.id), "message": "Indexing started."}


__all__ = ["router"]
