from __future__ import annotations

from app.repositories import JobsRepository
from app.services.scoring_service import ScoringService
from tests.factories import make_job


def test_jobs_repository_upsert_insert_and_update(db_session, settings) -> None:
    repository = JobsRepository(db_session)
    service = ScoringService(settings)
    payload = service.build_payload(make_job())

    assert repository.upsert_jobs([payload]) == 1
    db_session.commit()
    job = repository.list_recent_jobs(limit=1)[0]
    assert job.seen_count == 1

    payload["title"] = "Senior Python Platform Engineer"
    payload["score"] = 99
    assert repository.upsert_jobs([payload]) == 1
    db_session.commit()
    updated = repository.list_recent_jobs(limit=1)[0]
    assert updated.title == "Senior Python Platform Engineer"
    assert updated.seen_count == 2
    assert float(updated.score) == 99.0


def test_repository_helpers(db_session, settings) -> None:
    repository = JobsRepository(db_session)
    job = make_job()
    payload = ScoringService(settings).build_payload(job)
    repository.upsert_jobs([payload])
    db_session.commit()

    assert repository.get_existing_links([job.link]) == {job.link}
    assert repository.list_top_jobs(limit=1)[0].link == job.link
    assert repository.find_duplicates_by_fingerprint(job)
    repository.mark_job_seen(repository.list_recent_jobs(limit=1)[0].id)
    db_session.commit()
    assert repository.list_recent_jobs(limit=1)[0].seen_count == 2
