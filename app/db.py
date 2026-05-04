from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Declarative base for all SQLAlchemy ORM models."""


settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional SQLAlchemy session."""

    session = SessionLocal()
    logger.debug("Database session opened")
    try:
        yield session
        session.commit()
        logger.debug("Database transaction committed")
    except Exception:
        session.rollback()
        logger.exception("Database transaction rolled back")
        raise
    finally:
        session.close()
        logger.debug("Database session closed")


def init_db() -> None:
    """Create tables when running outside the Docker init SQL path."""

    import app.models  # noqa: F401

    logger.info("Ensuring database schema exists via SQLAlchemy metadata")
    Base.metadata.create_all(bind=engine)
