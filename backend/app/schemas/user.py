"""User + profile schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl

from app.schemas.skill import UserSkillRead


class UserBase(BaseModel):
    username: str
    display_name: str | None = None
    avatar_url: str | None = None
    bio: str | None = None
    location: str | None = None
    company: str | None = None
    website: str | None = None


class UserCreate(UserBase):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    """Partial profile update — every field is optional."""

    display_name: str | None = Field(default=None, max_length=120)
    avatar_url: HttpUrl | None = None
    bio: str | None = Field(default=None, max_length=2000)
    location: str | None = Field(default=None, max_length=120)
    company: str | None = Field(default=None, max_length=120)
    website: str | None = Field(default=None, max_length=512)


class UserRead(UserBase):
    """Public representation of an account."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    followers_count: int
    following_count: int
    created_at: datetime


class UserMe(UserRead):
    """Authenticated user — includes private fields."""

    email: EmailStr
    is_superuser: bool
    skills_analyzed_at: datetime | None = None


class UserProfile(UserRead):
    """
    Profile page payload: the public user plus their AI skill badges and a
    roll-up of languages across all repositories.
    """

    skills: list[UserSkillRead] = Field(default_factory=list)
    languages: dict[str, int] = Field(
        default_factory=dict,
        description="Language name -> number of repositories using it",
    )
    total_commits: int = 0
    total_repos: int = 0
    total_stars: int = 0
    followers: list[str] = Field(default_factory=list, description="Usernames")
    following: list[str] = Field(default_factory=list, description="Usernames")
