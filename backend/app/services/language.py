"""
Language detection + binary sniffing helpers.

Used by the VCS engine (to tag blobs), the ingestion pipeline (to pick a
tree-sitter grammar) and the API (to render language dots / syntax modes).
"""

from __future__ import annotations

import os
from pathlib import PurePosixPath

# --------------------------------------------------------------------------- #
# extension -> display language
# --------------------------------------------------------------------------- #
LANGUAGE_BY_EXTENSION: dict[str, str] = {
    # Python
    ".py": "Python",
    ".pyi": "Python",
    ".ipynb": "Jupyter Notebook",
    # JavaScript / TypeScript
    ".js": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    # Web
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "SCSS",
    ".less": "Less",
    ".vue": "Vue",
    ".svelte": "Svelte",
    # Systems
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hpp": "C++",
    ".cs": "C#",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".go": "Go",
    ".rs": "Rust",
    ".swift": "Swift",
    ".m": "Objective-C",
    ".php": "PHP",
    ".rb": "Ruby",
    ".scala": "Scala",
    ".dart": "Dart",
    ".lua": "Lua",
    ".pl": "Perl",
    ".r": "R",
    ".jl": "Julia",
    # Data / config / infra
    ".sql": "SQL",
    ".json": "JSON",
    ".jsonc": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".ini": "INI",
    ".cfg": "INI",
    ".env": "Dotenv",
    ".xml": "XML",
    ".md": "Markdown",
    ".mdx": "Markdown",
    ".rst": "reStructuredText",
    ".txt": "Text",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".ps1": "PowerShell",
    ".bat": "Batchfile",
    ".dockerfile": "Dockerfile",
    ".tf": "HCL",
    ".proto": "Protocol Buffer",
    ".graphql": "GraphQL",
    ".gql": "GraphQL",
    ".tex": "TeX",
}

# Exact filenames (no extension) -> language
LANGUAGE_BY_FILENAME: dict[str, str] = {
    "dockerfile": "Dockerfile",
    "makefile": "Makefile",
    "rakefile": "Ruby",
    "gemfile": "Ruby",
    "procfile": "Procfile",
    ".gitignore": "Git Config",
    ".gitattributes": "Git Config",
    ".dockerignore": "Git Config",
    ".editorconfig": "EditorConfig",
    "requirements.txt": "Text",
    "package-lock.json": "JSON",
    "alembic.ini": "INI",
    "cargo.toml": "TOML",
    "pyproject.toml": "TOML",
    "go.mod": "Go",
    "nginx.conf": "Nginx",
}

# Colours for the GitHub-style language dots on the frontend.
LANGUAGE_COLORS: dict[str, str] = {
    "Python": "#3572A5",
    "TypeScript": "#3178c6",
    "JavaScript": "#f1e05a",
    "TSX": "#3178c6",
    "JSX": "#f1e05a",
    "HTML": "#e34c26",
    "CSS": "#563d7c",
    "SCSS": "#c6538c",
    "Vue": "#41b883",
    "Svelte": "#ff3e00",
    "C": "#555555",
    "C++": "#f34b7d",
    "C#": "#178600",
    "Java": "#b07219",
    "Kotlin": "#A97BFF",
    "Go": "#00ADD8",
    "Rust": "#dea584",
    "Swift": "#F05138",
    "PHP": "#4F5D95",
    "Ruby": "#701516",
    "Scala": "#c22d40",
    "Dart": "#00B4AB",
    "Lua": "#000080",
    "R": "#198CE7",
    "Julia": "#a270ba",
    "SQL": "#e38c00",
    "Shell": "#89e051",
    "PowerShell": "#012456",
    "Dockerfile": "#384d54",
    "Makefile": "#427819",
    "Markdown": "#083fa1",
    "JSON": "#292929",
    "YAML": "#cb171e",
    "TOML": "#9c4221",
    "Jupyter Notebook": "#DA5B0B",
    "Text": "#6b7280",
}

# Extensions we treat as definitely binary (never embedded / diffed as text).
BINARY_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".tiff", ".svgz",
        ".pdf", ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar", ".xz",
        ".mp3", ".mp4", ".wav", ".ogg", ".webm", ".mov", ".avi", ".mkv",
        ".woff", ".woff2", ".ttf", ".otf", ".eot",
        ".exe", ".dll", ".so", ".dylib", ".bin", ".class", ".jar", ".pyc", ".wasm",
        ".db", ".sqlite", ".sqlite3", ".pkl", ".pt", ".onnx", ".h5", ".parquet",
    }
)

# Files that are pure noise for the AI pipeline and semantic search.
NOISE_FILENAMES: frozenset[str] = frozenset(
    {
        "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
        "Pipfile.lock", "composer.lock", "Cargo.lock", "Gemfile.lock",
        "bun.lockb", "uv.lock",
    }
)

NOISE_SUFFIXES: tuple[str, ...] = (".min.js", ".min.css", ".map", ".chunk.js")


def detect_language(file_path: str) -> str | None:
    """Best-effort language name for a path (``None`` when unknown)."""
    name = PurePosixPath(file_path).name.lower()

    if name in LANGUAGE_BY_FILENAME:
        return LANGUAGE_BY_FILENAME[name]
    if name.startswith("dockerfile"):
        return "Dockerfile"
    if name.startswith(".env"):
        return "Dotenv"

    suffix = os.path.splitext(name)[1]
    if suffix in LANGUAGE_BY_EXTENSION:
        language = LANGUAGE_BY_EXTENSION[suffix]
        # Disambiguate TSX/JSX for the syntax highlighter.
        if suffix == ".tsx":
            return "TSX"
        if suffix == ".jsx":
            return "JSX"
        return language
    return None


def language_color(language: str | None) -> str:
    """Hex colour for the language dot on a repo card."""
    if not language:
        return "#8b949e"
    return LANGUAGE_COLORS.get(language, "#8b949e")


def is_binary_bytes(data: bytes) -> bool:
    """Heuristic binary detector (NUL byte or >30% non-text bytes)."""
    if not data:
        return False
    if b"\x00" in data[:8192]:
        return True
    sample = data[:8192]
    text_chars = bytes({7, 8, 9, 10, 11, 12, 13, 27} | set(range(0x20, 0x7F)) | set(range(0x80, 0x100)))
    non_text = sample.translate(None, text_chars)
    return len(non_text) / len(sample) > 0.30


def is_binary_path(file_path: str) -> bool:
    """Cheap path-based binary check (no I/O)."""
    suffix = os.path.splitext(file_path.lower())[1]
    return suffix in BINARY_EXTENSIONS


def is_indexable(file_path: str, size_bytes: int = 0) -> bool:
    """Should this file be sent to the embedding model?"""
    name = PurePosixPath(file_path).name
    if name in NOISE_FILENAMES:
        return False
    if file_path.lower().endswith(NOISE_SUFFIXES):
        return False
    if is_binary_path(file_path):
        return False
    if detect_language(file_path) is None and not file_path.lower().endswith(
        ("readme", "license", "makefile", "dockerfile")
    ):
        # Unknown language is usually fine as long as it is small plain text.
        return size_bytes < 64 * 1024
    return True
