from __future__ import annotations

import logging

from celery import Celery
from celery.schedules import crontab

from app.config import get_settings, setup_logging

settings = get_settings()
setup_logging(settings)

logger = logging.getLogger(__name__)

celery = Celery(
    "jobhunter",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks"],
)

celery.conf.update(
    task_default_queue="default",
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone=settings.timezone,
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_time_limit=60 * 30,
    task_soft_time_limit=60 * 25,
    result_expires=60 * 60 * 24,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "jobhunter-daily-fetch-and-process": {
            "task": "app.tasks.fetch_and_process_jobs",
            "schedule": crontab(
                hour=settings.schedule_hour,
                minute=settings.schedule_minute,
            ),
        }
    },
)

logger.info(
    "Celery configured: broker=%s timezone=%s daily_schedule=%02d:%02d",
    settings.redis_url,
    settings.timezone,
    settings.schedule_hour,
    settings.schedule_minute,
)

__all__ = ["celery"]
