"""Commit + AI review schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Severity


class AuthorRead(BaseModel):
    """Minimal author info embedded in commit payloads."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    avatar_url: str | None = None


class CommitRead(BaseModel):
    """Commit row for lists and headers."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    commit_hash: str
    short_hash: str
    parent_hash: str | None = None
    message: str
    summary: str
    author: AuthorRead | None = None
    timestamp: datetime
    files_changed: int = 0
    additions: int = 0
    deletions: int = 0
    ai_reviewed: bool = False
    message_generated: bool = False


class AIReviewRead(BaseModel):
    """One AI review comment."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    review_text: str
    line_number: int | None = None
    file_path: str | None = None
    severity: Severity
    title: str | None = None
    created_at: datetime


class CommitDetail(CommitRead):
    """``GET /api/repos/{repo_id}/commits/{hash}`` response."""

    diff: str | None = None
    reviews: list[AIReviewRead] = Field(default_factory=list)


class CommitListResponse(BaseModel):
    """Paginated commit history."""

    items: list[CommitRead]
    total: int
    page: int
    per_page: int


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
class HeatmapDay(BaseModel):
    """One square in the contribution heatmap."""

    date: str = Field(description="ISO date, YYYY-MM-DD")
    count: int
    level: int = Field(ge=0, le=4, description="0-4 intensity bucket")
    additions: int = 0
    deletions: int = 0


class StreakStats(BaseModel):
    """Streak + roll-up statistics for the profile header."""

    total_commits: int
    total_additions: int
    total_deletions: int
    current_streak: int
    longest_streak: int
    active_days: int
    first_commit_at: datetime | None = None
    last_commit_at: datetime | None = None
    repos_contributed_to: int = 0


class HeatmapResponse(BaseModel):
    """``GET /api/dashboard/heatmap`` response."""

    days: list[HeatmapDay]
    stats: StreakStats
    # e.g. {"2026": 412, "2025": 38} — per-year contribution totals.
    yearly_totals: dict[str, int] = Field(default_factory=dict)


class ActivityPoint(BaseModel):
    """Weekly commit totals — consumed by the Recharts activity chart."""

    week_start: str
    commits: int
    additions: int
    deletions: int


class LanguageStat(BaseModel):
    """Language breakdown for the doughnut chart."""

    language: str
    repo_count: int
    percentage: float


class DashboardResponse(BaseModel):
    """Aggregated dashboard payload (heatmap + charts + pinned repos)."""

    heatmap: HeatmapResponse
    activity: list[ActivityPoint]
    languages: list[LanguageStat]
    pinned_repos: list["RepoRead"] = Field(default_factory=list)


# Resolved at the bottom of the module to avoid a circular import with
# ``app.schemas.repository`` (which itself references ``CommitRead``).
from app.schemas.repository import RepoRead  # noqa: E402

DashboardResponse.model_rebuild()
