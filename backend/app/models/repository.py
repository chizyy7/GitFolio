"""``repositories`` table."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import Visibility, enum_values

if TYPE_CHECKING:  # pragma: no cover
    from app.models.commit import Commit
    from app.models.file import File
    from app.models.user import User


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Repository(Base):
    """A hosted repository: metadata lives here, blobs live in Postgres/Git."""

    __tablename__ = "repositories"
    __table_args__ = (
        # A user cannot own two repositories with the same name.
        UniqueConstraint("user_id", "name", name="uq_repositories_user_id_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    visibility: Mapped[Visibility] = mapped_column(
        SAEnum(
            Visibility,
            name="visibility_enum",
            values_callable=enum_values,
            native_enum=True,
        ),
        default=Visibility.PUBLIC,
        nullable=False,
    )

    primary_language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    default_branch: Mapped[str] = mapped_column(String(100), default="main", nullable=False)

    # --- Dashboard metadata ---------------------------------------------- #
    star_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    topics: Mapped[str | None] = mapped_column(Text, nullable=True)  # comma separated

    # --- Denormalised counters (cheap dashboard queries) ------------------ #
    commit_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    file_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Vector-store sync state: None = never indexed.
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- Timestamps ------------------------------------------------------- #
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    # --- Relationships ---------------------------------------------------- #
    owner: Mapped["User"] = relationship("User", back_populates="repositories", lazy="joined")
    commits: Mapped[list["Commit"]] = relationship(
        "Commit",
        back_populates="repository",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Commit.timestamp.desc()",
    )
    files: Mapped[list["File"]] = relationship(
        "File",
        back_populates="repository",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # --- Helpers ---------------------------------------------------------- #
    @property
    def full_name(self) -> str:
        """``owner/repo`` slug used in URLs."""
        owner = self.owner.username if self.owner else "unknown"
        return f"{owner}/{self.name}"

    @property
    def topic_list(self) -> list[str]:
        return [t.strip() for t in (self.topics or "").split(",") if t.strip()]

    @property
    def is_public(self) -> bool:
        return self.visibility == Visibility.PUBLIC

    def __str__(self) -> str:  # pragma: no cover
        return self.full_name
