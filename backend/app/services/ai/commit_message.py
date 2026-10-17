"""
Auto-Commit Message Generator.

When a push arrives without a commit message we ask Llama 3.2 to write a
Conventional-Commits style summary from the diff.  If the model is unreachable
we fall back to a deterministic heuristic so a push is never blocked.
"""

from __future__ import annotations

import re

from app.core.logging import get_logger
from app.services.ai.reviewer import split_diff_by_file
from app.services.llm import OllamaClient, OllamaUnavailable, get_ollama
from app.services.language import detect_language

logger = get_logger("commit_message")

MAX_DIFF_CHARS = 8000

COMMIT_SYSTEM_PROMPT = """You write Git commit messages.

Rules:
1. Output ONLY the commit message. No quotes, no markdown, no explanation.
2. First line: a Conventional Commits subject, max 72 characters.
   Format: <type>(<optional scope>): <imperative summary>
   Allowed types: feat, fix, refactor, perf, docs, style, test, build, ci, chore.
3. Then one blank line, then up to 3 bullet points describing the *why* of the change.
4. Use the imperative mood ("add", "fix", "remove"), never past tense.
5. Never mention "the diff", "snippets" or that you are an AI.
"""

COMMIT_USER_TEMPLATE = """Files changed:
{file_summary}

--- BEGIN DIFF ---
{diff}
--- END DIFF ---

Write the commit message.
"""

# Very common path -> scope mappings (used by the heuristic fallback).
_SCOPE_HINTS = ("api", "auth", "ui", "frontend", "backend", "db", "tests", "docs", "config", "ai")

_TYPE_ORDER = ("feat", "fix", "refactor", "docs", "test", "chore")


def _sanitise(message: str) -> str:
    """Strip fences/quotes and enforce a sane subject length."""
    text = message.strip()
    text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
    text = text.replace("```", "").strip()
    text = text.strip("\"'` \n")

    lines = [line.rstrip() for line in text.splitlines()]
    # Drop leading boilerplate like "Commit message:".
    while lines and re.match(r"^(commit message|message|output)\s*:?\s*$", lines[0], re.IGNORECASE):
        lines.pop(0)
    lines = [l for l in lines]

    if not lines:
        return ""

    # Enforce the 72-char subject.
    subject = lines[0]
    if len(subject) > 72:
        subject = subject[:69].rstrip() + "..."

    body = "\n".join(lines[1:]).strip()
    body = re.sub(r"\n{3,}", "\n\n", body)
    return f"{subject}\n\n{body}".strip()


def _heuristic_message(diff: str) -> str:
    """
    Deterministic fallback: derive type + scope from the changed paths and the
    +/- balance.  Never crashes, always produces something sensible.
    """
    sections = split_diff_by_file(diff)
    paths = list(sections.keys()) or ["files"]

    additions = sum(1 for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++"))
    deletions = sum(1 for l in diff.splitlines() if l.startswith("-") and not l.startswith("---"))

    # Type inference.
    lowered = diff.lower()
    if any(token in lowered for token in ("def test_", "it(", "describe(", "@pytest")):
        change_type = "test"
    elif additions and deletions and additions > deletions * 3:
        change_type = "feat"
    elif deletions > additions * 2:
        change_type = "refactor"
    elif any(path.lower().endswith((".md", ".rst", ".txt")) for path in paths):
        change_type = "docs"
    elif additions <= 5 and deletions <= 5:
        change_type = "fix"
    else:
        change_type = "chore"

    # Scope inference from the first path segment that looks meaningful.
    scope = None
    for path in paths:
        parts = path.split("/")
        for part in parts[:-1]:
            if part.lower() in _SCOPE_HINTS:
                scope = part.lower()
                break
        if scope:
            break
    if scope is None and len(paths) == 1:
        language = detect_language(paths[0])
        if language:
            scope = language.lower()

    head = f"{change_type}({scope})" if scope else change_type

    if len(paths) == 1:
        subject = f"{head}: update {paths[0]}"
    else:
        subject = f"{head}: update {len(paths)} files"

    if len(subject) > 72:
        subject = subject[:69].rstrip() + "..."

    bullets = [
        f"- {path} (+{sum(1 for l in text.splitlines() if l.startswith('+') and not l.startswith('+++'))}"
        f"/-{sum(1 for l in text.splitlines() if l.startswith('-') and not l.startswith('---'))})"
        for path, text in list(sections.items())[:3]
    ]
    body = "\n".join(bullets) if bullets else ""
    return f"{subject}\n\n{body}".strip()


def generate_commit_message(
    diff: str,
    *,
    files_changed: int = 0,
    additions: int = 0,
    deletions: int = 0,
    llm: OllamaClient | None = None,
) -> str:
    """
    Produce a commit message for ``diff``.

    Always returns a non-empty string; falls back to the heuristic when the
    LLM is unavailable or returns something unusable.
    """
    if not diff.strip():
        return "chore: empty commit"

    try:
        llm = llm or get_ollama()
        sections = split_diff_by_file(diff)
        summary_lines = []
        for path, text in sections.items():
            adds = sum(1 for l in text.splitlines() if l.startswith("+") and not l.startswith("+++"))
            dels = sum(1 for l in text.splitlines() if l.startswith("-") and not l.startswith("---"))
            summary_lines.append(f"  - {path}: +{adds} / -{dels}")
        summary = "\n".join(summary_lines) or f"  - {files_changed} files (+{additions}/-{deletions})"

        prompt = COMMIT_USER_TEMPLATE.format(
            file_summary=summary, diff=diff[:MAX_DIFF_CHARS]
        )
        raw = llm.chat(
            [{"role": "user", "content": prompt}],
            system=COMMIT_SYSTEM_PROMPT,
            temperature=0.2,
            max_tokens=260,
        )
        message = _sanitise(raw)
        if message:
            return message
        logger.debug("LLM returned an empty commit message; using heuristic")
    except (OllamaUnavailable, Exception) as exc:  # noqa: B014
        logger.warning("Auto-commit message generation failed (%s); using heuristic", exc)

    return _heuristic_message(diff)


def is_conventional(message: str) -> bool:
    """True when ``message`` already looks like a Conventional Commit."""
    return bool(re.match(r"^(" + "|".join(_TYPE_ORDER) + r")(\([^)]+\))?!?:\s+\S", message.strip()))


__all__ = ["generate_commit_message", "is_conventional"]
