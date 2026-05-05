from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from app.config import Settings
from app.exceptions import ScraperError
from app.scrapers import GitHubBackendBRScraper, LinkedInScraper, ProgramathorScraper
from app.scrapers.base import BaseScraper, Job

logger = logging.getLogger(__name__)

SCRAPER_REGISTRY: dict[str, type[BaseScraper]] = {
    "github_backendbr": GitHubBackendBRScraper,
    "programathor": ProgramathorScraper,
    "linkedin": LinkedInScraper,
}


@dataclass(slots=True)
class ScrapingResult:
    jobs: list[Job] = field(default_factory=list)
    sources_scraped: int = 0
    errors: list[str] = field(default_factory=list)
    per_source_counts: dict[str, int] = field(default_factory=dict)


class ScrapingService:
    """Build and execute configured scrapers without letting one source stop the batch."""

    def __init__(self, settings: Settings, scrapers: list[BaseScraper] | None = None) -> None:
        self.settings = settings
        self._scrapers = scrapers

    def build_scrapers(self) -> list[BaseScraper]:
        if self._scrapers is not None:
            return self._scrapers
        scrapers: list[BaseScraper] = []
        for source in self.settings.sources:
            scraper_class = SCRAPER_REGISTRY.get(source.strip().lower())
            if not scraper_class:
                logger.warning("Unknown scraper source=%s ignored", source)
                continue
            scrapers.append(scraper_class(self.settings))
        logger.info("Scrapers built sources=%s", [scraper.name for scraper in scrapers])
        return scrapers

    def scrape_all(self) -> ScrapingResult:
        result = ScrapingResult()
        for scraper in self.build_scrapers():
            started = time.perf_counter()
            try:
                logger.info("Running scraper source=%s", scraper.name)
                jobs = scraper.scrape()
                duration_ms = int((time.perf_counter() - started) * 1000)
                result.jobs.extend(jobs)
                result.sources_scraped += 1
                result.per_source_counts[scraper.name] = len(jobs)
                logger.info(
                    "Scraper finished source=%s jobs_found=%s duration_ms=%s",
                    scraper.name,
                    len(jobs),
                    duration_ms,
                )
            except ScraperError as exc:
                message = f"{scraper.name}: {exc}"
                result.errors.append(message)
                logger.warning("Scraper failed source=%s error=%s", scraper.name, exc)
            except Exception as exc:
                message = f"{scraper.name}: {exc}"
                result.errors.append(message)
                logger.exception("Scraper failed source=%s", scraper.name)
        return result
