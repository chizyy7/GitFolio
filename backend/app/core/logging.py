"""Uniform logging configuration for the API and the background AI workers."""

from __future__ import annotations

import logging
import sys

from app.core.config import settings

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-32s | %(message)s"


def configure_logging() -> None:
    """Configure the root logger exactly once per process."""
    root = logging.getLogger()
    if getattr(root, "_gitfolio_configured", False):
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S"))

    root.handlers = [handler]
    root.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    # Trim the noisiest third-party loggers.
    for noisy in ("httpcore", "httpx", "urllib3", "chromadb", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    root._gitfolio_configured = True  # type: ignore[attr-defined]


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger."""
    return logging.getLogger(f"gitfolio.{name}")
