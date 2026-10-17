"""
AI Skill Mapper.

Looks at the whole account (file extensions, dependency manifests, config
files) and asks Llama 3.2 to produce a structured skill profile which is then
rendered as badges on the developer's profile page.
"""

from __future__ import annotations

import json
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import File, Proficiency, Repository, User, UserSkill
from app.schemas.skill import AISkillProfile
from app.services.language import detect_language
from app.services.llm import OllamaClient, OllamaUnavailable, get_ollama

logger = get_logger("skills")

# Manifest files whose contents reveal frameworks/tooling.
MANIFEST_FILES = {
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "Pipfile",
    "setup.py",
    "go.mod",
    "Cargo.toml",
    "pom.xml",
    "build.gradle",
    "Gemfile",
    "composer.json",
    "docker-compose.yml",
    "docker-compose.yaml",
    "Dockerfile",
    "vercel.json",
    "next.config.js",
    "next.config.mjs",
    "next.config.ts",
    "tsconfig.json",
    "tailwind.config.js",
    "tailwind.config.ts",
}

MANIFEST_CHAR_LIMIT = 2500
MAX_MANIFESTS = 12

SKILL_SYSTEM_PROMPT = """You are a technical recruiter analysing a developer's \
public repositories.

Output ONLY valid JSON matching exactly this shape:

{
  "languages":  ["Python", "TypeScript"],
  "frameworks": ["FastAPI", "Next.js", "React"],
  "tools":      ["Docker", "GitHub Actions", "Ollama"],
  "databases":  ["PostgreSQL", "ChromaDB"],
  "proficiency": "Intermediate",
  "summary": "One sentence describing this developer's focus."
}

Rules:
  * "proficiency" must be exactly one of: Beginner, Intermediate, Advanced.
    Judge it from the breadth AND depth of the evidence (variety of frameworks,
    database usage, tests, CI, deployment configs).
  * Only list a technology you actually see evidence for. No guessing.
  * Use canonical, human-readable names ("Next.js", not "next"; "PostgreSQL", not "postgres").
  * Between 1 and 8 entries per list. Deduplicate.
  * No prose outside the JSON object.
"""

SKILL_USER_TEMPLATE = """Analyse the evidence below and return the JSON skill profile.

=== REPOSITORIES ===
{repos}

=== FILE EXTENSION HISTOGRAM ===
{extensions}

=== DEPENDENCY MANIFEST EXCERPTS ===
{manifests}
"""


# --------------------------------------------------------------------------- #
# Evidence collection
# --------------------------------------------------------------------------- #
def collect_evidence(db: Session, user: User) -> dict[str, Any]:
    """Gather the raw signals used by the skill mapper."""
    repos = list(db.execute(select(Repository).where(Repository.user_id == user.id)).scalars())
    repo_ids = [r.id for r in repos]

    files: list[File] = []
    if repo_ids:
        files = list(db.execute(select(File).where(File.repo_id.in_(repo_ids))).scalars())

    extension_counter: Counter[str] = Counter()
    language_counter: Counter[str] = Counter()
    manifests: list[tuple[str, str]] = []

    for file_row in files:
        name = file_row.file_path.rsplit("/", 1)[-1]
        if "." in name:
            extension_counter["." + name.rsplit(".", 1)[-1].lower()] += 1
        else:
            extension_counter[name.lower()] += 1

        language = file_row.language or detect_language(file_row.file_path)
        if language and language not in ("Text", "Git Config"):
            language_counter[language] += 1

        if name in MANIFEST_FILES and file_row.content and len(manifests) < MAX_MANIFESTS:
            manifests.append(
                (f"{_repo_slug(repos, file_row.repo_id)}/{file_row.file_path}", file_row.content[:MANIFEST_CHAR_LIMIT])
            )

    return {
        "repos": repos,
        "repo_count": len(repos),
        "file_count": len(files),
        "extensions": extension_counter,
        "languages": language_counter,
        "manifests": manifests,
    }


def _repo_slug(repos: list[Repository], repo_id: uuid.UUID) -> str:
    for repo in repos:
        if repo.id == repo_id:
            return repo.name
    return "repo"


def _format_repos(repos: list[Repository]) -> str:
    if not repos:
        return "(none)"
    lines = []
    for repo in repos:
        topics = f" topics=[{', '.join(repo.topic_list)}]" if repo.topics else ""
        lines.append(
            f"- {repo.name}: {repo.description or 'no description'} "
            f"(language={repo.primary_language or 'unknown'}, commits={repo.commit_count}, "
            f"files={repo.file_count}){topics}"
        )
    return "\n".join(lines)


def _format_extensions(counter: Counter[str], limit: int = 25) -> str:
    if not counter:
        return "(none)"
    return ", ".join(f"{ext} x{count}" for ext, count in counter.most_common(limit))


def _format_manifests(manifests: list[tuple[str, str]]) -> str:
    if not manifests:
        return "(none found)"

    blocks = []
    for path, content in manifests:
        # Keep the signal dense: package.json/pyproject.toml are the richest.
        blocks.append(f"--- {path} ---\n{content}")
    return "\n\n".join(blocks)


# --------------------------------------------------------------------------- #
# Heuristic profile (no LLM required)
# --------------------------------------------------------------------------- #
_EXTENSION_SKILLS: dict[str, tuple[str, str]] = {
    ".py": ("Python", "language"),
    ".ts": ("TypeScript", "language"),
    ".tsx": ("React", "framework"),
    ".js": ("JavaScript", "language"),
    ".jsx": ("React", "framework"),
    ".java": ("Java", "language"),
    ".kt": ("Kotlin", "language"),
    ".go": ("Go", "language"),
    ".rs": ("Rust", "language"),
    ".rb": ("Ruby", "language"),
    ".php": ("PHP", "language"),
    ".cs": ("C#", "language"),
    ".c": ("C", "language"),
    ".cpp": ("C++", "language"),
    ".swift": ("Swift", "language"),
    ".sql": ("SQL", "database"),
    ".html": ("HTML", "language"),
    ".css": ("CSS", "language"),
    ".scss": ("SCSS", "language"),
    ".sh": ("Shell", "tool"),
    ".tf": ("Terraform", "tool"),
}

_MANIFEST_SKILLS: dict[str, tuple[str, str]] = {
    "fastapi": ("FastAPI", "framework"),
    "flask": ("Flask", "framework"),
    "django": ("Django", "framework"),
    "sqlalchemy": ("SQLAlchemy", "framework"),
    "pydantic": ("Pydantic", "framework"),
    "celery": ("Celery", "framework"),
    "pandas": ("pandas", "framework"),
    "numpy": ("NumPy", "framework"),
    "pytorch": ("PyTorch", "framework"),
    "torch": ("PyTorch", "framework"),
    "tensorflow": ("TensorFlow", "framework"),
    "scikit-learn": ("scikit-learn", "framework"),
    "streamlit": ("Streamlit", "framework"),
    "react": ("React", "framework"),
    "next": ("Next.js", "framework"),
    "vue": ("Vue", "framework"),
    "svelte": ("Svelte", "framework"),
    "express": ("Express", "framework"),
    "tailwindcss": ("Tailwind CSS", "framework"),
    "prisma": ("Prisma", "tool"),
    "chromadb": ("ChromaDB", "database"),
    "psycopg": ("PostgreSQL", "database"),
    "postgres": ("PostgreSQL", "database"),
    "sqlite": ("SQLite", "database"),
    "redis": ("Redis", "database"),
    "mongo": ("MongoDB", "database"),
    "mongoose": ("MongoDB", "database"),
    "docker": ("Docker", "tool"),
    "kubernetes": ("Kubernetes", "tool"),
    "ollama": ("Ollama", "tool"),
    "langchain": ("LangChain", "framework"),
    "llama-index": ("LlamaIndex", "framework"),
    "pytest": ("pytest", "tool"),
    "jest": ("Jest", "tool"),
    "vitest": ("Vitest", "tool"),
    "git": ("Git", "tool"),
}


def heuristic_profile(evidence: dict[str, Any]) -> AISkillProfile:
    """Build a skill profile without the LLM (also used to sanity-check output)."""
    languages: list[str] = []
    frameworks: list[str] = []
    tools: list[str] = []
    databases: list[str] = []

    def bucket(category: str) -> list[str]:
        return {
            "language": languages,
            "framework": frameworks,
            "tool": tools,
            "database": databases,
        }.get(category, tools)

    for ext, _count in evidence["extensions"].most_common(12):
        skill = _EXTENSION_SKILLS.get(ext)
        if skill:
            target = bucket(skill[1])
            if skill[0] not in target:
                target.append(skill[0])

    for slug, content in evidence["manifests"]:
        lowered = f"{slug}\n{content}".lower()
        for needle, (name, category) in _MANIFEST_SKILLS.items():
            if needle in lowered:
                target = bucket(category)
                if name not in target:
                    target.append(name)

    total_files = evidence["file_count"]
    proficiency = Proficiency.BEGINNER
    if total_files > 40 and len(languages) >= 3:
        proficiency = Proficiency.ADVANCED
    elif total_files > 8 or len(languages) >= 2:
        proficiency = Proficiency.INTERMEDIATE

    return AISkillProfile(
        languages=languages[:8],
        frameworks=frameworks[:8],
        tools=tools[:8],
        databases=databases[:8],
        proficiency=proficiency,
        summary=(
            f"{', '.join(languages[:3]) or 'Multi-language'} developer across "
            f"{evidence['repo_count']} repositories."
        ),
    )


# --------------------------------------------------------------------------- #
# LLM profile
# --------------------------------------------------------------------------- #
def generate_skill_profile(
    db: Session, user: User, *, llm: OllamaClient | None = None
) -> AISkillProfile:
    """Ask Llama 3.2 for a skill profile, falling back to the heuristic."""
    evidence = collect_evidence(db, user)
    baseline = heuristic_profile(evidence)

    if not evidence["repos"]:
        return baseline

    try:
        llm = llm or get_ollama()
        prompt = SKILL_USER_TEMPLATE.format(
            repos=_format_repos(evidence["repos"]),
            extensions=_format_extensions(evidence["extensions"]),
            manifests=_format_manifests(evidence["manifests"]),
        )
        payload = llm.chat_json(
            [{"role": "user", "content": prompt}],
            system=SKILL_SYSTEM_PROMPT,
            temperature=0.1,
            max_tokens=800,
        )
        if isinstance(payload, str):
            payload = json.loads(payload)
        if not isinstance(payload, dict):
            raise ValueError("Skill mapper did not return a JSON object")

        # Validate through Pydantic; missing keys default cleanly.
        profile = AISkillProfile.model_validate(payload)
        if not any([profile.languages, profile.frameworks, profile.tools, profile.databases]):
            logger.debug("LLM skill profile was empty; using heuristic")
            return baseline
        return profile
    except (OllamaUnavailable, Exception) as exc:  # noqa: B014
        logger.warning("Skill mapper fell back to heuristics: %s", exc)
        return baseline


def persist_skill_profile(db: Session, user: User, profile: AISkillProfile) -> list[UserSkill]:
    """Replace the user's stored skills with ``profile``."""
    db.execute(delete(UserSkill).where(UserSkill.user_id == user.id))

    rows: list[UserSkill] = []
    seen: set[str] = set()

    def add(items: list[str], category: str, confidence: int) -> None:
        for index, name in enumerate(items):
            cleaned = str(name).strip()
            if not cleaned or cleaned.lower() in seen:
                continue
            seen.add(cleaned.lower())
            rows.append(
                UserSkill(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    skill_name=cleaned[:80],
                    proficiency=profile.proficiency,
                    category=category,
                    confidence=max(10, confidence - index * 5),
                    evidence=profile.summary[:512] if profile.summary else None,
                )
            )

    add(profile.languages, "language", 95)
    add(profile.frameworks, "framework", 85)
    add(profile.tools, "tool", 75)
    add(profile.databases, "database", 70)

    db.add_all(rows)
    user.skills_analyzed_at = datetime.now(timezone.utc)
    db.commit()
    logger.info("Stored %d skill badges for @%s", len(rows), user.username)
    return rows


def refresh_user_skills(db: Session, user_id: uuid.UUID) -> list[UserSkill]:
    """Background-task entry point."""
    user = db.get(User, user_id)
    if user is None:
        return []
    return persist_skill_profile(db, user, generate_skill_profile(db, user))


def get_or_create_skills(db: Session, user: User) -> list[UserSkill]:
    """Return stored skills, generating them on first profile view."""
    if user.skills:
        return list(user.skills)
    if not user.skills_analyzed_at:
        return refresh_user_skills(db, user.id)
    return []


__all__ = [
    "collect_evidence",
    "generate_skill_profile",
    "get_or_create_skills",
    "heuristic_profile",
    "persist_skill_profile",
    "refresh_user_skills",
]
