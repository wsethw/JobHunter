from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Select, desc, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.deduplicator import generate_content_hash, generate_job_fingerprint
from app.models import Job as JobModel
from app.scrapers.base import Job

logger = logging.getLogger(__name__)


class JobsRepository:
    """Persistence operations for jobs."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_existing_links(self, links: Iterable[str], since_days: int | None = None) -> set[str]:
        links_list = list(links)
        if not links_list:
            return set()
        statement = select(JobModel.link).where(JobModel.link.in_(links_list))
        if since_days is not None:
            statement = statement.where(
                JobModel.created_at >= datetime.now(UTC) - timedelta(days=since_days)
            )
        existing = set(self.session.execute(statement).scalars().all())
        logger.debug("Repository fetched existing links count=%s", len(existing))
        return existing

    def upsert_jobs(self, payloads: list[dict[str, Any]]) -> int:
        if not payloads:
            logger.info("No job payloads to upsert")
            return 0

        prepared = [self._prepare_payload(payload) for payload in payloads]
        dialect_name = self.session.get_bind().dialect.name
        insert_factory = sqlite_insert if dialect_name == "sqlite" else pg_insert
        insert_statement = insert_factory(JobModel).values(prepared)
        excluded = insert_statement.excluded

        update_values = {
            "title": excluded.title,
            "company": excluded.company,
            "location": excluded.location,
            "stack": excluded.stack,
            "source": excluded.source,
            "external_id": excluded.external_id,
            "fingerprint": excluded.fingerprint,
            "content_hash": excluded.content_hash,
            "published_at": excluded.published_at,
            "seniority": excluded.seniority,
            "score": excluded.score,
            "score_reasons": excluded.score_reasons,
            "raw_payload": excluded.raw_payload,
            "salary_min": excluded.salary_min,
            "salary_max": excluded.salary_max,
            "salary_currency": excluded.salary_currency,
            "contract_type": excluded.contract_type,
            "remote_type": excluded.remote_type,
            "country": excluded.country,
            "city": excluded.city,
            "status": excluded.status,
            "last_seen_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
            "seen_count": JobModel.seen_count + 1,
        }
        statement = insert_statement.on_conflict_do_update(
            index_elements=["link"],
            set_=update_values,
        )
        result = self.session.execute(statement)
        self.session.flush()
        self.session.expire_all()
        count = max(getattr(result, "rowcount", len(prepared)) or 0, 0)
        logger.info("Upserted jobs count=%s", count)
        return count

    def list_recent_jobs(self, limit: int = 50) -> list[JobModel]:
        statement = select(JobModel).order_by(desc(JobModel.created_at)).limit(limit)
        return list(self.session.execute(statement).scalars().all())

    def list_top_jobs(self, limit: int = 10, min_score: float = 0.0) -> list[JobModel]:
        statement = (
            select(JobModel)
            .where(JobModel.score >= min_score)
            .order_by(desc(JobModel.score), desc(JobModel.last_seen_at))
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())

    def mark_job_seen(self, job_id: int) -> None:
        self.session.execute(
            update(JobModel)
            .where(JobModel.id == job_id)
            .values(
                last_seen_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                seen_count=JobModel.seen_count + 1,
            )
        )
        logger.info("Marked job seen id=%s", job_id)

    def find_duplicates_by_fingerprint(self, job: Job) -> list[JobModel]:
        fingerprint = generate_job_fingerprint(job)
        content_hash = generate_content_hash(job)
        statement: Select = select(JobModel).where(
            or_(
                JobModel.link == job.link,
                JobModel.fingerprint == fingerprint,
                JobModel.content_hash == content_hash,
            )
        )
        duplicates = list(self.session.execute(statement).scalars().all())
        logger.debug("Found duplicates by fingerprint count=%s", len(duplicates))
        return duplicates

    def _prepare_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        prepared = payload.copy()
        prepared.setdefault("status", "active")
        prepared.setdefault("seen_count", 1)
        prepared.setdefault("last_seen_at", datetime.now(UTC))
        prepared.setdefault("updated_at", datetime.now(UTC))
        return prepared
