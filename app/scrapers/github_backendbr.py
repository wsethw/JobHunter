from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any

import requests
from requests import Response
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import Settings
from app.scrapers.base import BaseScraper, Job

logger = logging.getLogger(__name__)


class GitHubBackendBRScraper(BaseScraper):
    """Collect open issues from backend-br/vagas through GitHub REST API."""

    name = "github_backendbr"
    api_url = "https://api.github.com/repos/backend-br/vagas/issues"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.session = requests.Session()

    def scrape(self) -> list[Job]:
        logger.info("%s scraping started", self.name)
        since = datetime.now(UTC) - timedelta(days=self.settings.github_since_days)
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": self.choose_user_agent(),
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.settings.github_token:
            headers["Authorization"] = f"Bearer {self.settings.github_token}"

        jobs: list[Job] = []
        page = 1
        while len(jobs) < self.settings.max_jobs_per_source:
            params = {
                "state": "open",
                "per_page": min(100, self.settings.max_jobs_per_source),
                "page": page,
                "since": since.isoformat(),
                "sort": "created",
                "direction": "desc",
            }
            response = self._get(self.api_url, headers=headers, params=params)
            issues = response.json()
            if not issues:
                logger.info("%s no more GitHub issues found at page=%s", self.name, page)
                break

            for issue in issues:
                if "pull_request" in issue:
                    continue
                try:
                    jobs.append(self._issue_to_job(issue))
                except Exception:
                    logger.exception("%s failed to normalize issue id=%s", self.name, issue.get("id"))
                if len(jobs) >= self.settings.max_jobs_per_source:
                    break

            page += 1
            if page > 3:
                logger.info("%s reached pagination safety limit", self.name)
                break

        logger.info("%s scraping finished jobs=%s", self.name, len(jobs))
        return jobs

    @retry(
        retry=retry_if_exception_type((requests.RequestException, RuntimeError)),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _get(self, url: str, **kwargs: Any) -> Response:
        response = self.session.get(url, timeout=30, **kwargs)
        if response.status_code >= 500:
            raise RuntimeError(f"GitHub API transient error status={response.status_code}")
        response.raise_for_status()
        remaining = response.headers.get("X-RateLimit-Remaining")
        logger.debug("%s GitHub API status=%s remaining=%s", self.name, response.status_code, remaining)
        return response

    def _issue_to_job(self, issue: dict[str, Any]) -> Job:
        title = issue.get("title") or "Sem título"
        body = issue.get("body") or ""
        html_url = issue["html_url"]
        labels = " ".join(label.get("name", "") for label in issue.get("labels", []))

        company = self._parse_company(title, body)
        location = self._parse_location(title, body, labels)
        published_at = self.safe_datetime(issue.get("created_at"))
        stack = self.detect_stack(title, body, labels)
        seniority = self.estimate_seniority(title, body, labels)

        return self.build_job(
            title=title,
            company=company,
            location=location,
            stack=stack,
            link=html_url,
            published_at=published_at,
            seniority=seniority,
            description=body,
            extra_text=labels,
        )

    def _parse_company(self, title: str, body: str) -> str | None:
        title_match = re.search(r"@\s*([^\]\)\|/-][\wÀ-ÿ0-9 .,&+-]{2,80})", title)
        if title_match:
            return title_match.group(1).strip()

        body_patterns = [
            r"(?im)^\s*(?:empresa|company)\s*[:\-]\s*(.+)$",
            r"(?im)^\s*##\s*(?:empresa|company)\s*$\s*(.+)$",
        ]
        for pattern in body_patterns:
            match = re.search(pattern, body)
            if match:
                value = self.normalize_text(match.group(1))
                if value:
                    return value[:200]
        return None

    def _parse_location(self, title: str, body: str, labels: str) -> str | None:
        bracket_match = re.search(r"\[([^\]]+)\]", title)
        if bracket_match:
            return bracket_match.group(1).strip()[:200]

        body_patterns = [
            r"(?im)^\s*(?:local|localização|localizacao|location)\s*[:\-]\s*(.+)$",
            r"(?im)^\s*(?:remoto|remote)\b.*$",
        ]
        for pattern in body_patterns:
            match = re.search(pattern, body)
            if match:
                value = self.normalize_text(match.group(1) if match.groups() else match.group(0))
                if value:
                    return value[:200]

        if "remoto" in labels.lower() or "remote" in labels.lower():
            return "Remoto"
        return None
