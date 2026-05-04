from __future__ import annotations

import logging
import os
from functools import lru_cache
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6_1) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:124.0) Gecko/20100101 Firefox/124.0",
]

DEFAULT_DESIRED_STACK = "Python,Django,FastAPI,PostgreSQL,Docker,AWS,Celery,Redis,SQLAlchemy"


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables and .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "local"
    log_level: str = "INFO"
    log_dir: str = "logs"
    timezone: str = "America/Sao_Paulo"

    schedule_hour: int = Field(default=8, ge=0, le=23)
    schedule_minute: int = Field(default=0, ge=0, le=59)

    database_url: str = "postgresql+psycopg://jobhunter:jobhunter@postgres:5432/jobhunter"
    redis_url: str = "redis://redis:6379/0"

    sources_raw: str = Field(
        default="github_backendbr,programathor,linkedin",
        validation_alias=AliasChoices("SOURCES", "sources"),
    )
    job_search_query: str = "python backend"
    job_search_location: str = "Brazil"
    max_jobs_per_source: int = Field(default=30, ge=1, le=100)
    playwright_timeout_ms: int = Field(default=30_000, ge=5_000, le=120_000)
    github_since_days: int = Field(default=14, ge=1, le=90)
    github_token: str | None = None

    desired_stack_raw: str = Field(
        default=DEFAULT_DESIRED_STACK,
        validation_alias=AliasChoices("DESIRED_STACK", "desired_stack"),
    )
    desired_seniority: str = "senior"
    min_score_to_notify: float = Field(default=1.0, ge=0.0, le=100.0)

    telegram_bot_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("TELEGRAM_BOT_TOKEN", "TELEGRAM_TOKEN"),
    )
    telegram_chat_id: str | None = None

    enable_email: bool = False
    email_host: str | None = None
    email_port: int = 587
    email_use_tls: bool = True
    email_username: str | None = None
    email_password: str | None = None
    email_from: str | None = None
    email_to: str | None = None

    user_agents_raw: str | None = Field(
        default=None,
        validation_alias=AliasChoices("USER_AGENTS", "user_agents"),
    )

    @field_validator("desired_seniority")
    @classmethod
    def normalize_seniority(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"junior", "pleno", "senior", "any"}:
            raise ValueError("DESIRED_SENIORITY must be junior, pleno, senior or any")
        return normalized

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    @property
    def email_enabled(self) -> bool:
        required = [self.email_host, self.email_from, self.email_to]
        return self.enable_email and all(required)

    @property
    def sources(self) -> list[str]:
        return parse_list(self.sources_raw)

    @property
    def desired_stack(self) -> list[str]:
        return parse_list(self.desired_stack_raw)

    @property
    def user_agents(self) -> list[str]:
        parsed = parse_list(self.user_agents_raw or "")
        return parsed or DEFAULT_USER_AGENTS.copy()


def parse_list(value: str) -> list[str]:
    cleaned = value.strip()
    if not cleaned:
        return []
    if cleaned.startswith("["):
        import json

        return [str(item).strip() for item in json.loads(cleaned) if str(item).strip()]
    return [item.strip() for item in cleaned.split(",") if item.strip()]


def setup_logging(settings: Settings | None = None) -> None:
    """Configure console and daily rotating file logging once per process."""

    settings = settings or get_settings()
    root = logging.getLogger()
    if getattr(root, "_jobhunter_logging_configured", False):
        return

    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    root.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    root.addHandler(console_handler)

    log_dir = Path(settings.log_dir)
    if not log_dir.is_absolute():
        log_dir = Path(os.getcwd()) / log_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    file_handler = TimedRotatingFileHandler(
        filename=log_dir / "jobhunter.log",
        when="midnight",
        interval=1,
        backupCount=14,
        encoding="utf-8",
        utc=False,
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    root.addHandler(file_handler)

    setattr(root, "_jobhunter_logging_configured", True)
    logger.info("Logging configured with level=%s log_dir=%s", settings.log_level, log_dir)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    logger.debug("Settings loaded for app_env=%s", settings.app_env)
    return settings
