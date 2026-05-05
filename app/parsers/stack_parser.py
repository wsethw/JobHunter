from __future__ import annotations

import logging
import re
from collections.abc import Iterable

from app.scrapers.base import TECH_ALIASES

logger = logging.getLogger(__name__)


DISPLAY_NAMES = {
    "aws": "AWS",
    "gcp": "GCP",
    "ci/cd": "CI/CD",
    "node.js": "Node.js",
    "sqlalchemy": "SQLAlchemy",
    "postgresql": "PostgreSQL",
    "graphql": "GraphQL",
    "rabbitmq": "RabbitMQ",
    "fastapi": "FastAPI",
}


def parse_stack(texts: Iterable[str | None], extra_terms: Iterable[str] | None = None) -> list[str]:
    combined = " ".join(_normalize(text or "") for text in texts)
    candidates = set(TECH_ALIASES.keys())
    if extra_terms:
        candidates.update(term.lower().strip() for term in extra_terms if term.strip())

    found: list[str] = []
    seen: set[str] = set()
    for canonical in sorted(candidates):
        aliases = TECH_ALIASES.get(canonical, [canonical])
        if any(_contains(combined, alias) for alias in aliases):
            display = DISPLAY_NAMES.get(canonical, canonical.title())
            if display.lower() not in seen:
                found.append(display)
                seen.add(display.lower())

    logger.debug("Parsed stack=%s", found)
    return found


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _contains(text: str, term: str) -> bool:
    escaped = re.escape(_normalize(term)).replace("\\ ", r"\s+")
    return bool(re.search(rf"(?<![\w+#.]){escaped}(?![\w+#.])", text, flags=re.IGNORECASE))
