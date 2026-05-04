from __future__ import annotations

import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from app.scrapers.base import BaseScraper, Job

logger = logging.getLogger(__name__)


class ProgramathorScraper(BaseScraper):
    """Scrape public ProgramaThor job pages with Playwright."""

    name = "programathor"
    base_url = "https://programathor.com.br"
    jobs_url = "https://programathor.com.br/jobs"

    def scrape(self) -> list[Job]:
        logger.info("%s scraping started url=%s", self.name, self.jobs_url)
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
                page.goto(self.jobs_url, wait_until="domcontentloaded", timeout=self.settings.playwright_timeout_ms)
                page.wait_for_timeout(1500)
                links = self._collect_job_links(page.content())
                logger.info("%s collected candidate links=%s", self.name, len(links))

                for link in links[: self.settings.max_jobs_per_source]:
                    try:
                        job = self._scrape_detail(page, link)
                        if job:
                            jobs.append(job)
                    except PlaywrightTimeoutError:
                        logger.warning("%s timeout loading detail link=%s", self.name, link)
                    except Exception:
                        logger.exception("%s failed to parse detail link=%s", self.name, link)
            finally:
                context.close()
                browser.close()

        logger.info("%s scraping finished jobs=%s", self.name, len(jobs))
        return jobs

    def _collect_job_links(self, html: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        links: list[str] = []
        seen: set[str] = set()

        for anchor in soup.select('a[href*="/jobs/"]'):
            href = anchor.get("href")
            if not href:
                continue
            absolute = self.canonicalize_url(urljoin(self.base_url, href))
            if "/jobs/" not in absolute or absolute in seen:
                continue
            text = self.normalize_text(anchor.get_text(" "))
            if not text or len(text) < 8:
                continue
            links.append(absolute)
            seen.add(absolute)

        logger.debug("%s collected links=%s", self.name, links)
        return links

    def _scrape_detail(self, page, link: str) -> Job | None:
        logger.info("%s loading detail link=%s", self.name, link)
        page.goto(link, wait_until="domcontentloaded", timeout=self.settings.playwright_timeout_ms)
        page.wait_for_timeout(1000)

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        full_text = self.normalize_text(soup.get_text(" "))

        title = self._first_text(soup, ["h1", "h2"]) or self._title_from_url(link)
        if not title or title.lower() in {"vagas", "programathor"}:
            logger.warning("%s ignored detail with missing title link=%s", self.name, link)
            return None

        company = self._extract_company(soup, full_text)
        location = self._extract_field(full_text, ["Localização", "Localizacao", "Local"])
        seniority = self._extract_seniority_from_text(full_text) or self.estimate_seniority(title, full_text)
        stack = self._extract_stack_chips(soup) or self.detect_stack(title, full_text)

        return self.build_job(
            title=title,
            company=company,
            location=location,
            stack=stack,
            link=link,
            published_at=None,
            seniority=seniority,
            description=full_text,
        )

    def _first_text(self, soup: BeautifulSoup, selectors: list[str]) -> str | None:
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                value = self.normalize_text(element.get_text(" "))
                if value:
                    return value
        return None

    def _title_from_url(self, link: str) -> str:
        slug = link.rstrip("/").split("/")[-1]
        cleaned = re.sub(r"^\d+-", "", slug).replace("-", " ")
        return cleaned.title()

    def _extract_company(self, soup: BeautifulSoup, full_text: str) -> str | None:
        image = soup.select_one('img[alt]:not([alt=""])')
        if image and image.get("alt"):
            alt = self.normalize_text(image["alt"])
            if 2 <= len(alt) <= 80 and "programathor" not in alt.lower():
                return alt[:200]

        company = self._extract_field(full_text, ["Empresa", "Company"])
        if company:
            return company[:200]

        lines = [self.normalize_text(line) for line in soup.get_text("\n").splitlines()]
        lines = [line for line in lines if line]
        for index, line in enumerate(lines):
            if line.lower().startswith("vaga") and index + 2 < len(lines):
                candidate = lines[index + 2]
                if 2 <= len(candidate) <= 80:
                    return candidate[:200]
        return None

    def _extract_field(self, text: str, labels: list[str]) -> str | None:
        for label in labels:
            pattern = rf"{re.escape(label)}\s*:\s*([^|•\n\r]{2,200})"
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return self.normalize_text(match.group(1))[:200]
        return None

    def _extract_seniority_from_text(self, text: str) -> str | None:
        lower_text = text.lower()
        if re.search(r"\b(júnior|junior|jr)\b", lower_text):
            return "junior"
        if re.search(r"\bpleno\b", lower_text):
            return "pleno"
        if re.search(r"\b(sênior|senior|sr|especialista)\b", lower_text):
            return "senior"
        return None

    def _extract_stack_chips(self, soup: BeautifulSoup) -> list[str]:
        candidates: list[str] = []
        for element in soup.select("a, span, li, div"):
            text = self.normalize_text(element.get_text(" "))
            if not text or len(text) > 30:
                continue
            stack = self.detect_stack(text)
            for item in stack:
                if item.lower() not in {candidate.lower() for candidate in candidates}:
                    candidates.append(item)
        return candidates
