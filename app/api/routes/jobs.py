from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import desc, func, select

from app.api.schemas import JobRead
from app.db import session_scope
from app.models import Job
from app.repositories import JobsRepository

router = APIRouter(tags=["jobs"])


@router.get("/jobs", response_model=list[JobRead])
def list_jobs(limit: int = Query(default=50, ge=1, le=200)) -> list[Job]:
    with session_scope() as session:
        return JobsRepository(session).list_recent_jobs(limit=limit)


@router.get("/jobs/top", response_model=list[JobRead])
def top_jobs(limit: int = Query(default=10, ge=1, le=50), min_score: float = 0) -> list[Job]:
    with session_scope() as session:
        return JobsRepository(session).list_top_jobs(limit=limit, min_score=min_score)


@router.get("/jobs/{job_id}", response_model=JobRead)
def get_job(job_id: int) -> Job:
    with session_scope() as session:
        job = session.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job


@router.get("/metrics/summary")
def metrics_summary() -> dict:
    with session_scope() as session:
        total_jobs = session.scalar(select(func.count(Job.id))) or 0
        top_score = session.scalar(select(func.max(Job.score))) or 0
        last_seen = session.scalar(
            select(Job.last_seen_at).order_by(desc(Job.last_seen_at)).limit(1)
        )
        return {
            "total_jobs": total_jobs,
            "top_score": float(top_score),
            "last_seen_at": last_seen,
        }
