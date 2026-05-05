from __future__ import annotations

from app.scrapers.programathor import ProgramathorScraper


def test_collect_job_links(settings, fixture_path) -> None:
    html = (fixture_path / "programathor_job_page.html").read_text(encoding="utf-8")
    links = ProgramathorScraper(settings)._collect_job_links(html)
    assert links == ["https://programathor.com.br/jobs/123-python-backend-senior"]


def test_parse_detail_html(settings, fixture_path) -> None:
    html = (fixture_path / "programathor_job_page.html").read_text(encoding="utf-8")
    job = ProgramathorScraper(settings).parse_detail_html(
        html,
        "https://programathor.com.br/jobs/123-python-backend-senior",
    )
    assert job is not None
    assert job.company == "ACME Tech"
    assert job.seniority == "senior"
    assert job.contract_type == "pj"
    assert job.remote_type == "remote"
    assert "FastAPI" in job.stack


def test_scrape_detail_uses_page_fixture(settings, fixture_path) -> None:
    html = (fixture_path / "programathor_job_page.html").read_text(encoding="utf-8")

    class FakePage:
        def goto(self, *_args, **_kwargs) -> None:
            return None

        def wait_for_timeout(self, *_args, **_kwargs) -> None:
            return None

        def content(self) -> str:
            return html

    job = ProgramathorScraper(settings)._scrape_detail(
        FakePage(),
        "https://programathor.com.br/jobs/123-python-backend-senior",
    )
    assert job is not None
    assert job.title == "Desenvolvedor Python Backend Senior"
