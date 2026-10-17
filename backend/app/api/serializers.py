"""ORM -> Pydantic serialisers shared by the route modules."""

from __future__ import annotations

from app.models import AIReview, Commit, File, Repository, UserSkill
from app.schemas import (
    AIReviewRead,
    AuthorRead,
    CommitDetail,
    CommitRead,
    FileRead,
    RepoRead,
    UserSkillRead,
)


def serialize_repo(repo: Repository) -> RepoRead:
    """Repository ORM row -> summary card DTO."""
    return RepoRead(
        id=repo.id,
        name=repo.name,
        description=repo.description,
        visibility=repo.visibility,
        primary_language=repo.primary_language,
        topics=repo.topic_list,
        owner_username=repo.owner.username if repo.owner else "",
        star_count=repo.star_count,
        is_pinned=repo.is_pinned,
        commit_count=repo.commit_count,
        file_count=repo.file_count,
        default_branch=repo.default_branch or "main",
        indexed_at=repo.indexed_at,
        created_at=repo.created_at,
        updated_at=repo.updated_at,
    )


def serialize_commit(commit: Commit) -> CommitRead:
    """Commit ORM row -> list/header DTO (uses the model's computed properties)."""
    return CommitRead(
        id=commit.id,
        commit_hash=commit.commit_hash,
        short_hash=commit.short_hash,
        parent_hash=commit.parent_hash,
        message=commit.message,
        summary=commit.summary,
        author=AuthorRead.model_validate(commit.author, from_attributes=True) if commit.author else None,
        timestamp=commit.timestamp,
        files_changed=commit.files_changed,
        additions=commit.additions,
        deletions=commit.deletions,
        ai_reviewed=commit.ai_reviewed,
        message_generated=commit.message_generated,
    )


def serialize_commit_detail(commit: Commit) -> CommitDetail:
    """Commit ORM row -> full detail payload (diff + AI review comments)."""
    base = serialize_commit(commit)
    return CommitDetail(
        **base.model_dump(),
        diff=commit.diff,
        reviews=[serialize_review(r) for r in commit.reviews],
    )


def serialize_review(review: AIReview) -> AIReviewRead:
    """AI review row -> DTO."""
    return AIReviewRead.model_validate(review, from_attributes=True)


def serialize_file(file_row: File, *, with_content: bool = False) -> FileRead | dict:
    """File ORM row -> metadata DTO (optionally including content)."""
    payload = {
        "id": file_row.id,
        "file_path": file_row.file_path,
        "size_bytes": file_row.size_bytes,
        "line_count": file_row.line_count,
        "language": file_row.language,
        "is_binary": bool(file_row.is_binary),
        "blob_hash": file_row.blob_hash,
        "updated_at": file_row.updated_at,
    }
    if with_content:
        payload["content"] = file_row.content
    return payload


def serialize_skill(skill: UserSkill) -> UserSkillRead:
    """Skill row -> badge DTO."""
    return UserSkillRead.model_validate(skill, from_attributes=True)


__all__ = [
    "serialize_commit",
    "serialize_commit_detail",
    "serialize_file",
    "serialize_repo",
    "serialize_review",
    "serialize_skill",
]
