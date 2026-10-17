"""``commits`` table."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:  # pragma: no cover
    from app.models.ai_review import AIReview
    from app.models.file import File
    from app.models.repository import Repository
    from app.models.user import User


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Commit(Base):
    """
    An immutable snapshot pointer.

    ``commit_hash`` is a genuine Git SHA-1 produced by libgit2 (via pygit2),
    so hashes are compatible with real ``git`` tooling.
    """

    __tablename__ = "commits"
    __table_args__ = (
        # The same hash can exist in different repositories, but not twice in one.
        UniqueConstraint("repo_id", "commit_hash", name="uq_commits_repo_id_commit_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    commit_hash: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    parent_hash: Mapped[str | None] = mapped_column(String(40), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # --- Diff payload (also fed to the AI reviewer) ----------------------- #
    diff: Mapped[str | None] = mapped_column(Text, nullable=True)
    files_changed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    additions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    deletions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # --- AI bookkeeping --------------------------------------------------- #
    ai_reviewed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_review_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # True when the message was produced by the Auto-Commit Message Generator.
    message_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # --- Timestamps ------------------------------------------------------- #
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True, nullable=False
    )

    # --- Relationships ---------------------------------------------------- #
    repository: Mapped["Repository"] = relationship("Repository", back_populates="commits")
    author: Mapped["User"] = relationship("User", back_populates="commits", lazy="joined")
    reviews: Mapped[list["AIReview"]] = relationship(
        "AIReview",
        back_populates="commit",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="AIReview.line_number",
    )
    files: Mapped[list["File"]] = relationship(
        "File",
        back_populates="last_modified_commit",
        passive_deletes=True,
    )

    # --- Helpers ---------------------------------------------------------- #
    @property
    def short_hash(self) -> str:
        return self.commit_hash[:7]

    @property
    def summary(self) -> str:
        """First line of the commit message."""
        return self.message.splitlines()[0] if self.message else ""

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.short_hash} {self.summary}"
