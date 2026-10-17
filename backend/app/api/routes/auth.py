"""
Authentication routes — registration, login and the current-user endpoints.

``POST /api/auth/login`` accepts **both** ``application/x-www-form-urlencoded``
(the OAuth2 password flow used by Swagger UI) and ``application/json`` (used by
the Next.js frontend).
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    hash_password,
    is_valid_username,
    verify_password,
)
from app.models import User
from app.schemas import AuthResponse, UserLogin, UserMe, UserRegister, UserUpdate

logger = get_logger("api.auth")

router = APIRouter(prefix="/auth", tags=["Auth"])

# Password used to synthesise a throwaway hash. Verifying against it keeps the
# login response time constant whether or not the account exists (mitigates
# username enumeration). The literal is never a valid credential because the
# branch it guards always raises.
_TIMING_DUMMY_PASSWORD = "gitfolio-timing-equaliser-do-not-use"


@lru_cache(maxsize=1)
def _dummy_password_hash() -> str:
    """Lazily-computed bcrypt hash used only to equalise login timing."""
    return hash_password(_TIMING_DUMMY_PASSWORD)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _default_avatar(username: str) -> str:
    """Deterministic, dependency-free avatar (DiceBear identicon)."""
    return f"https://api.dicebear.com/7.x/identicon/svg?seed={username}&backgroundType=gradientLinear"


def _issue_token(user: User) -> AuthResponse:
    """Build the standard token response for a user."""
    token = create_access_token(
        subject=str(user.id),
        extra_claims={"username": user.username},
    )
    return AuthResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserMe.model_validate(user, from_attributes=True),
    )


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new GitFolio account",
)
def register(payload: UserRegister, db: DbSession) -> AuthResponse:
    """
    Create an account.

    Returns a JWT immediately so the frontend can log the user straight in.
    """
    existing_username = db.execute(
        select(User).where(func.lower(User.username) == payload.username.lower())
    ).scalar_one_or_none()
    if existing_username is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That username is already taken.",
        )

    existing_email = db.execute(
        select(User).where(func.lower(User.email) == payload.email.lower())
    ).scalar_one_or_none()
    if existing_email is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists.",
        )

    user = User(
        username=payload.username,
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
        display_name=payload.display_name or payload.username,
        avatar_url=_default_avatar(payload.username),
        bio=None,
        followers_count=0,
        following_count=0,
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info("New account created: @%s", user.username)
    return _issue_token(user)


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Exchange credentials for a JWT",
)
async def login(request: Request, db: DbSession) -> AuthResponse:
    """
    Authenticate with username (or email) + password.

    Supports both JSON and form-encoded bodies.
    """
    content_type = (request.headers.get("content-type") or "").lower()

    username: str | None = None
    password: str | None = None

    if "application/json" in content_type:
        try:
            payload = UserLogin.model_validate(await request.json())
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid login payload: {exc}",
            ) from exc
        username, password = payload.username, payload.password
    else:
        form = await request.form()
        raw_username = form.get("username")
        raw_password = form.get("password")
        username = str(raw_username) if raw_username is not None else None
        password = str(raw_password) if raw_password is not None else None

    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Both 'username' and 'password' are required.",
        )

    user = db.execute(
        select(User).where(
            (func.lower(User.username) == username.lower())
            | (func.lower(User.email) == username.lower())
        )
    ).scalar_one_or_none()

    # Always run a hash comparison to avoid user-enumeration timing leaks.
    if user is None:
        verify_password(password, _dummy_password_hash())
        logger.warning("Failed login attempt for %r", username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(password, user.hashed_password):
        logger.warning("Failed login attempt for %r", username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated.",
        )

    return _issue_token(user)


@router.get("/me", response_model=UserMe, summary="Get the authenticated user")
def read_me(current_user: CurrentUser) -> UserMe:
    """Return the profile of the bearer-token owner."""
    return UserMe.model_validate(current_user, from_attributes=True)


@router.patch("/me", response_model=UserMe, summary="Update the authenticated user's profile")
def update_me(payload: UserUpdate, current_user: CurrentUser, db: DbSession) -> UserMe:
    """Partial profile update — only the provided fields are written."""
    data = payload.model_dump(exclude_unset=True, exclude_none=True)

    for field, value in data.items():
        if field == "avatar_url" and value is not None:
            value = str(value)
        setattr(current_user, field, value)

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return UserMe.model_validate(current_user, from_attributes=True)


@router.post("/refresh", response_model=AuthResponse, summary="Re-issue the access token")
def refresh_token(current_user: CurrentUser) -> AuthResponse:
    """Exchange a still-valid token for a fresh one."""
    return _issue_token(current_user)


@router.get(
    "/check-username/{username}",
    summary="Check whether a username is available",
)
def check_username(username: str, db: DbSession) -> dict[str, object]:
    """Used by the registration form for live validation."""
    taken = (
        db.execute(select(User.id).where(func.lower(User.username) == username.lower())).scalar_one_or_none()
        is not None
    )
    return {
        "username": username,
        "available": not taken,
        "valid": is_valid_username(username),
    }
