"""Repository, file-tree and push (version-control) schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import settings
from app.models.enums import ChangeType, Visibility


# --------------------------------------------------------------------------- #
# Repository
# --------------------------------------------------------------------------- #
class RepoBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    visibility: Visibility = Visibility.PUBLIC
    primary_language: str | None = Field(default=None, max_length=50)
    topics: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned.replace("-", "").replace("_", "").replace(".", "").isalnum():
            raise ValueError("Repository names may only contain letters, numbers, '-', '_' and '.'")
        return cleaned


class RepoCreate(RepoBase):
    """``POST /api/repos`` payload."""

    # Index the repository for AI search immediately after creation.
    auto_index: bool = True


class RepoUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=2000)
    visibility: Visibility | None = None
    primary_language: str | None = Field(default=None, max_length=50)
    topics: list[str] | None = None
    is_pinned: bool | None = None
    star_count: int | None = Field(default=None, ge=0)


class RepoRead(RepoBase):
    """Repository summary card."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_username: str = ""
    primary_language: str | None = None
    star_count: int = 0
    is_pinned: bool = False
    commit_count: int = 0
    file_count: int = 0
    default_branch: str = "main"
    indexed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# File tree / contents
# --------------------------------------------------------------------------- #
class FileNode(BaseModel):
    """A node in the rendered repository tree."""

    name: str
    path: str
    type: str = Field(description="'blob' (file) or 'tree' (directory)")
    size: int | None = None
    language: str | None = None
    children: list["FileNode"] | None = None


FileNode.model_rebuild()


class FileRead(BaseModel):
    """File metadata without the payload."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    file_path: str
    size_bytes: int
    line_count: int
    language: str | None = None
    is_binary: bool = False
    blob_hash: str | None = None
    updated_at: datetime


class FileContent(FileRead):
    """File metadata plus its text content."""

    content: str = ""


class RepoDetail(RepoRead):
    """``GET /api/repos/{username}/{repo_name}`` response."""

    owner_avatar_url: str | None = None
    tree: list[FileNode] = Field(default_factory=list)
    latest_commit: "CommitRead | None" = None


# --------------------------------------------------------------------------- #
# Push
# --------------------------------------------------------------------------- #
class PushFile(BaseModel):
    """One file in a push."""

    path: str = Field(min_length=1, max_length=1024)
    content: str = ""

    @field_validator("path")
    @classmethod
    def _normalise_path(cls, value: str) -> str:
        # Reject path traversal / absolute paths / backslashes.
        path = value.replace("\\", "/").lstrip("/")
        parts = [p for p in path.split("/") if p not in ("", ".")]
        if any(p == ".." for p in parts):
            raise ValueError("File path must not contain '..'")
        if not parts:
            raise ValueError("File path must not be empty")
        normalised = "/".join(parts)
        size = len(normalised.encode("utf-8"))
        if size > settings.MAX_FILE_BYTES // 8:  # path length guard
            raise ValueError("File path is unreasonably long")
        return normalised

    @field_validator("content")
    @classmethod
    def _limit_size(cls, value: str) -> str:
        if len(value.encode("utf-8")) > settings.MAX_FILE_BYTES:
            raise ValueError(f"File exceeds the {settings.MAX_FILE_BYTES // 1024} KB limit")
        return value


class PushRequest(BaseModel):
    """
    ``POST /api/repos/{repo_id}/push`` payload.

    ``commit_message`` is optional: when omitted (or blank) the
    Auto-Commit Message Generator asks Llama 3.2 to write one from the diff.
    """

    files: list[PushFile] = Field(default_factory=list)
    deleted_paths: list[str] = Field(default_factory=list)
    commit_message: str | None = Field(default=None, max_length=5000)
    branch: str | None = Field(default=None, max_length=100)
    run_ai: bool = True

    @field_validator("files")
    @classmethod
    def _limit_files(cls, value: list[PushFile]) -> list[PushFile]:
        if len(value) > settings.MAX_PUSH_FILES:
            raise ValueError(f"A single push may contain at most {settings.MAX_PUSH_FILES} files")
        # Detect duplicate paths in one push.
        seen: set[str] = set()
        for f in value:
            if f.path in seen:
                raise ValueError(f"Duplicate path in push: {f.path}")
            seen.add(f.path)
        return value


class PushFileResult(BaseModel):
    """Per-file outcome of a push."""

    path: str
    change_type: ChangeType
    additions: int = 0
    deletions: int = 0
    blob_hash: str


class PushResponse(BaseModel):
    """Result of a successful push."""

    commit_hash: str
    short_hash: str
    message: str
    message_generated: bool = False
    files_changed: int
    additions: int
    deletions: int
    files: list[PushFileResult] = Field(default_factory=list)
    ai_queued: bool = False


# Resolve the forward reference in ``RepoDetail``.
from app.schemas.commit import CommitRead  # noqa: E402

RepoDetail.model_rebuild()
