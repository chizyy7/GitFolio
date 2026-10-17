"""
GitFolio API — application entry point.

Run locally::

    uvicorn app.main:app --reload --port 8000

Run in production (Docker)::

    gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 4 -b 0.0.0.0:8000
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, ORJSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.session import check_database_connection, engine

configure_logging()
logger = get_logger("main")


# --------------------------------------------------------------------------- #
# Lifespan
# --------------------------------------------------------------------------- #
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown hooks."""
    logger.info("=" * 78)
    logger.info("  %s v%s  [%s]", settings.APP_NAME, settings.APP_VERSION, settings.ENVIRONMENT)
    logger.info("  docs:      %s/docs", "http://localhost:8000")
    logger.info("  database:  %s", _redact(settings.DATABASE_URL))
    logger.info("  ollama:    %s (%s)", settings.OLLAMA_HOST, settings.OLLAMA_CHAT_MODEL)
    logger.info("  chroma:    %s:%s", settings.CHROMA_HOST, settings.CHROMA_PORT)
    logger.info("  storage:   %s", settings.STORAGE_PATH)
    logger.info("=" * 78)

    # Ensure the Git object-store root exists.
    settings.repos_root.mkdir(parents=True, exist_ok=True)

    if settings.AUTO_CREATE_TABLES:
        try:
            from app.db.base import Base  # noqa: F401  (registers all models)

            Base.metadata.create_all(bind=engine)
            logger.info("Database schema is up to date.")
        except SQLAlchemyError as exc:
            logger.error("Could not create database schema: %s", exc)
    else:
        logger.info("AUTO_CREATE_TABLES=false — expecting an externally managed schema.")

    if not check_database_connection():
        logger.warning("Database is unreachable at startup; /health/ready will report degraded.")

    yield

    logger.info("Shutting down %s.", settings.APP_NAME)


def _redact(url: str) -> str:
    """Hide the password in a database URL before logging it."""
    if "@" not in url:
        return url
    scheme, rest = url.split("://", 1) if "://" in url else ("", url)
    credentials, host = rest.rsplit("@", 1)
    user = credentials.split(":", 1)[0]
    return f"{scheme}://{user}:***@{host}"


# --------------------------------------------------------------------------- #
# App factory
# --------------------------------------------------------------------------- #
def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "**GitFolio** — a self-hosted, AI-powered version control and portfolio "
            "platform.\n\nReal Git object storage (`pygit2`), a local RAG pipeline "
            "over your own code (Ollama + Llama 3.2 + ChromaDB), AI code review, "
            "semantic code search and an AI skill mapper."
        ),
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        contact={"name": "GitFolio", "url": "https://github.com/gitfolio"},
        license_info={"name": "MIT"},
    )

    # ---------------------------------------------------------------- CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Process-Time", "Content-Disposition"],
        max_age=600,
    )

    # ------------------------------------------------------------ middleware
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        """Expose request duration for the frontend's dev overlay."""
        import time

        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Process-Time"] = f"{(time.perf_counter() - started) * 1000:.1f}"
        return response

    # ------------------------------------------------------ error handlers
    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_request: Request, exc: RequestValidationError):
        """Flatten Pydantic errors into a small, frontend-friendly shape."""
        problems = [
            {
                "field": ".".join(str(part) for part in error.get("loc", [])[1:]) or "body",
                "message": error.get("msg", "Invalid value"),
                "type": error.get("type", "value_error"),
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": "Request validation failed.", "errors": problems},
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error_handler(_request: Request, exc: SQLAlchemyError):
        """Never leak SQL to clients; log it and return a generic 500."""
        logger.exception("Database error: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "A database error occurred. Please try again."},
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(_request: Request, exc: ValueError):
        """Domain-level validation errors become 400s."""
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)},
        )

    # ------------------------------------------------------------- routers
    app.include_router(api_router, prefix=settings.API_PREFIX)

    @app.get("/", tags=["System"], summary="API index")
    def root() -> dict[str, object]:
        """Human-readable index of the API surface."""
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "docs": "/docs",
            "health": f"{settings.API_PREFIX}/health",
            "endpoints": {
                "auth": [
                    f"POST {settings.API_PREFIX}/auth/register",
                    f"POST {settings.API_PREFIX}/auth/login",
                    f"GET  {settings.API_PREFIX}/auth/me",
                ],
                "repositories": [
                    f"POST   {settings.API_PREFIX}/repos",
                    f"GET    {settings.API_PREFIX}/repos/{{username}}",
                    f"GET    {settings.API_PREFIX}/repos/{{username}}/{{repo_name}}",
                ],
                "version_control": [
                    f"POST {settings.API_PREFIX}/repos/{{repo_id}}/push",
                    f"GET  {settings.API_PREFIX}/repos/{{repo_id}}/commits",
                    f"GET  {settings.API_PREFIX}/repos/{{repo_id}}/commits/{{commit_hash}}",
                ],
                "ai": [
                    f"POST {settings.API_PREFIX}/ai/chat",
                    f"POST {settings.API_PREFIX}/ai/search",
                    f"GET  {settings.API_PREFIX}/ai/reviews/{{commit_id}}",
                    f"POST {settings.API_PREFIX}/ai/skills/refresh",
                    f"GET  {settings.API_PREFIX}/ai/health",
                ],
                "dashboard": [f"GET {settings.API_PREFIX}/dashboard/{{username}}"],
            },
        }

    return app


app = create_app()


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
    )
