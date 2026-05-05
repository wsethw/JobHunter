from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

logger = logging.getLogger(__name__)

JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


class Job(Base):
    """Persisted job listing."""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    company: Mapped[str | None] = mapped_column(String(200), nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    stack: Mapped[list[str]] = mapped_column(
        JSON_TYPE,
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )
    link: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    seniority: Mapped[str | None] = mapped_column(String(50), nullable=True)
    score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    score_reasons: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    salary_min: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    salary_max: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    contract_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    remote_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="active", server_default="active"
    )
    seen_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("idx_jobs_created_at", "created_at"),
        Index("idx_jobs_last_seen_at", "last_seen_at"),
        Index("idx_jobs_source", "source"),
        Index("idx_jobs_score", "score"),
        Index("idx_jobs_fingerprint", "fingerprint"),
        Index("idx_jobs_content_hash", "content_hash"),
        Index("idx_jobs_source_external_id", "source", "external_id"),
        CheckConstraint(
            "score IS NULL OR (score >= 0 AND score <= 100)", name="ck_jobs_score_range"
        ),
    )

    def __repr__(self) -> str:
        return f"Job(id={self.id!r}, title={self.title!r}, source={self.source!r})"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "stack": self.stack,
            "link": self.link,
            "source": self.source,
            "external_id": self.external_id,
            "fingerprint": self.fingerprint,
            "content_hash": self.content_hash,
            "published_at": self.published_at,
            "seniority": self.seniority,
            "score": float(self.score) if self.score is not None else None,
            "score_reasons": self.score_reasons,
            "salary_min": float(self.salary_min) if self.salary_min is not None else None,
            "salary_max": float(self.salary_max) if self.salary_max is not None else None,
            "salary_currency": self.salary_currency,
            "contract_type": self.contract_type,
            "remote_type": self.remote_type,
            "country": self.country,
            "city": self.city,
            "status": self.status,
            "seen_count": self.seen_count,
            "last_seen_at": self.last_seen_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class ExecutionLog(Base):
    """Audit record for one pipeline execution."""

    __tablename__ = "execution_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sources_scraped: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    jobs_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    jobs_new: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
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
