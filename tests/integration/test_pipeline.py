from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.scrapers.base import BaseScraper, Job
from app.services import PipelineService, ScrapingService
from app.tasks import _build_scrapers, _process_and_store_jobs
from tests.factories import make_job


class FakeScraper(BaseScraper):
    name = "fake"

    def scrape(self) -> list[Job]:
        return [make_job(source=self.name)]


class FakeNotificationService:
    def __init__(self) -> None:
        self.calls = []

    def notify_daily_report(self, jobs, total_new: int) -> str:
        self.calls.append((jobs, total_new))
        return "sent"


def test_pipeline_complete_flow(monkeypatch, settings) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )

    @contextmanager
    def test_session_scope():
        session = SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    monkeypatch.setattr("app.services.pipeline_service.session_scope", test_session_scope)
    notifications = FakeNotificationService()
    pipeline = PipelineService(
        settings=settings,
        scraping_service=ScrapingService(settings, scrapers=[FakeScraper(settings)]),
        notification_service=notifications,
    )
    result = pipeline.run(task_id="test")
    assert result["status"] == "success"
    assert result["jobs_new"] == 1
    assert notifications.calls[0][1] == 1
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_pipeline_dry_run_does_not_notify(settings) -> None:
    notifications = FakeNotificationService()
    pipeline = PipelineService(
        settings=settings,
        scraping_service=ScrapingService(settings, scrapers=[FakeScraper(settings)]),
        notification_service=notifications,
    )
    result = pipeline.run(task_id="dry", dry_run=True)
    assert result["status"] == "dry_run"
    assert notifications.calls == []


def test_task_compatibility_wrappers(monkeypatch, settings) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )

    @contextmanager
    def test_session_scope():
        session = SessionLocal()
        try:
            yield session
            session.commit()
        finally:
            session.close()

    monkeypatch.setattr("app.tasks.session_scope", test_session_scope)
    monkeypatch.setattr("app.tasks.get_settings", lambda: settings)
    top_jobs, affected = _process_and_store_jobs([make_job()])
    assert affected == 1
    assert top_jobs
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_build_scrapers_wrapper(monkeypatch, settings) -> None:
    monkeypatch.setattr("app.tasks.get_settings", lambda: settings)
    scrapers = _build_scrapers()
    assert [scraper.name for scraper in scrapers] == ["github_backendbr", "programathor"]
