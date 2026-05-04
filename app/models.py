from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Integer, Numeric, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

logger = logging.getLogger(__name__)


class Job(Base):
    """Persisted job listing."""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    company: Mapped[str | None] = mapped_column(String(200), nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    stack: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    link: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    seniority: Mapped[str | None] = mapped_column(String(50), nullable=True)
    score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index("idx_jobs_created_at", "created_at"),
        Index("idx_jobs_source", "source"),
        Index("idx_jobs_score", "score"),
    )

    def __repr__(self) -> str:
        return f"Job(id={self.id!r}, title={self.title!r}, source={self.source!r})"


class ExecutionLog(Base):
    """Audit record for one pipeline execution."""

    __tablename__ = "execution_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sources_scraped: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    jobs_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    jobs_new: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index("idx_execution_logs_started_at", "started_at"),
        Index("idx_execution_logs_status", "status"),
    )

    def __repr__(self) -> str:
        return f"ExecutionLog(id={self.id!r}, status={self.status!r}, jobs_new={self.jobs_new!r})"
