"""
Public profile routes — the data behind the GitHub-style profile page.
"""

from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Query
from sqlalchemy import func, or_, select

from app.api.deps import DbSession, PageParams, UsernamePath, get_user_or_404
from app.api.serializers import serialize_skill
from app.models import Commit, Repository, User
from app.schemas import UserProfile, UserRead
from app.services.ai.skills import get_or_create_skills

router = APIRouter(prefix="/users", tags=["Profiles"])


@router.get(
    "",
    response_model=list[UserRead],
    summary="List GitFolio accounts (for the explore page)",
)
def list_users(
    db: DbSession,
    page: PageParams,
    q: str | None = Query(default=None, max_length=100, description="Search username or display name"),
) -> list[UserRead]:
    """Newest accounts first, optionally filtered by a search term."""
    statement = select(User).where(User.is_active.is_(True))

    if q:
        needle = f"%{q.lower()}%"
        statement = statement.where(
            or_(
                func.lower(User.username).like(needle),
                func.lower(func.coalesce(User.display_name, "")).like(needle),
            )
        )

    users = list(
        db.execute(
            statement.order_by(User.created_at.desc()).offset(page.offset).limit(page.limit)
        ).scalars()
    )
    return [UserRead.model_validate(user, from_attributes=True) for user in users]


@router.get(
    "/{username}",
    response_model=UserProfile,
    summary="Public profile: bio, stats, languages and AI skill badges",
)
def get_profile(username: UsernamePath, db: DbSession) -> UserProfile:
    """
    Everything the profile sidebar and header need in one call:

    * identity + bio + follower counters
    * repository language roll-up (for the doughnut chart)
    * total commits / repos / stars
    * AI-generated skill badges (generated lazily on first view)
    """
    user = get_user_or_404(db, username)

    repos = list(
        db.execute(select(Repository).where(Repository.user_id == user.id)).scalars()
    )

    languages: Counter[str] = Counter()
    for repo in repos:
        if repo.primary_language:
            languages[repo.primary_language] += 1

    total_commits = int(
        db.execute(
            select(func.count(Commit.id)).where(Commit.author_id == user.id)
        ).scalar_one()
    )

    # Skills are generated on demand; failures degrade to an empty list.
    try:
        skills = get_or_create_skills(db, user)
    except Exception:  # pragma: no cover - AI stack unavailable
        skills = list(user.skills or [])

    return UserProfile(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        bio=user.bio,
        location=user.location,
        company=user.company,
        website=user.website,
        followers_count=user.followers_count,
        following_count=user.following_count,
        created_at=user.created_at,
        skills=[serialize_skill(s) for s in skills],
        languages=dict(languages.most_common()),
        total_commits=total_commits,
        total_repos=len(repos),
        total_stars=sum(repo.star_count for repo in repos),
        # A full follow graph is out of scope for v1 — the counters are real.
        followers=[],
        following=[],
    )


@router.get(
    "/{username}/languages",
    summary="Language distribution for a user's repositories",
)
def get_languages(username: UsernamePath, db: DbSession) -> dict[str, int]:
    """``{language: repo_count}`` — drives the profile doughnut chart."""
    user = get_user_or_404(db, username)
    rows = db.execute(
        select(Repository.primary_language, func.count(Repository.id))
        .where(Repository.user_id == user.id, Repository.primary_language.is_not(None))
        .group_by(Repository.primary_language)
        .order_by(func.count(Repository.id).desc())
    ).all()
    return {str(language): int(count) for language, count in rows}
