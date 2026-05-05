from __future__ import annotations

import logging
import traceback
from datetime import UTC, datetime
from typing import Any

from app.config import Settings
from app.db import session_scope
from app.repositories import ExecutionLogsRepository, JobsRepository
from app.scrapers.base import Job
from app.services.notification_service import NotificationService
from app.services.scoring_service import ScoringService
from app.services.scraping_service import ScrapingService

logger = logging.getLogger(__name__)


class PipelineService:
    """Main JobHunter pipeline orchestrator."""

    def __init__(
        self,
        settings: Settings,
        scraping_service: ScrapingService | None = None,
        scoring_service: ScoringService | None = None,
        notification_service: NotificationService | None = None,
    ) -> None:
        self.settings = settings
        self.scraping_service = scraping_service or ScrapingService(settings)
        self.scoring_service = scoring_service or ScoringService(settings)
        self.notification_service = notification_service or NotificationService(settings)

    def run(self, task_id: str | None = None, *, dry_run: bool = False) -> dict[str, Any]:
        started_at = datetime.now(UTC)
        logger.info("Pipeline started task_id=%s dry_run=%s", task_id, dry_run)
        execution_log_id: int | None = None
        sources_scraped = 0
        jobs_found = 0
        jobs_new = 0
        notification_status = "skipped"
        scraper_errors: list[str] = []

        try:
            if not dry_run:
                with session_scope() as session:
                    execution_log_id = ExecutionLogsRepository(session).create_log(started_at)

            scraping_result = self.scraping_service.scrape_all()
            sources_scraped = scraping_result.sources_scraped
            jobs_found = len(scraping_result.jobs)
            scraper_errors = scraping_result.errors
            payloads = self.process_jobs(scraping_result.jobs)

            if dry_run:
                top_jobs = self._top_payloads(payloads)
                return {
                    "execution_log_id": None,
                    "sources_scraped": sources_scraped,
                    "jobs_found": jobs_found,
                    "jobs_new": len(payloads),
                    "status": "dry_run",
                    "errors": scraper_errors,
                    "top_jobs": top_jobs,
                }

            with session_scope() as session:
                jobs_repo = JobsRepository(session)
                jobs_new = jobs_repo.upsert_jobs(payloads)
                top_jobs = [
                    job.to_dict()
                    for job in jobs_repo.list_top_jobs(
                        limit=10, min_score=self.settings.min_score_to_notify
                    )
                ]
                logs_repo = ExecutionLogsRepository(session)
                status = "success" if sources_scraped > 0 else "failed"
                error_message = "; ".join(scraper_errors) if scraper_errors else None
                if status == "success":
                    logs_repo.finish_success(
                        execution_log_id or 0,
                        sources_scraped=sources_scraped,
                        jobs_found=jobs_found,
                        jobs_new=jobs_new,
                        error_message=error_message,
                    )
                else:
                    logs_repo.finish_failed(
                        execution_log_id or 0,
                        sources_scraped=sources_scraped,
                        jobs_found=jobs_found,
                        jobs_new=jobs_new,
                        error_message=error_message or "No source was successfully scraped",
                    )

            notification_status = self.notification_service.notify_daily_report(
                top_jobs, total_new=jobs_new
            )
            result = {
                "execution_log_id": execution_log_id,
                "sources_scraped": sources_scraped,
                "jobs_found": jobs_found,
                "jobs_new": jobs_new,
                "status": "success" if sources_scraped > 0 else "failed",
                "errors": scraper_errors,
                "notification_status": notification_status,
            }
            logger.info("Pipeline finished result=%s", result)
            return result
        except Exception as exc:
            logger.exception("Pipeline failed task_id=%s", task_id)
            if execution_log_id is not None and not dry_run:
                with session_scope() as session:
                    ExecutionLogsRepository(session).finish_failed(
                        execution_log_id,
                        sources_scraped=sources_scraped,
                        jobs_found=jobs_found,
                        jobs_new=jobs_new,
                        error_message=f"{exc}\n{traceback.format_exc()}",
                    )
            raise

    def process_jobs(self, jobs: list[Job]) -> list[dict[str, Any]]:
        unique_jobs = self._deduplicate_batch(jobs)
        return self.scoring_service.build_payloads(unique_jobs)

    def _deduplicate_batch(self, jobs: list[Job]) -> list[Job]:
        from app.deduplicator import generate_content_hash, generate_job_fingerprint

        unique: list[Job] = []
        links: set[str] = set()
        fingerprints: set[str] = set()
        hashes: set[str] = set()
        for job in jobs:
            fingerprint = generate_job_fingerprint(job)
            content_hash = generate_content_hash(job)
            if job.link in links or fingerprint in fingerprints or content_hash in hashes:
                logger.info(
                    "Duplicate ignored inside pipeline batch link=%s fingerprint=%s",
                    job.link,
                    fingerprint,
                )
                continue
            unique.append(job)
            links.add(job.link)
            fingerprints.add(fingerprint)
            hashes.add(content_hash)
        return unique

    def _top_payloads(self, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(
            [
                payload
                for payload in payloads
                if float(payload.get("score") or 0) >= self.settings.min_score_to_notify
            ],
            key=lambda payload: float(payload.get("score") or 0),
            reverse=True,
        )[:10]
