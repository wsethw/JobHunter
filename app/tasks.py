from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from app.celery_app import celery
from app.config import get_settings, setup_logging
from app.db import session_scope
from app.models import ExecutionLog
from app.repositories import ExecutionLogsRepository, JobsRepository
from app.scrapers.base import BaseScraper, Job
from app.services import PipelineService, ScrapingService

settings = get_settings()
setup_logging(settings)
logger = logging.getLogger(__name__)


@celery.task(name="app.tasks.fetch_and_process_jobs", bind=True)
def fetch_and_process_jobs(self) -> dict[str, Any]:
    """Celery entrypoint: delegate the actual work to PipelineService."""

    task_id = getattr(self.request, "id", None)
    return PipelineService(settings=get_settings()).run(task_id=task_id)


def _build_scrapers() -> list[BaseScraper]:
    """Compatibility wrapper used by tests and older integrations."""

    return ScrapingService(get_settings()).build_scrapers()


def _process_and_store_jobs(scraped_jobs: list[Job]) -> tuple[list[dict[str, Any]], int]:
    """Compatibility wrapper around the service/repository pipeline."""

    service = PipelineService(settings=get_settings())
    payloads = service.process_jobs(scraped_jobs)
    with session_scope() as session:
        repository = JobsRepository(session)
        affected = repository.upsert_jobs(payloads)
        top_jobs = [
            job.to_dict()
            for job in repository.list_top_jobs(
                limit=10, min_score=get_settings().min_score_to_notify
            )
        ]
    return top_jobs, affected


def _create_execution_log(started_at: datetime | None = None) -> int:
    """Compatibility wrapper for legacy tests."""

    with session_scope() as session:
        return ExecutionLogsRepository(session).create_log(started_at or datetime.now(UTC))


def _finalize_execution_log(
    *,
    execution_log_id: int,
    sources_scraped: int,
    jobs_found: int,
    jobs_new: int,
    status: str,
    error_message: str | None,
) -> None:
    """Compatibility wrapper for legacy tests."""

    with session_scope() as session:
        repository = ExecutionLogsRepository(session)
        if status == "success":
            repository.finish_success(
                execution_log_id,
                sources_scraped=sources_scraped,
                jobs_found=jobs_found,
                jobs_new=jobs_new,
                error_message=error_message,
            )
        else:
            repository.finish_failed(
                execution_log_id,
                sources_scraped=sources_scraped,
                jobs_found=jobs_found,
                jobs_new=jobs_new,
                error_message=error_message,
            )


__all__ = [
    "ExecutionLog",
    "fetch_and_process_jobs",
    "_build_scrapers",
    "_process_and_store_jobs",
    "_create_execution_log",
    "_finalize_execution_log",
]
