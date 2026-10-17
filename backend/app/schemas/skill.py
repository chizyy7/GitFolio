"""Skill badge schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Proficiency


class UserSkillRead(BaseModel):
    """A rendered skill badge."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    skill_name: str
    proficiency: Proficiency
    category: str
    confidence: int = 0
    evidence: str | None = None


class AISkillProfile(BaseModel):
    """
    Strict shape the LLM must return from the skill-mapper prompt.

    Kept separate from the ORM model so the model output can be validated
    before it ever touches the database.
    """

    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    databases: list[str] = Field(default_factory=list)
    proficiency: Proficiency = Proficiency.INTERMEDIATE
    summary: str | None = None


class SkillProfileResponse(AISkillProfile):
    """API response for ``POST /api/ai/skills/refresh``."""

    username: str
    generated_at: datetime
