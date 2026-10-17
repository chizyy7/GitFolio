"""
Shared FastAPI dependencies: authentication, authorisation and lookups.

Every route gets its session from :func:`app.db.session.get_db` and its user
from :func:`get_current_user`, so error handling for 401/403/404 lives in
exactly one place.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Path, Query, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import Repository, User, Visibility

# ``auto_error=False`` lets us raise a consistent 401 ourselves.
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_PREFIX}/auth/login",
    auto_error=False,
)

DbSession = Annotated[Session, Depends(get_db)]
BearerToken = Annotated[str | None, Depends(oauth2_scheme)]


def _unauthorized(detail: str = "Could not validate credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user_optional(token: BearerToken, db: DbSession) -> User | None:
    """Resolve the bearer token to a user, or ``None`` when absent/invalid."""
    if not token:
        return None

    payload = decode_access_token(token)
    if not payload:
        return None

    raw_subject = payload.get("sub")
    try:
        user_id = uuid.UUID(str(raw_subject))
    except (TypeError, ValueError):
        return None

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        return None
    return user


def get_current_user(token: BearerToken, db: DbSession) -> User:
    """Require an authenticated, active user."""
    user = get_current_user_optional(token, db)
    if user is None:
        raise _unauthorized()
    return user


def get_current_superuser(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    """Require an administrator account."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required.",
        )
    return current_user


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_current_user_optional)]
SuperUser = Annotated[User, Depends(get_current_superuser)]


# --------------------------------------------------------------------------- #
# Lookups
# --------------------------------------------------------------------------- #
def get_user_or_404(db: Session, username: str) -> User:
    """Fetch a user by username (case-insensitive)."""
    user = db.execute(
        select(User).where(User.username.ilike(username))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{username}' not found.",
        )
    return user


def can_view(repo: Repository, viewer: User | None) -> bool:
    """Visibility check for a repository."""
    if repo.visibility == Visibility.PUBLIC:
        return True
    if viewer is None:
        return False
    return viewer.id == repo.user_id or viewer.is_superuser


def get_repo_or_404(
    db: Session,
    username: str,
    repo_name: str,
    viewer: User | None,
) -> Repository:
    """
    Fetch ``username/repo_name``.

    Private repositories are reported as 404 (not 403) to avoid leaking their
    existence — the same behaviour as GitHub.
    """
    owner = get_user_or_404(db, username)
    repo = db.execute(
        select(Repository).where(
            Repository.user_id == owner.id,
            Repository.name == repo_name,
        )
    ).scalar_one_or_none()

    if repo is None or not can_view(repo, viewer):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository '{username}/{repo_name}' not found.",
        )
    return repo


def get_owned_repo_or_404(db: Session, repo_id: uuid.UUID, user: User) -> Repository:
    """Fetch a repository by id and require ownership."""
    repo = db.get(Repository, repo_id)
    if repo is None or not can_view(repo, user):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found.",
        )
    if repo.user_id != user.id and not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have write access to this repository.",
        )
    return repo


def get_writable_repo(db: Session, repo_id: uuid.UUID, user: User) -> Repository:
    """Alias used by the push endpoint (ownership required)."""
    return get_owned_repo_or_404(db, repo_id, user)


# --------------------------------------------------------------------------- #
# Pagination
# --------------------------------------------------------------------------- #
class Pagination:
    """Simple offset pagination shared by list endpoints."""

    def __init__(
        self,
        page: Annotated[int, Query(ge=1, le=10_000, description="1-based page number")] = 1,
        per_page: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 30,
    ) -> None:
        self.page = page
        self.per_page = per_page

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page

    @property
    def limit(self) -> int:
        return self.per_page


PageParams = Annotated[Pagination, Depends(Pagination)]

RepoNamePath = Annotated[str, Path(min_length=1, max_length=100, description="Repository name")]
UsernamePath = Annotated[str, Path(min_length=1, max_length=39, description="Username")]


__all__ = [
    "CurrentUser",
    "DbSession",
    "OptionalUser",
    "PageParams",
    "Pagination",
    "RepoNamePath",
    "SuperUser",
    "UsernamePath",
    "can_view",
    "get_current_superuser",
    "get_current_user",
    "get_current_user_optional",
    "get_owned_repo_or_404",
    "get_repo_or_404",
    "get_user_or_404",
    "get_writable_repo",
]
