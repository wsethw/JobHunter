from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any

from app.config import Settings
from app.notifier import Notifier

logger = logging.getLogger(__name__)


class NotificationService:
    """Small orchestration wrapper around concrete notifiers."""

    def __init__(self, settings: Settings, notifier: Notifier | None = None) -> None:
        self.settings = settings
        self.notifier = notifier or Notifier(settings)

    def notify_daily_report(self, jobs: Sequence[Mapping[str, Any]], total_new: int) -> str:
        if not jobs and not self.settings.send_empty_report:
            logger.info("Skipping empty report because SEND_EMPTY_REPORT=false")
            return "skipped_empty"
        self.notifier.send_daily_report(jobs, total_new)
        return "sent"
