"""
GitFolio — central application configuration.

Every tunable lives here and is populated from environment variables (or a
local ``.env`` file).  We never read ``os.environ`` anywhere else in the
codebase, which makes the whole stack testable and 12-factor friendly.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed, validated application settings."""

    model_config = SettingsConfigDict(
        # ``backend/.env`` when running locally, ``.env`` when running in Docker.
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ------------------------------------------------------------------ #
    # General
    # ------------------------------------------------------------------ #
    APP_NAME: str = "GitFolio API"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = Field(default="development", pattern="^(development|staging|production)$")
    DEBUG: bool = True
    API_PREFIX: str = "/api"

    # Comma separated list of allowed browser origins.
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # ------------------------------------------------------------------ #
    # Database
    # ------------------------------------------------------------------ #
    DATABASE_URL: str = "postgresql+psycopg://gitfolio:gitfolio@localhost:5432/gitfolio"
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE_SECONDS: int = 1800

    # ------------------------------------------------------------------ #
    # Auth
    # ------------------------------------------------------------------ #
    JWT_SECRET: str = "dev-only-secret-change-me-in-production-0123456789abcdef"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # one week

    # ------------------------------------------------------------------ #
    # Ollama (local Llama 3.2)
    # ------------------------------------------------------------------ #
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_CHAT_MODEL: str = "llama3.2"
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"
    OLLAMA_TIMEOUT_SECONDS: float = 180.0
    OLLAMA_KEEP_ALIVE: str = "10m"
    # When the AI stack is unreachable we degrade gracefully instead of 500ing.
    AI_ENABLED: bool = True

    # ------------------------------------------------------------------ #
    # ChromaDB (vector store)
    # ------------------------------------------------------------------ #
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000
    CHROMA_SSL: bool = False
    CHROMA_AUTH_TOKEN: str | None = None
    CHROMA_ENABLED: bool = True

    # ------------------------------------------------------------------ #
    # Retrieval / RAG tuning
    # ------------------------------------------------------------------ #
    RAG_TOP_K: int = 5
    RAG_MAX_CONTEXT_CHARS: int = 14000
    CHUNK_MAX_LINES: int = 120
    CHUNK_MIN_LINES: int = 3
    EMBED_BATCH_SIZE: int = 32

    # ------------------------------------------------------------------ #
    # Storage (bare Git object databases live on disk)
    # ------------------------------------------------------------------ #
    STORAGE_PATH: Path = Path("/data/repos")
    MAX_FILE_BYTES: int = 512 * 1024  # 512 KB per file
    MAX_PUSH_FILES: int = 2000
    IGNORED_PATHS: str = (
        ".git/,node_modules/,dist/,build/,.next/,__pycache__/,.venv/,venv/,"
        ".mypy_cache/,.pytest_cache/,coverage/,*.min.js,*.lock,*.png,*.jpg,"
        "*.jpeg,*.gif,*.ico,*.pdf,*.zip,*.tar,*.gz,*.woff,*.woff2,*.ttf"
    )

    # Run the AI pipeline (reviews, skills, ingestion) after every push.
    ENABLE_BACKGROUND_AI: bool = True

    # Create tables from the ORM metadata on startup (dev / first boot).
    # Set to false in production only if you manage the schema yourself; no
    # Alembic migration set is bundled yet.
    AUTO_CREATE_TABLES: bool = True

    # ------------------------------------------------------------------ #
    # Derived helpers
    # ------------------------------------------------------------------ #
    @property
    def cors_origins(self) -> list[str]:
        """``BACKEND_CORS_ORIGINS`` as a clean list of origins."""
        return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def ignored_patterns(self) -> list[str]:
        """``IGNORED_PATHS`` as a clean list of glob-ish patterns."""
        return [p.strip() for p in self.IGNORED_PATHS.split(",") if p.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def repos_root(self) -> Path:
        """Directory holding one Git object database per repository."""
        return Path(self.STORAGE_PATH)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance (import-safe singleton)."""
    return Settings()


settings = get_settings()
