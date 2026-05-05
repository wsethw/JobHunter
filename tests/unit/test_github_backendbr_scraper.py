from __future__ import annotations

import json

import pytest

from app.exceptions import ScraperError
from app.scrapers.github_backendbr import GitHubBackendBRScraper


def test_issue_to_job(settings, fixture_path) -> None:
    issue = json.loads(
        (fixture_path / "github_issue_python_backend.json").read_text(encoding="utf-8")
    )
    job = GitHubBackendBRScraper(settings)._issue_to_job(issue)
    assert job.title.startswith("[Remoto]")
    assert job.company == "ACME"
    assert job.external_id == "42"
    assert "Python" in job.stack
    assert job.raw_payload["issue_number"] == 42


def test_next_link(settings) -> None:
    scraper = GitHubBackendBRScraper(settings)
    header = '<https://api.github.com/repositories/1/issues?page=2>; rel="next"'
    assert scraper._next_link(header).endswith("page=2")


def test_get_rate_limit_raises(settings, mocker) -> None:
    scraper = GitHubBackendBRScraper(settings)
    response = mocker.Mock()
    response.status_code = 403
    response.headers = {"X-RateLimit-Remaining": "0"}
    scraper.session.get = mocker.Mock(return_value=response)
    with pytest.raises(ScraperError):
        scraper._get("https://api.github.com/test")


def test_get_server_error_retries_and_raises(settings, mocker) -> None:
    scraper = GitHubBackendBRScraper(settings)
    response = mocker.Mock()
    response.status_code = 500
    response.headers = {}
    scraper.session.get = mocker.Mock(return_value=response)
    with pytest.raises(RuntimeError):
        scraper._get("https://api.github.com/test")
    assert scraper.session.get.call_count == 3
