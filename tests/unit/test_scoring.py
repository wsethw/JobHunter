from __future__ import annotations

from app.scoring import _canonical_tech, _contains, _seniority_factor, score_job, score_job_detailed
from tests.factories import make_job


def test_score_job_returns_number() -> None:
    job = make_job()
    assert score_job(job, ["Python", "FastAPI", "PostgreSQL"], "senior") > 50


def test_score_job_detailed_explains_reasons() -> None:
    result = score_job_detailed(
        job=make_job(
            remote_type="remote",
            stack=["Python", "FastAPI", "PostgreSQL"],
            description="Python FastAPI PostgreSQL remote",
        ),
        must_have_stack=["Python", "PostgreSQL"],
        nice_to_have_stack=["FastAPI", "Redis"],
        desired_seniority="senior",
        negative_keywords=["frontend only"],
        preferred_location=["remote"],
    )
    assert result.value > 60
    assert "Python" in result.matched_techs
    assert "Redis" in result.missing_techs
    assert result.positive_reasons


def test_seniority_factor_penalizes_incompatible_role() -> None:
    assert _seniority_factor("junior", "senior") == 0.0
    assert _seniority_factor(None, "senior") == 0.85


def test_canonical_tech_and_contains() -> None:
    assert _canonical_tech("Postgres") == "postgresql"
    assert _canonical_tech("Fast API") == "fastapi"
    assert _contains("Senior Python backend", "python")
    assert not _contains("typescript", "script")


def test_negative_keywords_reduce_score() -> None:
    clean = score_job_detailed(
        job=make_job(),
        must_have_stack=["Python"],
        nice_to_have_stack=["FastAPI"],
        desired_seniority="senior",
    )
    penalized = score_job_detailed(
        job=make_job(description="Python FastAPI frontend only presencial obrigatório"),
        must_have_stack=["Python"],
        nice_to_have_stack=["FastAPI"],
        desired_seniority="senior",
        negative_keywords=["frontend only", "presencial obrigatório"],
    )
    assert penalized.value < clean.value
