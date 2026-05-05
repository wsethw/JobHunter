from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import executions, health, jobs

app = FastAPI(title="JobHunter API", version="1.0.0")
app.include_router(health.router)
app.include_router(jobs.router)
app.include_router(executions.router)
