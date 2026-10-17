"""System routes: liveness, readiness and a machine-readable API index."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.db.session import check_database_connection

router = APIRouter(tags=["System"])


@router.get("/health", summary="Liveness probe")
def health() -> dict[str, object]:
    """Cheap liveness check (no dependencies touched)."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


@router.get("/health/ready", summary="Readiness probe")
def readiness() -> dict[str, object]:
    """
    Readiness check: verifies the database, and reports (without failing) the
    optional AI dependencies.
    """
    database_ok = check_database_connection()
    return {
        "status": "ready" if database_ok else "degraded",
        "checks": {
            "database": database_ok,
            "ai_enabled": settings.AI_ENABLED,
            "chroma_enabled": settings.CHROMA_ENABLED,
        },
    }


__all__ = ["router"]
