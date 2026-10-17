"""
Enumerations shared by the ORM models and the Pydantic schemas.

Each enum subclasses ``str`` so it serialises straight to JSON, and each is
persisted with ``native_enum`` using the **member value** (e.g. ``"Public"``)
rather than the Python member name.
"""

from __future__ import annotations

import enum


class Visibility(str, enum.Enum):
    """Repository visibility."""

    PUBLIC = "Public"
    PRIVATE = "Private"


class Severity(str, enum.Enum):
    """Severity of an AI code-review comment."""

    BUG = "Bug"
    SECURITY = "Security"
    STYLE = "Style"
    SUGGESTION = "Suggestion"


class Proficiency(str, enum.Enum):
    """Self/AI assessed proficiency for a skill."""

    BEGINNER = "Beginner"
    INTERMEDIATE = "Intermediate"
    ADVANCED = "Advanced"


class ChangeType(str, enum.Enum):
    """How a file changed in a commit (derived from the Git diff)."""

    ADDED = "Added"
    MODIFIED = "Modified"
    DELETED = "Deleted"
    RENAMED = "Renamed"


# Helper used by ``sqlalchemy.Enum`` so the DB stores the *values*.
def enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    """Return the list of ``.value`` strings for a ``str``-Enum."""
    return [member.value for member in enum_cls]
