"""
Dashboard routes — contribution heatmap, streak statistics and charts.

    GET /api/dashboard/{username}            aggregated dashboard payload
    GET /api/dashboard/{username}/heatmap    heatmap squares + stats
    GET /api/dashboard/{username}/stats      streak / totals only

Aggregation happens in Python on purpose: a portfolio account has thousands of
commits at most, and this keeps the queries portable across PostgreSQL and the
SQLite database used by the test-suite.
"""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import DbSession, OptionalUser, UsernamePath, can_view, get_user_or_404
from app.api.serializers import serialize_repo
from app.models import Commit, Repository, Visibility
from app.schemas import (
    ActivityPoint,
    DashboardResponse,
    HeatmapDay,
    HeatmapResponse,
    LanguageStat,
    StreakStats,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

# GitHub's five-step intensity buckets.
LEVEL_THRESHOLDS = ((0, 0), (3, 1), (6, 2), (10, 3))
MAX_LEVEL = 4


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _level(count: int) -> int:
    """Map a daily commit count onto GitHub's 0-4 intensity scale."""
    if count <= 0:
        return 0
    if count <= 3:
        return 1
    if count <= 6:
        return 2
    if count <= 10:
        return 3
    return MAX_LEVEL


def _as_date(value: datetime) -> date:
    """UTC calendar date for a (possibly naive) datetime."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).date()


def _fetch_commits(
    db: DbSession,
    user_id: uuid.UUID,
    repo_ids: list[uuid.UUID] | None = None,
) -> list[tuple[datetime, int, int, uuid.UUID]]:
    """Return ``(timestamp, additions, deletions, repo_id)`` for a user's commits."""
    statement = select(Commit.timestamp, Commit.additions, Commit.deletions, Commit.repo_id).where(
        Commit.author_id == user_id
    )
    if repo_ids is not None:
        if not repo_ids:
            return []
        statement = statement.where(Commit.repo_id.in_(repo_ids))
    return [tuple(row) for row in db.execute(statement).all()]  # type: ignore[misc]


def _build_heatmap(
    commits: list[tuple[datetime, int, int, uuid.UUID]],
    *,
    weeks: int = 53,
    include_future: bool = False,
) -> HeatmapResponse:
    """Build the heatmap grid (one entry per calendar day) plus roll-up stats."""
    per_day: Counter[date] = Counter()
    additions_by_day: Counter[date] = Counter()
    deletions_by_day: Counter[date] = Counter()

    for timestamp, additions, deletions, _repo_id in commits:
        day = _as_date(timestamp)
        per_day[day] += 1
        additions_by_day[day] += int(additions or 0)
        deletions_by_day[day] += int(deletions or 0)

    today = datetime.now(timezone.utc).date()
    # Align the first column to a Sunday so the grid renders like GitHub's.
    end = today
    start = today - timedelta(days=weeks * 7 - 1)
    start -= timedelta(days=(start.weekday() + 1) % 7)  # back up to Sunday

    days: list[HeatmapDay] = []
    cursor = start
    while cursor <= end or include_future:
        count = per_day.get(cursor, 0)
        days.append(
            HeatmapDay(
                date=cursor.isoformat(),
                count=count,
                level=_level(count),
                additions=additions_by_day.get(cursor, 0),
                deletions=deletions_by_day.get(cursor, 0),
            )
        )
        cursor += timedelta(days=1)
        if include_future and cursor > end:
            break

    yearly: Counter[str] = Counter()
    for day, count in per_day.items():
        yearly[str(day.year)] += count

    stats = _compute_stats(per_day, additions_by_day, deletions_by_day, commits)

    return HeatmapResponse(
        days=days,
        stats=stats,
        yearly_totals=dict(sorted(yearly.items())),
    )


def _compute_stats(
    per_day: Counter[date],
    additions_by_day: Counter[date],
    deletions_by_day: Counter[date],
    commits: list[tuple[datetime, int, int, uuid.UUID]],
) -> StreakStats:
    """Total commits, additions/deletions and current/longest streaks."""
    active_days = sorted(per_day)

    longest = 0
    run = 0
    previous: date | None = None
    for day in active_days:
        if previous is not None and (day - previous).days == 1:
            run += 1
        else:
            run = 1
        longest = max(longest, run)
        previous = day

    today = datetime.now(timezone.utc).date()
    current = 0
    if active_days:
        # A streak is "alive" if the most recent commit was today or yesterday.
        latest = active_days[-1]
        if latest in (today, today - timedelta(days=1)):
            probe = latest
            active = set(active_days)
            while probe in active:
                current += 1
                probe -= timedelta(days=1)

    timestamps = [_as_date(ts) for ts, _a, _d, _r in commits] or [None]

    return StreakStats(
        total_commits=sum(per_day.values()),
        total_additions=sum(additions_by_day.values()),
        total_deletions=sum(deletions_by_day.values()),
        current_streak=current,
        longest_streak=longest,
        active_days=len(active_days),
        first_commit_at=min((ts for ts, _a, _d, _r in commits), default=None),
        last_commit_at=max((ts for ts, _a, _d, _r in commits), default=None),
        repos_contributed_to=len({repo_id for _ts, _a, _d, repo_id in commits}),
    )


def _weekly_activity(
    commits: list[tuple[datetime, int, int, uuid.UUID]],
    *,
    weeks: int = 26,
) -> list[ActivityPoint]:
    """Aggregate the last ``weeks`` weeks into Recharts-friendly points."""
    today = datetime.now(timezone.utc).date()
    this_monday = today - timedelta(days=today.weekday())
    first_monday = this_monday - timedelta(weeks=weeks - 1)

    buckets: dict[date, dict[str, int]] = {
        first_monday + timedelta(weeks=i): {"commits": 0, "additions": 0, "deletions": 0}
        for i in range(weeks)
    }

    for timestamp, additions, deletions, _repo_id in commits:
        day = _as_date(timestamp)
        if day < first_monday:
            continue
        monday = day - timedelta(days=day.weekday())
        if monday in buckets:
            buckets[monday]["commits"] += 1
            buckets[monday]["additions"] += int(additions or 0)
            buckets[monday]["deletions"] += int(deletions or 0)

    return [
        ActivityPoint(
            week_start=monday.isoformat(),
            commits=values["commits"],
            additions=values["additions"],
            deletions=values["deletions"],
        )
        for monday, values in sorted(buckets.items())
    ]


def _language_stats(repos: list[Repository]) -> list[LanguageStat]:
    """Language distribution across a user's repositories."""
    counts: Counter[str] = Counter(repo.primary_language for repo in repos if repo.primary_language)
    total = sum(counts.values()) or 1
    return [
        LanguageStat(
            language=language,
            repo_count=count,
            percentage=round(count * 100 / total, 2),
        )
        for language, count in counts.most_common()
    ]


def _visible_repos(db: DbSession, user_id: uuid.UUID, viewer) -> list[Repository]:
    """Repositories on a profile the viewer is allowed to see."""
    statement = select(Repository).where(Repository.user_id == user_id)
    repos = list(db.execute(statement).scalars())
    return [repo for repo in repos if repo.visibility == Visibility.PUBLIC or (viewer and (viewer.id == user_id or viewer.is_superuser))]


def _pinned(repos: list[Repository], limit: int = 6) -> list[Repository]:
    """Pinned repositories, falling back to the most active ones."""
    pinned = [repo for repo in repos if repo.is_pinned]
    if pinned:
        return sorted(pinned, key=lambda r: (-r.star_count, r.name))[:limit]
    return sorted(repos, key=lambda r: (-r.commit_count, r.name))[:limit]


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@router.get(
    "/{username}/heatmap",
    response_model=HeatmapResponse,
    summary="Contribution heatmap + streak statistics",
)
def get_heatmap(
    username: UsernamePath,
    db: DbSession,
    viewer: OptionalUser,
    weeks: int = Query(default=53, ge=1, le=106, description="Number of weeks to render"),
) -> HeatmapResponse:
    """Daily commit counts for the last ``weeks`` weeks."""
    user = get_user_or_404(db, username)
    repos = _visible_repos(db, user.id, viewer)
    commits = _fetch_commits(db, user.id, [repo.id for repo in repos])
    # Viewer-scoped stats: only count commits in repos the viewer can see.
    visible_ids = {repo.id for repo in repos}
    commits = [c for c in commits if c[3] in visible_ids]
    return _build_heatmap(commits, weeks=weeks)


@router.get(
    "/{username}/stats",
    response_model=StreakStats,
    summary="Streak and roll-up statistics",
)
def get_stats(username: UsernamePath, db: DbSession, viewer: OptionalUser) -> StreakStats:
    """Total commits, additions/deletions and current/longest streaks."""
    user = get_user_or_404(db, username)
    repos = _visible_repos(db, user.id, viewer)
    visible_ids = {repo.id for repo in repos}
    commits = [c for c in _fetch_commits(db, user.id) if c[3] in visible_ids]
    heatmap = _build_heatmap(commits)
    return heatmap.stats


@router.get(
    "/{username}",
    response_model=DashboardResponse,
    summary="Full dashboard payload (heatmap + charts + pinned repos)",
)
def get_dashboard(
    username: UsernamePath,
    db: DbSession,
    viewer: OptionalUser,
    weeks: int = Query(default=53, ge=1, le=106),
    activity_weeks: int = Query(default=26, ge=4, le=104),
) -> DashboardResponse:
    """
    One request for the whole dashboard: heatmap, weekly activity chart,
    language split and the pinned repository cards.
    """
    user = get_user_or_404(db, username)
    repos = _visible_repos(db, user.id, viewer)
    visible_ids = {repo.id for repo in repos}
    commits = [c for c in _fetch_commits(db, user.id) if c[3] in visible_ids]

    return DashboardResponse(
        heatmap=_build_heatmap(commits, weeks=weeks),
        activity=_weekly_activity(commits, weeks=activity_weeks),
        languages=_language_stats(repos),
        pinned_repos=[serialize_repo(repo) for repo in _pinned(repos)],
    )


__all__ = ["router"]
