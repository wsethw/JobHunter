from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Job as JobModel
from app.scrapers.base import Job

logger = logging.getLogger(__name__)


class Deduplicator:
    """Strict link-based deduplication against the database and current batch."""

    def __init__(self, session: Session, recent_window_days: int = 7) -> None:
        self.session = session
        self.recent_window_days = recent_window_days
        logger.debug("Deduplicator initialized recent_window_days=%s", recent_window_days)

    def filter_new(self, jobs: Iterable[Job]) -> list[Job]:
        jobs_by_link: dict[str, Job] = {}
        for job in jobs:
            if job.link in jobs_by_link:
                logger.info("Duplicate ignored inside current batch link=%s", job.link)
                continue
            jobs_by_link[job.link] = job

        links = list(jobs_by_link.keys())
        existing_recent = self.existing_links(links, recent_only=True)
        existing_any = self.existing_links(links, recent_only=False)
        existing = existing_recent | existing_any

        new_jobs: list[Job] = []
        for link, job in jobs_by_link.items():
            if link in existing:
                window = "recent" if link in existing_recent else "historical"
                logger.info("Duplicate ignored from database window=%s link=%s", window, link)
                continue
            new_jobs.append(job)

        logger.info(
            "Deduplication finished input=%s unique_batch=%s existing=%s new=%s",
            len(list(jobs_by_link.values())),
            len(jobs_by_link),
            len(existing),
            len(new_jobs),
        )
        return new_jobs

    def existing_links(self, links: list[str], *, recent_only: bool) -> set[str]:
        if not links:
            return set()

        statement = select(JobModel.link).where(JobModel.link.in_(links))
        if recent_only:
            since = datetime.now(UTC) - timedelta(days=self.recent_window_days)
            statement = statement.where(JobModel.created_at >= since)

        rows = self.session.execute(statement).scalars().all()
        existing = set(rows)
        logger.debug("Existing links fetched recent_only=%s count=%s", recent_only, len(existing))
        return existing
