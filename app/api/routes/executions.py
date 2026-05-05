from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import desc, select

from app.api.schemas import ExecutionRead
from app.db import session_scope
from app.models import ExecutionLog

router = APIRouter(tags=["executions"])


@router.get("/executions", response_model=list[ExecutionRead])
def list_executions(limit: int = Query(default=25, ge=1, le=100)) -> list[ExecutionLog]:
    with session_scope() as session:
        statement = select(ExecutionLog).order_by(desc(ExecutionLog.started_at)).limit(limit)
        return list(session.execute(statement).scalars().all())
