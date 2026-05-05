from __future__ import annotations

import logging
from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from app.config import Settings
from app.deduplicator import generate_content_hash, generate_job_fingerprint
from app.parsers import parse_contract_type, parse_location, parse_salary
from app.scoring import ScoreResult, score_job_detailed
from app.scrapers.base import Job

logger = logging.getLogger(__name__)


class ScoringService:
    """Convert scraped jobs into scored persistence payloads."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def score(self, job: Job) -> ScoreResult:
        return score_job_detailed(
            job=job,
            must_have_stack=self.settings.must_have_stack,
            nice_to_have_stack=self.settings.nice_to_have_stack,
            desired_seniority=self.settings.desired_seniority,
            negative_keywords=self.settings.negative_keywords,
            preferred_location=self.settings.preferred_location,
            remote_only=self.settings.remote_only,
        )

    def build_payloads(self, jobs: Iterable[Job]) -> list[dict[str, Any]]:
        payloads = [self.build_payload(job) for job in jobs]
        logger.info("Built scored payloads count=%s", len(payloads))
        return payloads

    def build_payload(self, job: Job) -> dict[str, Any]:
        salary_info = parse_salary(job.description)
        location_info = parse_location(job.location, job.description)
        contract_type = job.contract_type or parse_contract_type([job.title, job.description])
        score = self.score(job)
        raw_payload = job.raw_payload.copy()
        if job.description and "description" not in raw_payload:
            raw_payload["description"] = job.description

        payload = {
            "title": job.title[:300],
            "company": job.company[:200] if job.company else None,
            "location": (location_info.normalized_location or job.location),
            "stack": job.stack,
            "link": job.link[:500],
            "source": job.source[:100],
            "external_id": job.external_id[:200] if job.external_id else None,
            "fingerprint": generate_job_fingerprint(job),
            "content_hash": generate_content_hash(job),
            "published_at": job.published_at,
            "seniority": job.seniority[:50] if job.seniority else None,
            "score": Decimal(str(score.value)),
            "score_reasons": score.to_dict(),
            "raw_payload": raw_payload,
            "salary_min": job.salary_min or salary_info.salary_min,
            "salary_max": job.salary_max or salary_info.salary_max,
            "salary_currency": job.salary_currency or salary_info.salary_currency,
            "contract_type": contract_type,
            "remote_type": job.remote_type or location_info.remote_type,
            "country": job.country or location_info.country,
            "city": job.city or location_info.city,
            "status": "active",
        }
        logger.debug("Built payload for link=%s score=%s", job.link, score.value)
        return payload
