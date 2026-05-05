from __future__ import annotations

from app.deduplicator import Deduplicator, generate_content_hash, generate_job_fingerprint
from app.models import Job as JobModel
from tests.factories import make_job


def test_generate_fingerprint_is_stable_for_small_variations() -> None:
    first = make_job(title="Dev Python Sênior")
    second = make_job(title="Dev Python Senior", link="https://example.com/jobs/2")
    assert generate_job_fingerprint(first) == generate_job_fingerprint(second)


def test_generate_content_hash_changes_with_description() -> None:
    assert generate_content_hash(make_job()) != generate_content_hash(
        make_job(description="Other text")
    )


def test_existing_links(db_session) -> None:
    db_session.add(
        JobModel(
            title="Senior Python",
            link="https://example.com/jobs/1",
            source="test",
            stack=["Python"],
        )
    )
    db_session.commit()
    deduplicator = Deduplicator(db_session)
    assert deduplicator.existing_links(["https://example.com/jobs/1"], recent_only=False) == {
        "https://example.com/jobs/1"
    }


def test_filter_new_deduplicates_link_fingerprint_and_database(db_session) -> None:
    existing = make_job(link="https://example.com/jobs/existing")
    db_session.add(
        JobModel(
            title=existing.title,
            company=existing.company,
            location=existing.location,
            stack=existing.stack,
            link=existing.link,
            source=existing.source,
            fingerprint=generate_job_fingerprint(existing),
            content_hash=generate_content_hash(existing),
        )
    )
    db_session.commit()
    jobs = [
        existing,
        make_job(link="https://example.com/jobs/2", company="OtherCo"),
        make_job(link="https://example.com/jobs/2?utm_source=x", company="OtherCo"),
        make_job(link="https://other-source.test/jobs/abc", company="OtherCo"),
    ]
    new_jobs = Deduplicator(db_session).filter_new(jobs)
    assert len(new_jobs) == 1
