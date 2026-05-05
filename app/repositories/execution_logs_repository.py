from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models import ExecutionLog

logger = logging.getLogger(__name__)


class ExecutionLogsRepository:
    """Persistence operations for execution audit logs."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_log(self, started_at: datetime | None = None) -> int:
        log = ExecutionLog(started_at=started_at or datetime.now(UTC), status="pending")
        self.session.add(log)
        self.session.flush()
        logger.info("Execution log created id=%s", log.id)
        return int(log.id)

    def finish_success(
        self,
        execution_log_id: int,
        *,
        sources_scraped: int,
        jobs_found: int,
        jobs_new: int,
        error_message: str | None = None,
    ) -> None:
        self._finish(
            execution_log_id,
            status="success",
            sources_scraped=sources_scraped,
            jobs_found=jobs_found,
            jobs_new=jobs_new,
            error_message=error_message,
        )

    def finish_failed(
        self,
        execution_log_id: int,
        *,
        sources_scraped: int = 0,
        jobs_found: int = 0,
        jobs_new: int = 0,
        error_message: str | None = None,
    ) -> None:
        self._finish(
            execution_log_id,
            status="failed",
            sources_scraped=sources_scraped,
            jobs_found=jobs_found,
            jobs_new=jobs_new,
            error_message=error_message,
        )

    def _finish(
        self,
        execution_log_id: int,
        *,
        status: str,
        sources_scraped: int,
        jobs_found: int,
        jobs_new: int,
        error_message: str | None,
    ) -> None:
        self.session.execute(
            update(ExecutionLog)
            .where(ExecutionLog.id == execution_log_id)
            .values(
                finished_at=datetime.now(UTC),
                sources_scraped=sources_scraped,
                jobs_found=jobs_found,
                jobs_new=jobs_new,
                status=status,
                error_message=error_message,
            )
        )
        logger.info("Execution log finished id=%s status=%s", execution_log_id, status)
