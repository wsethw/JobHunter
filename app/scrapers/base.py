from __future__ import annotations

import logging
import random
import re
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import Settings

logger = logging.getLogger(__name__)


TECH_ALIASES: dict[str, list[str]] = {
    "python": ["python", "python3"],
    "django": ["django", "django rest framework", "drf"],
    "fastapi": ["fastapi", "fast api"],
    "flask": ["flask"],
    "postgresql": ["postgresql", "postgres", "postgre sql"],
    "mysql": ["mysql", "mariadb"],
    "mongodb": ["mongodb", "mongo db"],
    "redis": ["redis"],
    "celery": ["celery"],
    "docker": ["docker", "docker-compose", "docker compose"],
    "kubernetes": ["kubernetes", "k8s"],
    "aws": ["aws", "amazon web services", "lambda", "ecs", "eks", "s3"],
    "gcp": ["gcp", "google cloud"],
    "azure": ["azure"],
    "sqlalchemy": ["sqlalchemy", "sql alchemy"],
    "pytest": ["pytest", "py test"],
    "rest": ["rest", "restful", "api rest"],
    "graphql": ["graphql", "graph ql"],
    "rabbitmq": ["rabbitmq", "rabbit mq"],
    "kafka": ["kafka", "apache kafka"],
    "linux": ["linux", "unix"],
    "git": ["git", "github", "gitlab"],
    "ci/cd": ["ci/cd", "ci cd", "continuous integration", "continuous delivery"],
    "javascript": ["javascript", "js"],
    "typescript": ["typescript", "ts"],
    "node.js": ["node.js", "nodejs", "node js"],
    "java": ["java"],
    "go": ["golang", "go"],
    "php": ["php"],
}

SENIORITY_KEYWORDS: dict[str, list[str]] = {
    "junior": ["junior", "júnior", "jr", "trainee", "estagio", "estágio", "entry level"],
    "pleno": ["pleno", "mid-level", "mid level", "midlevel", "intermediario", "intermediário"],
    "senior": [
        "senior",
        "sênior",
        "sr",
        "especialista",
        "specialist",
        "lead",
        "staff",
        "principal",
    ],
}


class Job(BaseModel):
    """Normalized job object returned by every scraper before persistence."""

    model_config = ConfigDict(str_strip_whitespace=True, arbitrary_types_allowed=True)

    title: str = Field(min_length=2, max_length=300)
    company: str | None = Field(default=None, max_length=200)
    location: str | None = Field(default=None, max_length=200)
    stack: list[str] = Field(default_factory=list)
    link: str = Field(min_length=8, max_length=500)
    source: str = Field(min_length=2, max_length=100)
    external_id: str | None = Field(default=None, max_length=200)
    published_at: datetime | None = None
    seniority: str | None = Field(default=None, max_length=50)
    salary_min: Decimal | None = None
    salary_max: Decimal | None = None
    salary_currency: str | None = Field(default=None, max_length=10)
    contract_type: str | None = Field(default=None, max_length=50)
    remote_type: str | None = Field(default=None, max_length=50)
    country: str | None = Field(default=None, max_length=100)
    city: str | None = Field(default=None, max_length=120)
    raw_payload: dict[str, Any] = Field(default_factory=dict, exclude=True)
    description: str | None = Field(default=None, exclude=True)

    @field_validator("link")
    @classmethod
    def validate_link(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("link must be an absolute HTTP/HTTPS URL")
        return value

    @field_validator("stack")
    @classmethod
    def normalize_stack(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        normalized: list[str] = []
        for item in value:
            cleaned = str(item).strip()
            if not cleaned:
                continue
            key = cleaned.lower()
            if key not in seen:
                normalized.append(cleaned)
                seen.add(key)
        return normalized


class BaseScraper(ABC):
    """Common scraper contract and text normalization helpers."""

    name: str = "base"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        logger.debug("%s initialized", self.__class__.__name__)

    @abstractmethod
    def scrape(self) -> list[Job]:
        """Return normalized job listings."""

    def choose_user_agent(self) -> str:
        user_agent = random.choice(self.settings.user_agents)
        logger.debug("%s selected user-agent=%s", self.name, user_agent)
        return user_agent

    def save_artifact(self, name: str, content: str | bytes, suffix: str = ".html") -> Path:
        artifact_dir = Path(self.settings.scraper_artifacts_dir)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^a-zA-Z0-9_.-]+", "-", name).strip("-") or "artifact"
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        path = artifact_dir / f"{self.name}-{safe_name}-{timestamp}{suffix}"
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
        logger.info("%s saved scraper artifact path=%s", self.name, path)
        return path

    def canonicalize_url(self, url: str) -> str:
        """Normalize URLs enough to support deterministic link deduplication."""

        parsed = urlparse(url.strip())
        tracking_params = {
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_term",
            "utm_content",
            "trk",
            "trackingId",
            "refId",
            "position",
            "pageNum",
        }
        query = [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=False)
            if key not in tracking_params
        ]
        normalized_path = parsed.path.rstrip("/") or parsed.path
        canonical = urlunparse(
            (
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                normalized_path,
                "",
                urlencode(query),
                "",
            )
        )
        logger.debug("%s canonicalized url=%s", self.name, canonical)
        return canonical

    def normalize_text(self, value: str | None) -> str:
        if not value:
            return ""
        return re.sub(r"\s+", " ", value).strip()

    def detect_stack(self, *texts: str | None) -> list[str]:
        combined = " ".join(self.normalize_text(text).lower() for text in texts if text)
        detected: list[str] = []
        seen: set[str] = set()
        candidates = set(TECH_ALIASES.keys())
        candidates.update(tech.lower() for tech in self.settings.desired_stack)

        for canonical in sorted(candidates):
            aliases = TECH_ALIASES.get(canonical, [canonical])
            if any(self._contains_term(combined, alias.lower()) for alias in aliases):
                display = self._display_technology(canonical)
                if display.lower() not in seen:
                    detected.append(display)
                    seen.add(display.lower())

        logger.debug("%s detected stack=%s", self.name, detected)
        return detected

    def estimate_seniority(self, *texts: str | None) -> str | None:
        combined = " ".join(self.normalize_text(text).lower() for text in texts if text)
        if not combined:
            return None
        positions: dict[str, int] = {}
        for seniority, keywords in SENIORITY_KEYWORDS.items():
            indexes = [
                combined.find(keyword)
                for keyword in keywords
                if self._contains_term(combined, keyword.lower())
            ]
            if indexes:
                positions[seniority] = min(index for index in indexes if index >= 0)
        if not positions:
            return None
        estimated = min(positions, key=lambda key: positions[key])
        logger.debug("%s estimated seniority=%s", self.name, estimated)
        return estimated

    def build_job(
        self,
        *,
        title: str,
        link: str,
        company: str | None = None,
        location: str | None = None,
        stack: list[str] | None = None,
        published_at: datetime | None = None,
        seniority: str | None = None,
        description: str | None = None,
        extra_text: str | None = None,
        external_id: str | None = None,
        salary_min: Decimal | None = None,
        salary_max: Decimal | None = None,
        salary_currency: str | None = None,
        contract_type: str | None = None,
        remote_type: str | None = None,
        country: str | None = None,
        city: str | None = None,
        raw_payload: dict[str, Any] | None = None,
    ) -> Job:
        normalized_title = self.normalize_text(title)
        normalized_company = self.normalize_text(company) or None
        normalized_location = self.normalize_text(location) or None
        normalized_description = self.normalize_text(description) or None
        detected_stack = stack or self.detect_stack(title, description, extra_text)
        estimated_seniority = seniority or self.estimate_seniority(title, description, extra_text)

        job = Job(
            title=normalized_title,
            company=normalized_company,
            location=normalized_location,
            stack=detected_stack,
            link=self.canonicalize_url(link),
            source=self.name,
            external_id=external_id,
            published_at=published_at,
            seniority=estimated_seniority,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=salary_currency,
            contract_type=contract_type,
            remote_type=remote_type,
            country=country,
            city=city,
            raw_payload=raw_payload or {},
            description=normalized_description,
        )
        logger.info(
            "%s normalized job title=%r company=%r seniority=%r stack=%s",
            self.name,
            job.title,
            job.company,
            job.seniority,
            job.stack,
        )
        return job

    def _contains_term(self, text: str, term: str) -> bool:
        escaped = re.escape(term).replace("\\ ", r"\s+")
        return bool(re.search(rf"(?<![\w+#.]){escaped}(?![\w+#.])", text, flags=re.IGNORECASE))

    def _display_technology(self, canonical: str) -> str:
        preferred = {
            "aws": "AWS",
            "gcp": "GCP",
            "ci/cd": "CI/CD",
            "node.js": "Node.js",
        }
        if canonical in preferred:
            return preferred[canonical]
        if canonical in {"sqlalchemy", "postgresql", "graphql", "rabbitmq", "fastapi"}:
            return {
                "sqlalchemy": "SQLAlchemy",
                "postgresql": "PostgreSQL",
                "graphql": "GraphQL",
                "rabbitmq": "RabbitMQ",
                "fastapi": "FastAPI",
            }[canonical]
        return canonical.title()

    @staticmethod
    def safe_datetime(value: Any) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            from dateutil.parser import isoparse

            return isoparse(str(value))
        except Exception:
            logger.debug("Could not parse datetime value=%r", value)
            return None
