"""
ORM model registry.

Importing ``app.models`` pulls in every table definition so that
``Base.metadata.create_all()`` and Alembic autogenerate see the full schema.
"""

from app.models.ai_review import AIReview
from app.models.commit import Commit
from app.models.enums import ChangeType, Proficiency, Severity, Visibility
from app.models.file import File
from app.models.repository import Repository
from app.models.skill import UserSkill
from app.models.user import User

__all__ = [
    "AIReview",
    "ChangeType",
    "Commit",
    "File",
    "Proficiency",
    "Repository",
    "Severity",
    "User",
    "UserSkill",
    "Visibility",
]
