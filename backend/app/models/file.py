"""``files`` table — the working tree snapshot."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:  # pragma: no cover
    from app.models.commit import Commit
    from app.models.repository import Repository


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class File(Base):
    """
    The *current* content of a file inside a repository.

    Historical content is reconstructible from the Git object database; this
    table is the fast path for rendering the repo browse view and for the
    AI ingestion pipeline.
    """

    __tablename__ = "files"
    __table_args__ = (
        UniqueConstraint("repo_id", "file_path", name="uq_files_repo_id_file_path"),
        Index("ix_files_repo_id_file_path", "repo_id", "file_path"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # --- Git metadata ----------------------------------------------------- #
    blob_hash: Mapped[str | None] = mapped_column(String(40), nullable=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    line_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Non-UTF8 / binary payloads are stored as empty content with this flag.
    is_binary: Mapped[bool] = mapped_column(Integer, default=0, nullable=False)

    # --- Pointers --------------------------------------------------------- #
    last_modified_commit_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("commits.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    # --- Relationships ---------------------------------------------------- #
    repository: Mapped["Repository"] = relationship("Repository", back_populates="files")
    last_modified_commit: Mapped["Commit | None"] = relationship("Commit", back_populates="files")

    def __str__(self) -> str:  # pragma: no cover
        return self.file_path
