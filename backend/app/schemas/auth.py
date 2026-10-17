"""Authentication request/response models."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.security import is_valid_username


class UserRegister(BaseModel):
    """``POST /api/auth/register`` payload."""

    username: str = Field(min_length=2, max_length=39, examples=["octocat"])
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=120)

    @field_validator("username")
    @classmethod
    def _validate_username(cls, value: str) -> str:
        value = value.strip()
        if not is_valid_username(value):
            raise ValueError(
                "Username may only contain letters, numbers and hyphens, "
                "and must start/end with an alphanumeric character."
            )
        return value

    @field_validator("password")
    @classmethod
    def _validate_password(cls, value: str) -> str:
        if value.strip() != value:
            raise ValueError("Password must not start or end with whitespace.")
        return value


class UserLogin(BaseModel):
    """JSON login payload (the OAuth2 form variant is also supported)."""

    username: str = Field(description="Username or email address")
    password: str


class Token(BaseModel):
    """OAuth2 compatible token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Token lifetime in seconds")


class AuthResponse(Token):
    """
    Token + the authenticated user.

    Returned by ``/register`` and ``/login`` so the frontend can hydrate its
    auth context with a single round-trip.
    """

    user: "UserMe"


class TokenPayload(BaseModel):
    """Decoded JWT claims."""

    model_config = ConfigDict(extra="ignore")

    sub: uuid.UUID
    exp: int
    iat: int | None = None
    iss: str | None = None


# Resolved at the bottom to keep ``app.schemas.auth`` importable on its own.
from app.schemas.user import UserMe  # noqa: E402

AuthResponse.model_rebuild()
