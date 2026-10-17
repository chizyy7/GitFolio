"""``users`` table + ``user_skills`` relationship."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.models.ai_review import AIReview  # noqa: F401
    from app.models.commit import Commit
    from app.models.repository import Repository
    from app.models.skill import UserSkill


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """A GitFolio account — the portfolio owner."""

    __tablename__ = "users"

    # --- Primary key ------------------------------------------------------ #
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # --- Identity --------------------------------------------------------- #
    username: Mapped[str] = mapped_column(String(39), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    # --- Profile (GitHub-style sidebar) ----------------------------------- #
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    company: Mapped[str | None] = mapped_column(String(120), nullable=True)
    website: Mapped[str | None] = mapped_column(String(512), nullable=True)
    followers_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    following_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # --- Flags ------------------------------------------------------------ #
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Set once the AI skill-mapper has profiled the account.
    skills_analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- Timestamps ------------------------------------------------------- #
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    # --- Relationships ---------------------------------------------------- #
    repositories: Mapped[list["Repository"]] = relationship(
        "Repository",
        back_populates="owner",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Repository.created_at.desc()",
    )
    commits: Mapped[list["Commit"]] = relationship(
        "Commit",
        back_populates="author",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    skills: Mapped[list["UserSkill"]] = relationship(
        "UserSkill",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="UserSkill.skill_name",
    )

    def __str__(self) -> str:  # pragma: no cover
        return f"@{self.username}"
