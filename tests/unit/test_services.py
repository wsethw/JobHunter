from __future__ import annotations

from app.exceptions import ScraperError
from app.scrapers.base import BaseScraper, Job
from app.services.notification_service import NotificationService
from app.services.scraping_service import ScrapingService
from tests.factories import make_job


class GoodScraper(BaseScraper):
    name = "good"

    def scrape(self) -> list[Job]:
        return [make_job(source=self.name)]


class BadScraper(BaseScraper):
    name = "bad"

    def scrape(self) -> list[Job]:
        raise ScraperError("blocked")


class UnexpectedBadScraper(BaseScraper):
    name = "unexpected"

    def scrape(self) -> list[Job]:
        raise RuntimeError("boom")


def test_scraping_service_collects_partial_results(settings) -> None:
    result = ScrapingService(
        settings, scrapers=[GoodScraper(settings), BadScraper(settings)]
    ).scrape_all()
    assert result.sources_scraped == 1
    assert len(result.jobs) == 1
    assert result.errors == ["bad: blocked"]


def test_scraping_service_catches_unexpected_errors(settings) -> None:
    result = ScrapingService(settings, scrapers=[UnexpectedBadScraper(settings)]).scrape_all()
    assert result.sources_scraped == 0
    assert result.errors == ["unexpected: boom"]


def test_notification_service_skips_empty_report(settings) -> None:
    assert NotificationService(settings).notify_daily_report([], 0) == "skipped_empty"


def test_notification_service_sends(mocker, settings) -> None:
    settings.send_empty_report = True
    notifier = mocker.Mock()
    service = NotificationService(settings, notifier=notifier)
    assert service.notify_daily_report([], 0) == "sent"
    notifier.send_daily_report.assert_called_once()
