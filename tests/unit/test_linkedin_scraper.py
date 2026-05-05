from __future__ import annotations

from app.scrapers.linkedin import LinkedInScraper


def test_build_search_url(settings) -> None:
    url = LinkedInScraper(settings)._build_search_url()
    assert "keywords=python+backend" in url
    assert "location=Brazil" in url


def test_parse_card_html(settings, fixture_path) -> None:
    html = (fixture_path / "linkedin_search_card.html").read_text(encoding="utf-8")
    job = LinkedInScraper(settings).parse_card_html(html)
    assert job is not None
    assert job.company == "ACME LinkedIn"
    assert job.external_id == "999"
    assert "Python" in job.stack


def test_parse_card_with_mocked_locator(settings, mocker) -> None:
    scraper = LinkedInScraper(settings)
    mocker.patch.object(scraper, "_safe_inner_text", return_value="Python FastAPI PostgreSQL")
    mocker.patch.object(
        scraper,
        "_safe_locator_text",
        side_effect=["Senior Python Backend Engineer", "ACME", "Remote Brazil"],
    )
    mocker.patch.object(
        scraper,
        "_safe_locator_attr",
        side_effect=["https://www.linkedin.com/jobs/view/123", "2026-05-01T00:00:00Z"],
    )
    job = scraper._parse_card(object())
    assert job is not None
    assert job.external_id == "123"
    assert job.seniority == "senior"


def test_blocked_page_detection(settings) -> None:
    assert LinkedInScraper(settings)._is_blocked_page("<html>captcha checkpoint</html>")
