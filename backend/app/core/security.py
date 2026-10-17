"""
Password hashing + JWT issuance/verification.

Uses ``passlib`` (bcrypt) for password storage and ``python-jose`` for the
OAuth2 password-bearer flow consumed by the Next.js frontend.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# bcrypt with a sensible work factor. ``bcrypt`` is explicitly listed in
# requirements so passlib does not fall back to its (broken) internal backend.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,37}[a-zA-Z0-9])?$")


# --------------------------------------------------------------------------- #
# Passwords
# --------------------------------------------------------------------------- #
def hash_password(plain_password: str) -> str:
    """Return a bcrypt hash for ``plain_password``."""
    # bcrypt silently truncates at 72 bytes; truncate explicitly to avoid
    # surprising behaviour with long passphrases.
    return pwd_context.hash(plain_password[:72])


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Constant-time verification of a password against its bcrypt hash."""
    try:
        return pwd_context.verify(plain_password[:72], hashed_password)
    except ValueError:
        # Malformed / legacy hash in the database — treat as a failed login.
        return False


# --------------------------------------------------------------------------- #
# Usernames
# --------------------------------------------------------------------------- #
def is_valid_username(username: str) -> bool:
    """GitHub-compatible username validation."""
    return bool(_USERNAME_RE.match(username))


def slugify_username(value: str) -> str:
    """Best-effort conversion of arbitrary text into a valid username."""
    slug = re.sub(r"[^a-zA-Z0-9-]+", "-", value.strip().lower()).strip("-")
    return slug[:39] or "user"


# --------------------------------------------------------------------------- #
# JWT
# --------------------------------------------------------------------------- #
def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """
    Create a signed access token.

    ``subject`` is the user id (also mirrored into the ``sub`` claim).
    """
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "iss": settings.APP_NAME,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode + verify a JWT. Returns ``None`` when the token is invalid."""
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            issuer=settings.APP_NAME,
        )
    except JWTError:
        return None
