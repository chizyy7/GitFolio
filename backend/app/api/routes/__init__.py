"""Route modules, aggregated into a single router for ``main.py``."""

from fastapi import APIRouter

from app.api.routes import ai, auth, dashboard, profiles, repos, system, vcs
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(auth.router)
api_router.include_router(profiles.router)
api_router.include_router(repos.router)
api_router.include_router(vcs.router)
api_router.include_router(ai.router)
api_router.include_router(dashboard.router)

__all__ = ["ai", "api_router", "auth", "dashboard", "profiles", "repos", "system", "vcs"]
