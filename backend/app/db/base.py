"""
Declarative base + metadata conventions.

Importing this module guarantees that **every** model has been registered on
``Base.metadata``, so ``Base.metadata.create_all()`` and Alembic autogenerate
both see the whole schema.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Deterministic constraint names make Alembic migrations reviewable.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Common declarative base for all GitFolio ORM models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        pk = getattr(self, "id", None)
        return f"<{type(self).__name__} id={pk}>"


# Import every model module so their tables attach to ``Base.metadata``.
# (Kept at the bottom to avoid circular imports at module load time.)
from app.models import (  # noqa: E402,F401  pylint: disable=wrong-import-position
    ai_review,
    commit,
    file,
    repository,
    skill,
    user,
)

__all__ = ["Base", "NAMING_CONVENTION"]
