"""
SQLAlchemy 2.0 engine / session factory.

A single ``Engine`` is created per process with a tuned connection pool.
``get_db`` is the FastAPI dependency used by every route.
"""

from __future__ import annotations

from collections.abc import Generator, Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("db")

# ``pool_pre_ping`` recycles connections dropped by the database/proxy;
# essential for Render/Railway where idle connections are culled.
_engine_kwargs: dict = {
    "pool_pre_ping": True,
    "pool_recycle": settings.DB_POOL_RECYCLE_SECONDS,
    "echo": settings.DB_ECHO,
    "future": True,
}

# SQLite (used by the test-suite) does not support pool sizing arguments.
if not settings.DATABASE_URL.startswith("sqlite"):
    _engine_kwargs.update(
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
    )
else:
    _engine_kwargs.update(connect_args={"check_same_thread": False})

engine: Engine = create_engine(settings.DATABASE_URL, **_engine_kwargs)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a request-scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope for background tasks / scripts."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_database_connection() -> bool:
    """Return ``True`` when the database answers a trivial query."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # pragma: no cover - infrastructure dependent
        logger.warning("Database connectivity check failed: %s", exc)
        return False
