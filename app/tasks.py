from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.celery_app import celery
from app.config import get_settings, setup_logging
from app.db import init_db, session_scope
from app.deduplicator import Deduplicator
from app.models import ExecutionLog, Job as JobModel
from app.notifier import Notifier
from app.scoring import score_job
from app.scrapers import GitHubBackendBRScraper, LinkedInScraper, ProgramathorScraper
from app.scrapers.base import BaseScraper, Job

settings = get_settings()
setup_logging(settings)
logger = logging.getLogger(__name__)


SCRAPER_REGISTRY: dict[str, type[BaseScraper]] = {
    "github_backendbr": GitHubBackendBRScraper,
    "programathor": ProgramathorScraper,
    "linkedin": LinkedInScraper,
}


@celery.task(name="app.tasks.fetch_and_process_jobs", bind=True)
def fetch_and_process_jobs(self) -> dict[str, Any]:
    """Orchestrate scraping, deduplication, scoring, persistence and notification."""

    task_id = getattr(self.request, "id", None)
    started_at = datetime.now(UTC)
    logger.info("Pipeline started task_id=%s started_at=%s", task_id, started_at.isoformat())
    init_db()

    execution_log_id = _create_execution_log(started_at)
    scraped_jobs: list[Job] = []
    scraper_errors: list[str] = []
    sources_scraped = 0

    try:
        for scraper in _build_scrapers():
            try:
                logger.info("Running scraper source=%s", scraper.name)
                jobs = scraper.scrape()
                scraped_jobs.extend(jobs)
                sources_scraped += 1
                logger.info("Scraper source=%s finished jobs=%s", scraper.name, len(jobs))
            except Exception as exc:
                message = f"{scraper.name}: {exc}"
                scraper_errors.append(message)
                logger.exception("Scraper source=%s failed and will be skipped", scraper.name)

        top_jobs, inserted_count = _process_and_store_jobs(scraped_jobs)
        status = "success" if sources_scraped > 0 else "failed"
        error_message = "; ".join(scraper_errors) if scraper_errors else None
        if status == "failed" and not error_message:
            error_message = "No source was successfully scraped"

        _finalize_execution_log(
            execution_log_id=execution_log_id,
            sources_scraped=sources_scraped,
            jobs_found=len(scraped_jobs),
            jobs_new=inserted_count,
            status=status,
            error_message=error_message,
        )

        try:
            Notifier(settings).send_daily_report(top_jobs, total_new=inserted_count)
        except Exception:
            logger.exception("Notification failed after successful persistence")

        result = {
            "execution_log_id": execution_log_id,
            "sources_scraped": sources_scraped,
            "jobs_found": len(scraped_jobs),
            "jobs_new": inserted_count,
            "status": status,
            "errors": scraper_errors,
        }
        logger.info("Pipeline finished result=%s", result)
        return result
    except Exception as exc:
        logger.exception("Pipeline failed task_id=%s", task_id)
        _finalize_execution_log(
            execution_log_id=execution_log_id,
            sources_scraped=sources_scraped,
            jobs_found=len(scraped_jobs),
            jobs_new=0,
            status="failed",
            error_message=str(exc),
        )
        raise


def _build_scrapers() -> list[BaseScraper]:
    scrapers: list[BaseScraper] = []
    for source in settings.sources:
        source_key = source.strip().lower()
        scraper_class = SCRAPER_REGISTRY.get(source_key)
        if not scraper_class:
            logger.warning("Unknown scraper source=%s ignored", source)
            continue
        scrapers.append(scraper_class(settings))
    logger.info("Scrapers built sources=%s", [scraper.name for scraper in scrapers])
    return scrapers


def _create_execution_log(started_at: datetime) -> int:
    with session_scope() as session:
        log = ExecutionLog(started_at=started_at, status="pending")
        session.add(log)
        session.flush()
        logger.info("Execution log created id=%s", log.id)
        return log.id


def _finalize_execution_log(
    *,
    execution_log_id: int,
    sources_scraped: int,
    jobs_found: int,
    jobs_new: int,
    status: str,
    error_message: str | None,
) -> None:
    finished_at = datetime.now(UTC)
    with session_scope() as session:
        session.execute(
            update(ExecutionLog)
            .where(ExecutionLog.id == execution_log_id)
            .values(
                finished_at=finished_at,
                sources_scraped=sources_scraped,
                jobs_found=jobs_found,
                jobs_new=jobs_new,
                status=status,
                error_message=error_message,
            )
        )
    logger.info(
        "Execution log finalized id=%s status=%s jobs_found=%s jobs_new=%s",
        execution_log_id,
        status,
        jobs_found,
        jobs_new,
    )


def _process_and_store_jobs(scraped_jobs: list[Job]) -> tuple[list[dict[str, Any]], int]:
    if not scraped_jobs:
        logger.info("No scraped jobs to process")
        return [], 0

    with session_scope() as session:
        deduplicator = Deduplicator(session=session, recent_window_days=7)
        new_jobs = deduplicator.filter_new(scraped_jobs)
        if not new_jobs:
            logger.info("No new jobs after deduplication")
            return [], 0

        payloads: list[dict[str, Any]] = []
        for job in new_jobs:
            score = score_job(job, settings.desired_stack, settings.desired_seniority)
            payloads.append(
                {
                    "title": job.title[:300],
                    "company": job.company[:200] if job.company else None,
                    "location": job.location[:200] if job.location else None,
                    "stack": job.stack,
                    "link": job.link[:500],
                    "source": job.source[:100],
                    "published_at": job.published_at,
                    "seniority": job.seniority[:50] if job.seniority else None,
                    "score": Decimal(str(score)),
                }
            )

        statement = (
            pg_insert(JobModel)
            .values(payloads)
            .on_conflict_do_nothing(index_elements=["link"])
            .returning(JobModel.link)
        )
        inserted_links = set(session.execute(statement).scalars().all())
        inserted_payloads = [payload for payload in payloads if payload["link"] in inserted_links]
        logger.info("Inserted new jobs count=%s", len(inserted_payloads))

        top_jobs = sorted(
            (
                payload
                for payload in inserted_payloads
                if float(payload["score"]) >= settings.min_score_to_notify
            ),
            key=lambda payload: float(payload["score"]),
            reverse=True,
        )[:10]
        logger.info("Top jobs selected for notification count=%s", len(top_jobs))
        return top_jobs, len(inserted_payloads)
