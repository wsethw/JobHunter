from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class PipelineMetrics:
    sources_scraped: int = 0
    jobs_found: int = 0
    jobs_new: int = 0
    scraper_errors: list[str] = field(default_factory=list)
    notification_status: str = "skipped"

    def to_dict(self) -> dict:
        return asdict(self)
