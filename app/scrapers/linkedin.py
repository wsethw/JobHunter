from __future__ import annotations

import logging
from urllib.parse import urlencode

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from app.scrapers.base import BaseScraper, Job

logger = logging.getLogger(__name__)


class LinkedInScraper(BaseScraper):
    """Scrape public LinkedIn Jobs search results defensively."""

    name = "linkedin"
    base_url = "https://www.linkedin.com/jobs/search/"

    def scrape(self) -> list[Job]:
        search_url = self._build_search_url()
        logger.info("%s scraping started url=%s", self.name, search_url)
        jobs: list[Job] = []

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = browser.new_context(
                user_agent=self.choose_user_agent(),
                locale="pt-BR",
                viewport={"width": 1366, "height": 768},
            )
            context.set_default_timeout(self.settings.playwright_timeout_ms)
            page = context.new_page()

            try:
                page.goto(search_url, wait_until="domcontentloaded", timeout=self.settings.playwright_timeout_ms)
                page.wait_for_timeout(2500)
                cards = page.locator("ul.jobs-search__results-list li, div.base-search-card").all()
                logger.info("%s result cards found=%s", self.name, len(cards))

                for card in cards[: self.settings.max_jobs_per_source]:
                    try:
                        job = self._parse_card(card)
                        if job:
                            jobs.append(job)
                    except Exception:
                        logger.exception("%s failed to parse a result card", self.name)
            except PlaywrightTimeoutError:
                logger.warning("%s timed out loading search results", self.name)
            finally:
                context.close()
                browser.close()

        logger.info("%s scraping finished jobs=%s", self.name, len(jobs))
        return jobs

    def _build_search_url(self) -> str:
        params = {
            "keywords": self.settings.job_search_query,
            "location": self.settings.job_search_location,
            "f_TPR": "r86400",
            "position": "1",
            "pageNum": "0",
        }
        return f"{self.base_url}?{urlencode(params)}"

    def _parse_card(self, card) -> Job | None:
        text = self._safe_inner_text(card)
        title = self._safe_locator_text(card, ".base-search-card__title, h3")
        company = self._safe_locator_text(card, ".base-search-card__subtitle, h4")
        location = self._safe_locator_text(card, ".job-search-card__location")
        link = self._safe_locator_attr(card, "a.base-card__full-link, a[href*='/jobs/view/']", "href")
        published_raw = self._safe_locator_attr(card, "time", "datetime")

        if not title or not link:
            logger.debug("%s ignored card without title/link text=%s", self.name, text[:120])
            return None

        stack = self.detect_stack(title, text)
        seniority = self.estimate_seniority(title, text)

        return self.build_job(
            title=title,
            company=company,
            location=location,
            stack=stack,
            link=link,
            published_at=self.safe_datetime(published_raw),
            seniority=seniority,
            description=text,
        )

    def _safe_inner_text(self, locator) -> str:
        try:
            return self.normalize_text(locator.inner_text(timeout=2000))
        except Exception:
            return ""

    def _safe_locator_text(self, root, selector: str) -> str | None:
        try:
            locator = root.locator(selector).first
            if locator.count() == 0:
                return None
            value = locator.inner_text(timeout=2000)
            return self.normalize_text(value) or None
        except Exception:
            return None

    def _safe_locator_attr(self, root, selector: str, attr: str) -> str | None:
        try:
            locator = root.locator(selector).first
            if locator.count() == 0:
                return None
            return locator.get_attribute(attr, timeout=2000)
        except Exception:
            return None
