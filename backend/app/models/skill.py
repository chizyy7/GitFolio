"""``user_skills`` table — AI-generated skill badges."""

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
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import Proficiency, enum_values

if TYPE_CHECKING:  # pragma: no cover
    from app.models.user import User


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserSkill(Base):
    """A skill badge shown on the profile sidebar (e.g. ``FastAPI`` → Advanced)."""

    __tablename__ = "user_skills"
    __table_args__ = (
        UniqueConstraint("user_id", "skill_name", name="uq_user_skills_user_id_skill_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    skill_name: Mapped[str] = mapped_column(String(80), nullable=False)
    proficiency: Mapped[Proficiency] = mapped_column(
        SAEnum(
            Proficiency,
            name="proficiency_enum",
            values_callable=enum_values,
            native_enum=True,
        ),
        default=Proficiency.INTERMEDIATE,
        nullable=False,
    )

    # --- Provenance ------------------------------------------------------- #
    # "language" | "framework" | "tool" | "database" | "other"
    category: Mapped[str] = mapped_column(String(40), default="other", nullable=False)
    # Rough confidence/weight 0-100 computed from how much code uses the skill.
    confidence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    evidence: Mapped[str | None] = mapped_column(String(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # --- Relationships ---------------------------------------------------- #
    user: Mapped["User"] = relationship("User", back_populates="skills")

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.skill_name} ({self.proficiency})"
