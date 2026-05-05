from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    company: str | None = None
    location: str | None = None
    stack: list[str] = Field(default_factory=list)
    link: str
    source: str
    seniority: str | None = None
    score: float | None = None
    score_reasons: dict[str, Any] | None = None
    remote_type: str | None = None
    contract_type: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    created_at: datetime
    updated_at: datetime


class ExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    started_at: datetime | None = None
    finished_at: datetime | None = None
    sources_scraped: int
    jobs_found: int
    jobs_new: int
    status: str
    error_message: str | None = None
