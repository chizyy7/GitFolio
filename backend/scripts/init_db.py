"""
Database bootstrap + demo-data seeder.

Usage::

    python -m scripts.init_db              # create tables only
    python -m scripts.init_db --seed       # create tables + demo data
    python -m scripts.init_db --drop       # drop everything first (destructive!)
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Allow ``python -m scripts.init_db`` from the ``backend/`` directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.logging import configure_logging, get_logger  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.models import Repository, User  # noqa: E402

logger = get_logger("init_db")

DEMO_USERNAME = "demo"
DEMO_EMAIL = "demo@gitfolio.dev"
DEMO_PASSWORD = "demo-password-123"


def create_schema(drop: bool = False) -> None:
    """Create (or recreate) every table."""
    if drop:
        logger.warning("Dropping all tables…")
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    logger.info("Schema ready: %s", ", ".join(sorted(Base.metadata.tables)))


def seed() -> None:
    """Create a demo account with a couple of empty repositories."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == DEMO_USERNAME).one_or_none()
        if user is None:
            user = User(
                username=DEMO_USERNAME,
                email=DEMO_EMAIL,
                hashed_password=hash_password(DEMO_PASSWORD),
                display_name="Demo Developer",
                bio="Demo account for GitFolio. Push some code and ask the AI about it!",
                location="Remote",
                avatar_url=f"https://api.dicebear.com/7.x/identicon/svg?seed={DEMO_USERNAME}",
            )
            db.add(user)
            db.flush()
            logger.info("Created demo user @%s (password: %s)", DEMO_USERNAME, DEMO_PASSWORD)

        for name, description, language in (
            ("gitfolio-demo", "A sandbox repository for trying the AI reviewer.", "Python"),
            ("portfolio-site", "Personal site built with Next.js and Tailwind.", "TypeScript"),
        ):
            exists = (
                db.query(Repository)
                .filter(Repository.user_id == user.id, Repository.name == name)
                .one_or_none()
            )
            if exists is None:
                db.add(
                    Repository(
                        user_id=user.id,
                        name=name,
                        description=description,
                        primary_language=language,
                        topics="demo,gitfolio",
                        is_pinned=True,
                        created_at=datetime.now(timezone.utc) - timedelta(days=30),
                    )
                )
                logger.info("Created repository %s/%s", DEMO_USERNAME, name)

        db.commit()
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialise the GitFolio database.")
    parser.add_argument("--seed", action="store_true", help="insert demo data")
    parser.add_argument("--drop", action="store_true", help="drop all tables first")
    args = parser.parse_args()

    configure_logging()
    create_schema(drop=args.drop)
    if args.seed:
        seed()
    logger.info("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
