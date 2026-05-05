# Architecture

JobHunter is organized around a small Celery entrypoint and a service-oriented application core.

```mermaid
flowchart LR
    Beat[Celery Beat] --> Worker[Celery Worker]
    Worker --> Pipeline[PipelineService]
    Pipeline --> Scraping[ScrapingService]
    Pipeline --> Scoring[ScoringService]
    Pipeline --> JobsRepo[JobsRepository]
    Pipeline --> LogsRepo[ExecutionLogsRepository]
    Pipeline --> Notify[NotificationService]
    Scraping --> GitHub[GitHub API]
    Scraping --> Programathor[ProgramaThor]
    Scraping --> LinkedIn[LinkedIn]
    JobsRepo --> Postgres[(PostgreSQL)]
    LogsRepo --> Postgres
    Notify --> Telegram[Telegram]
```

The Celery task only calls `PipelineService.run()`. Scrapers return normalized Pydantic `Job` objects. Services enrich and score jobs. Repositories own persistence and Alembic owns schema evolution.
