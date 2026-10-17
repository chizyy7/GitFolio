"""
AI Code Reviewer.

On every push the unified diff is sent to Llama 3.2 with a strict
"return JSON only" contract.  Comments are validated, severity-normalised and
persisted as ``ai_reviews`` rows tied to the commit.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.models import AIReview, Commit, Severity
from app.services.llm import OllamaClient, OllamaUnavailable, get_ollama

logger = get_logger("reviewer")

MAX_DIFF_CHARS = 14000

REVIEW_SYSTEM_PROMPT = """You are a meticulous senior code reviewer performing a \
pull-request review. You are direct, specific and never invent problems.

You must output ONLY valid JSON — no prose, no markdown fences.

Return a JSON array of review comments. Each element must be an object with:
  "file_path":  string  – the file the comment applies to (from the diff)
  "line_number": integer – the line number in the NEW file (the `+` side), or null
  "severity":   string  – exactly one of "Bug", "Security", "Style", "Suggestion"
  "title":      string  – max 80 chars, e.g. "SQL injection via f-string"
  "comment":    string  – 1-4 sentences: what is wrong and how to fix it

Severity guide:
  "Bug"        – logic errors, off-by-one, null dereference, resource leaks, wrong results
  "Security"   – injection, hardcoded secrets, missing authz, unsafe deserialisation, XSS
  "Style"      – naming, dead code, duplicated logic, missing type hints, formatting
  "Suggestion" – genuinely useful improvements (performance, readability, tests)

Rules:
  * Only comment on lines that actually appear in the diff (added `+` lines).
  * Do not comment on purely trivial whitespace.
  * Never repeat the same comment for multiple lines.
  * If the diff is clean, return [].
  * Maximum 12 comments, ordered by severity (Security and Bug first).
"""

REVIEW_USER_TEMPLATE = """Repository: {repo_name}
Commit: {commit_hash}
Commit message: {message}

File-level summary of the diff:
{file_summary}

--- BEGIN DIFF ---
{diff}
--- END DIFF ---

Review the diff and return the JSON array of comments.
"""


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
_SEVERITY_ALIASES: dict[str, Severity] = {
    "bug": Severity.BUG,
    "error": Severity.BUG,
    "defect": Severity.BUG,
    "correctness": Severity.BUG,
    "critical": Severity.BUG,
    "security": Severity.SECURITY,
    "vulnerability": Severity.SECURITY,
    "insecure": Severity.SECURITY,
    "cwe": Severity.SECURITY,
    "style": Severity.STYLE,
    "formatting": Severity.STYLE,
    "lint": Severity.STYLE,
    "nit": Severity.STYLE,
    "suggestion": Severity.SUGGESTION,
    "improvement": Severity.SUGGESTION,
    "performance": Severity.SUGGESTION,
    "refactor": Severity.SUGGESTION,
    "info": Severity.SUGGESTION,
}

_SEVERITY_ORDER = {
    Severity.SECURITY.value: 0,
    Severity.BUG.value: 1,
    Severity.STYLE.value: 2,
    Severity.SUGGESTION.value: 3,
}


def normalise_severity(raw: Any) -> Severity:
    """Map whatever the model wrote onto our enum (default: Suggestion)."""
    if isinstance(raw, Severity):
        return raw
    text = str(raw or "").strip().lower()
    if text in _SEVERITY_ALIASES:
        return _SEVERITY_ALIASES[text]
    for key, value in _SEVERITY_ALIASES.items():
        if key in text:
            return value
    # Accept the exact enum values too ("Bug", "Security", …).
    for member in Severity:
        if member.value.lower() == text:
            return member
    return Severity.SUGGESTION


def split_diff_by_file(diff: str) -> dict[str, str]:
    """Split a concatenated unified diff into ``{file_path: diff_text}``."""
    sections: dict[str, list[str]] = {}
    current: str | None = None

    for line in diff.splitlines(keepends=True):
        if line.startswith("diff --git "):
            match = re.match(r"diff --git a/(.*?) b/(.*)", line.strip())
            current = (match.group(2).strip() if match else line.strip())
            sections[current] = [line]
        elif current is not None:
            sections[current].append(line)

    return {path: "".join(parts) for path, parts in sections.items()}


def _file_summary(diff: str) -> str:
    """Compact per-file +/- statistics fed to the model as orientation."""
    lines: list[str] = []
    for path, text in split_diff_by_file(diff).items():
        additions = sum(1 for l in text.splitlines() if l.startswith("+") and not l.startswith("+++"))
        deletions = sum(1 for l in text.splitlines() if l.startswith("-") and not l.startswith("---"))
        lines.append(f"  - {path}: +{additions} / -{deletions}")
    return "\n".join(lines) or "  (no file sections detected)"


def _truncate_diff(diff: str, limit: int = MAX_DIFF_CHARS) -> tuple[str, bool]:
    """Keep the head of an oversized diff, noting the truncation."""
    if len(diff) <= limit:
        return diff, False
    kept = diff[:limit]
    # Cut at the last complete diff hunk to avoid a half-line.
    cut = kept.rfind("\ndiff --git ")
    if cut > limit // 2:
        kept = kept[:cut]
    return kept + "\n... [diff truncated for review]\n", True


def _coerce_comment(raw: Any) -> dict[str, Any] | None:
    """Validate and normalise one raw comment from the model."""
    if not isinstance(raw, dict):
        return None

    text = (
        raw.get("comment")
        or raw.get("review_text")
        or raw.get("message")
        or raw.get("description")
        or ""
    )
    text = str(text).strip()
    if not text:
        return None

    line_number: int | None = None
    for key in ("line_number", "line", "start_line"):
        value = raw.get(key)
        if value is None:
            continue
        try:
            line_number = int(value)
            break
        except (TypeError, ValueError):
            continue
    if line_number is not None and line_number <= 0:
        line_number = None

    title = raw.get("title") or raw.get("summary")
    title = str(title).strip()[:200] if title else None

    file_path = raw.get("file_path") or raw.get("file") or raw.get("path")
    file_path = str(file_path).strip()[:1024] if file_path else None

    return {
        "review_text": text,
        "line_number": line_number,
        "severity": normalise_severity(raw.get("severity") or raw.get("type")),
        "title": title,
        "file_path": file_path,
    }


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def review_diff(
    diff: str,
    *,
    repo_name: str,
    commit_hash: str,
    message: str,
    llm: OllamaClient | None = None,
) -> list[dict[str, Any]]:
    """Ask Llama 3.2 to review a diff; returns normalised comment dicts."""
    if not diff.strip():
        return []

    llm = llm or get_ollama()
    truncated_diff, was_truncated = _truncate_diff(diff)
    if was_truncated:
        logger.info("Diff truncated to %d chars for review", len(truncated_diff))

    prompt = REVIEW_USER_TEMPLATE.format(
        repo_name=repo_name,
        commit_hash=commit_hash[:12],
        message=message,
        file_summary=_file_summary(diff),
        diff=truncated_diff,
    )

    payload = llm.chat_json(
        [{"role": "user", "content": prompt}],
        system=REVIEW_SYSTEM_PROMPT,
        temperature=0.1,
        max_tokens=2000,
    )

    if isinstance(payload, dict):
        # Some models wrap the array: {"comments": [...]}.
        payload = payload.get("comments") or payload.get("reviews") or payload.get("results") or []
    if not isinstance(payload, list):
        logger.warning("Reviewer returned an unexpected payload type: %s", type(payload))
        return []

    comments: list[dict[str, Any]] = []
    seen: set[tuple[str, int | None, str]] = set()
    valid_paths = set(split_diff_by_file(diff))

    for raw in payload:
        comment = _coerce_comment(raw)
        if comment is None:
            continue

        # Guard against hallucinated file paths.
        if comment["file_path"] and valid_paths and comment["file_path"] not in valid_paths:
            match = next((p for p in valid_paths if p.endswith(comment["file_path"])), None)
            comment["file_path"] = match

        key = (comment["file_path"] or "", comment["line_number"], comment["review_text"][:60])
        if key in seen:
            continue
        seen.add(key)
        comments.append(comment)

    comments.sort(
        key=lambda c: (
            _SEVERITY_ORDER.get(c["severity"].value, 9),
            c["line_number"] if c["line_number"] is not None else 10**9,
        )
    )
    return comments[:12]


def review_commit(
    db: Session,
    commit: Commit,
    *,
    llm: OllamaClient | None = None,
    force: bool = False,
) -> list[AIReview]:
    """
    Review a commit and persist the comments.

    Failures are recorded on the commit (``ai_review_error``) rather than
    raised, so a flaky Ollama never breaks the push flow.
    """
    if commit.ai_reviewed and not force:
        return list(commit.reviews)

    repo = commit.repository
    repo_name = f"{repo.owner.username}/{repo.name}" if repo and repo.owner else "repository"

    try:
        comments = review_diff(
            commit.diff or "",
            repo_name=repo_name,
            commit_hash=commit.commit_hash,
            message=commit.message,
            llm=llm,
        )
    except (OllamaUnavailable, Exception) as exc:  # noqa: B014
        message = str(exc)[:500]
        logger.warning("AI review failed for %s: %s", commit.short_hash, message)
        commit.ai_reviewed = False
        commit.ai_review_error = message
        db.commit()
        return []

    # Replace any previous review for this commit.
    db.execute(delete(AIReview).where(AIReview.commit_id == commit.id))

    rows: list[AIReview] = []
    for comment in comments:
        row = AIReview(
            id=uuid.uuid4(),
            commit_id=commit.id,
            review_text=comment["review_text"],
            line_number=comment["line_number"],
            file_path=comment["file_path"],
            severity=comment["severity"],
            title=comment["title"],
        )
        db.add(row)
        rows.append(row)

    commit.ai_reviewed = True
    commit.ai_review_error = None
    db.commit()

    logger.info("AI review stored %d comments for %s", len(rows), commit.short_hash)
    return rows


def review_commit_by_id(db: Session, commit_id: uuid.UUID, *, force: bool = False) -> list[AIReview]:
    """Convenience wrapper used by the background task runner."""
    commit = db.get(Commit, commit_id)
    if commit is None:
        return []
    return review_commit(db, commit, force=force)


__all__ = [
    "REVIEW_SYSTEM_PROMPT",
    "normalise_severity",
    "review_commit",
    "review_commit_by_id",
    "review_diff",
    "split_diff_by_file",
]
