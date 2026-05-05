from __future__ import annotations

import json
import logging
import os
import re
from functools import lru_cache
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from pydantic import AliasChoices, Field, field_validator, model_validator
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
VALID_SOURCES = {"github_backendbr", "programathor", "linkedin"}
SECRET_FIELD_PATTERNS = re.compile("token|password|secret|basic_auth|database_url|redis_url", re.I)


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables and .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        populate_by_name=True,
        extra="ignore",
    )

    app_env: str = "local"
    log_level: str = "INFO"
    log_dir: str = "logs"
    timezone: str = "America/Sao_Paulo"

    schedule_hour: int = Field(default=8, ge=0, le=23)
    schedule_minute: int = Field(default=0, ge=0, le=59)

    database_url: str = "postgresql+psycopg://jobhunter:jobhunter@postgres:5432/jobhunter"
    database_url_test: str = (
        "postgresql+psycopg://jobhunter:jobhunter@localhost:5432/jobhunter_test"
    )
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
    must_have_stack_raw: str = Field(
        default="Python,PostgreSQL",
        validation_alias=AliasChoices("MUST_HAVE_STACK", "must_have_stack"),
    )
    nice_to_have_stack_raw: str = Field(
        default="FastAPI,Docker,AWS,Redis,Celery",
        validation_alias=AliasChoices("NICE_TO_HAVE_STACK", "nice_to_have_stack"),
    )
    negative_keywords_raw: str = Field(
        default="estágio,frontend only,presencial obrigatório",
        validation_alias=AliasChoices("NEGATIVE_KEYWORDS", "negative_keywords"),
    )
    preferred_location_raw: str = Field(
        default="remote,brazil",
        validation_alias=AliasChoices("PREFERRED_LOCATION", "preferred_location"),
    )
    desired_seniority: str = "senior"
    remote_only: bool = False
    min_score_to_notify: float = Field(default=50.0, ge=0.0, le=100.0)

    enable_telegram: bool = False
    telegram_bot_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("TELEGRAM_BOT_TOKEN", "TELEGRAM_TOKEN"),
    )
    telegram_chat_id: str | None = None
    telegram_parse_mode: str = "HTML"

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
    send_empty_report: bool = False
    scraper_artifacts_dir: str = "logs/artifacts"
    enable_playwright_tracing: bool = False
    respect_robots_txt: bool = False
    scraper_rate_limit_seconds: float = Field(default=1.0, ge=0.0, le=60.0)
    flower_basic_auth: str | None = None

    @field_validator("desired_seniority")
    @classmethod
    def normalize_seniority(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"junior", "pleno", "senior", "any"}:
            raise ValueError("DESIRED_SENIORITY must be junior, pleno, senior or any")
        return normalized

    @field_validator("sources_raw")
    @classmethod
    def validate_sources(cls, value: str) -> str:
        sources = parse_list(value)
        unknown = sorted(set(sources) - VALID_SOURCES)
        if unknown:
            raise ValueError(
                f"Unknown source(s): {', '.join(unknown)}. Valid: {sorted(VALID_SOURCES)}"
            )
        if not sources:
            raise ValueError("At least one source must be configured in SOURCES")
        return value

    @field_validator("telegram_parse_mode")
    @classmethod
    def validate_parse_mode(cls, value: str) -> str:
        normalized = value.strip()
        if normalized not in {"HTML", "Markdown", "MarkdownV2"}:
            raise ValueError("TELEGRAM_PARSE_MODE must be HTML, Markdown or MarkdownV2")
        return normalized

    @model_validator(mode="after")
    def validate_notification_settings(self) -> Settings:
        if self.enable_telegram and not (self.telegram_bot_token and self.telegram_chat_id):
            raise ValueError(
                "ENABLE_TELEGRAM=true requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID"
            )
        if self.enable_email:
            missing = [
                name for name in ("email_host", "email_from", "email_to") if not getattr(self, name)
            ]
            if missing:
                raise ValueError(f"ENABLE_EMAIL=true requires: {', '.join(missing)}")
        return self

    @property
    def telegram_enabled(self) -> bool:
        return bool(
            (self.enable_telegram or self.telegram_bot_token)
            and self.telegram_bot_token
            and self.telegram_chat_id
        )

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
    def must_have_stack(self) -> list[str]:
        return parse_list(self.must_have_stack_raw)

    @property
    def nice_to_have_stack(self) -> list[str]:
        return parse_list(self.nice_to_have_stack_raw)

    @property
    def negative_keywords(self) -> list[str]:
        return parse_list(self.negative_keywords_raw)

    @property
    def preferred_location(self) -> list[str]:
        return parse_list(self.preferred_location_raw)

    @property
    def user_agents(self) -> list[str]:
        parsed = parse_list(self.user_agents_raw or "")
        return parsed or DEFAULT_USER_AGENTS.copy()

    def redacted_dict(self) -> dict[str, Any]:
        data = self.model_dump()
        data.update(
            {
                "sources": self.sources,
                "desired_stack": self.desired_stack,
                "must_have_stack": self.must_have_stack,
                "nice_to_have_stack": self.nice_to_have_stack,
                "negative_keywords": self.negative_keywords,
                "preferred_location": self.preferred_location,
            }
        )
        return {key: redact_secret(key, value) for key, value in data.items()}


def parse_list(value: str) -> list[str]:
    cleaned = value.strip()
    if not cleaned:
        return []
    if cleaned.startswith("["):
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON list: {exc.msg}") from exc
        if not isinstance(parsed, list):
            raise ValueError("JSON value must be a list")
        return [str(item).strip() for item in parsed if str(item).strip()]
    return [item.strip() for item in cleaned.split(",") if item.strip()]


def redact_secret(key: str, value: Any) -> Any:
    if value is None or value == "":
        return value
    if not SECRET_FIELD_PATTERNS.search(key):
        return value
    if key.lower().endswith("_url") and isinstance(value, str):
        return redact_url(value)
    return "***REDACTED***"


def redact_url(url: str) -> str:
    parts = urlsplit(url)
    if not parts.password and not parts.username:
        return url
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    username = parts.username or "***"
    redacted_netloc = f"{username}:***@{host}"
    return urlunsplit((parts.scheme, redacted_netloc, parts.path, parts.query, parts.fragment))


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

    root.__dict__["_jobhunter_logging_configured"] = True
    logger.info("Logging configured with level=%s log_dir=%s", settings.log_level, log_dir)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    logger.debug("Settings loaded for app_env=%s", settings.app_env)
    return settings
