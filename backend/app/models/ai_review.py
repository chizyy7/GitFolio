"""``ai_reviews`` table — one row per AI code-review comment."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import Severity, enum_values

if TYPE_CHECKING:  # pragma: no cover
    from app.models.commit import Commit


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AIReview(Base):
    """
    A single review comment produced by Llama 3.2 for a diff.

    ``line_number`` refers to the line in the *new* version of the file
    (i.e. the ``+`` side of the unified diff), which is what the frontend
    highlights on the commit page.
    """

    __tablename__ = "ai_reviews"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    commit_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("commits.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    review_text: Mapped[str] = mapped_column(Text, nullable=False)
    line_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    severity: Mapped[Severity] = mapped_column(
        SAEnum(
            Severity,
            name="severity_enum",
            values_callable=enum_values,
            native_enum=True,
        ),
        default=Severity.SUGGESTION,
        nullable=False,
    )
    # Optional short title ("SQL injection via f-string").
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # --- Relationships ---------------------------------------------------- #
    commit: Mapped["Commit"] = relationship("Commit", back_populates="reviews")

    def __str__(self) -> str:  # pragma: no cover
        return f"[{self.severity}] {self.file_path}:{self.line_number}"
