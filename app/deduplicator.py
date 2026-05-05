from __future__ import annotations

import hashlib
import logging
import re
import unicodedata
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Job as JobModel
from app.scrapers.base import Job

logger = logging.getLogger(__name__)


class Deduplicator:
    """Deduplicate jobs by canonical link, fingerprint and content hash."""

    def __init__(self, session: Session, recent_window_days: int = 7) -> None:
        self.session = session
        self.recent_window_days = recent_window_days
        logger.debug("Deduplicator initialized recent_window_days=%s", recent_window_days)

    def filter_new(self, jobs: Iterable[Job]) -> list[Job]:
        jobs_list = list(jobs)
        unique_batch: dict[str, Job] = {}
        seen_links: set[str] = set()
        seen_fingerprints: set[str] = set()
        seen_hashes: set[str] = set()

        for job in jobs_list:
            fingerprint = generate_job_fingerprint(job)
            content_hash = generate_content_hash(job)
            if job.link in seen_links:
                logger.info("Duplicate ignored inside batch by link=%s", job.link)
                continue
            if fingerprint in seen_fingerprints:
                logger.info("Duplicate ignored inside batch by fingerprint=%s", fingerprint)
                continue
            if content_hash in seen_hashes:
                logger.info("Duplicate ignored inside batch by content_hash=%s", content_hash)
                continue
            unique_batch[job.link] = job
            seen_links.add(job.link)
            seen_fingerprints.add(fingerprint)
            seen_hashes.add(content_hash)

        existing_links = self.existing_links(list(seen_links), recent_only=False)
        existing_fingerprints = self.existing_fingerprints(
            list(seen_fingerprints), recent_only=False
        )
        existing_hashes = self.existing_content_hashes(list(seen_hashes), recent_only=False)

        new_jobs: list[Job] = []
        for job in unique_batch.values():
            fingerprint = generate_job_fingerprint(job)
            content_hash = generate_content_hash(job)
            if job.link in existing_links:
                logger.info("Duplicate ignored from database by link=%s", job.link)
                continue
            if fingerprint in existing_fingerprints:
                logger.info("Duplicate ignored from database by fingerprint=%s", fingerprint)
                continue
            if content_hash in existing_hashes:
                logger.info("Duplicate ignored from database by content_hash=%s", content_hash)
                continue
            new_jobs.append(job)

        logger.info(
            "Deduplication finished input=%s unique_batch=%s existing=%s new=%s",
            len(jobs_list),
            len(unique_batch),
            len(existing_links) + len(existing_fingerprints) + len(existing_hashes),
            len(new_jobs),
        )
        return new_jobs

    def existing_links(self, links: list[str], *, recent_only: bool) -> set[str]:
        if not links:
            return set()
        statement = select(JobModel.link).where(JobModel.link.in_(links))
        if recent_only:
            statement = statement.where(JobModel.created_at >= self._recent_cutoff())
        existing = set(self.session.execute(statement).scalars().all())
        logger.debug("Existing links fetched recent_only=%s count=%s", recent_only, len(existing))
        return existing

    def existing_fingerprints(self, fingerprints: list[str], *, recent_only: bool) -> set[str]:
        fingerprints = [item for item in fingerprints if item]
        if not fingerprints:
            return set()
        statement = select(JobModel.fingerprint).where(JobModel.fingerprint.in_(fingerprints))
        if recent_only:
            statement = statement.where(JobModel.created_at >= self._recent_cutoff())
        return {item for item in self.session.execute(statement).scalars().all() if item}

    def existing_content_hashes(self, hashes: list[str], *, recent_only: bool) -> set[str]:
        hashes = [item for item in hashes if item]
        if not hashes:
            return set()
        statement = select(JobModel.content_hash).where(JobModel.content_hash.in_(hashes))
        if recent_only:
            statement = statement.where(JobModel.created_at >= self._recent_cutoff())
        return {item for item in self.session.execute(statement).scalars().all() if item}

    def find_duplicates_by_fingerprint(self, job: Job) -> list[JobModel]:
        fingerprint = generate_job_fingerprint(job)
        content_hash = generate_content_hash(job)
        statement = select(JobModel).where(
            or_(
                JobModel.link == job.link,
                JobModel.fingerprint == fingerprint,
                JobModel.content_hash == content_hash,
            )
        )
        return list(self.session.execute(statement).scalars().all())

    def _recent_cutoff(self) -> datetime:
        return datetime.now(UTC) - timedelta(days=self.recent_window_days)


def generate_job_fingerprint(job: Job) -> str:
    parts = [
        _normalize(job.title),
        _normalize(job.company or ""),
        _normalize(job.location or ""),
        _normalize(job.seniority or ""),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def generate_content_hash(job: Job) -> str:
    parts = [
        _normalize(job.title),
        _normalize(job.company or ""),
        _normalize(job.location or ""),
        _normalize(" ".join(sorted(job.stack, key=str.lower))),
        _normalize(job.description or ""),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = re.sub(r"\b(senior|sênior|sr\.?)\b", "senior", value, flags=re.I)
    value = re.sub(r"\b(junior|júnior|jr\.?)\b", "junior", value, flags=re.I)
    value = re.sub(r"\b(pleno|mid[- ]?level)\b", "pleno", value, flags=re.I)
    value = re.sub(r"[^\w\s]", " ", value.lower())
    return re.sub(r"\s+", " ", value).strip()
