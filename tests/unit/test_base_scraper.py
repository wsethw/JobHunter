from __future__ import annotations

import pytest

from app.scrapers.base import BaseScraper, Job


class DummyScraper(BaseScraper):
    name = "dummy"

    def scrape(self) -> list[Job]:
        return []


def test_job_model_validates_link_and_stack() -> None:
    job = Job(
        title="Senior Python",
        company="ACME",
        location="Remote",
        stack=["Python", "python", ""],
        link="https://example.com/job",
        source="test",
    )
    assert job.stack == ["Python"]
    with pytest.raises(ValueError):
        Job(title="x", link="not-url", source="test")


def test_canonicalize_url_removes_tracking(settings) -> None:
    scraper = DummyScraper(settings)
    assert (
        scraper.canonicalize_url("HTTPS://Example.com/jobs/1/?utm_source=x&foo=bar#fragment")
        == "https://example.com/jobs/1?foo=bar"
    )


def test_detect_stack_and_estimate_seniority(settings) -> None:
    scraper = DummyScraper(settings)
    stack = scraper.detect_stack("Senior Python backend with FastAPI and PostgreSQL")
    assert {"Python", "FastAPI", "PostgreSQL"}.issubset(set(stack))
    assert scraper.estimate_seniority("Vaga Sênior Python") == "senior"
