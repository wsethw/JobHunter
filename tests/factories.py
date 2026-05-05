from __future__ import annotations

from app.scrapers.base import Job


def make_job(**overrides) -> Job:
    data = {
        "title": "Senior Python Backend Engineer",
        "company": "ACME",
        "location": "Remote Brazil",
        "stack": ["Python", "FastAPI", "PostgreSQL", "Docker", "Redis", "Celery"],
        "link": "https://example.com/jobs/1",
        "source": "test",
        "seniority": "senior",
        "description": "Python FastAPI PostgreSQL Docker AWS Redis Celery remote PJ salary R$ 18000",
    }
    data.update(overrides)
    return Job(**data)
