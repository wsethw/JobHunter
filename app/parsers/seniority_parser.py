from __future__ import annotations

import logging
import re
from collections.abc import Iterable

from app.scrapers.base import SENIORITY_KEYWORDS

logger = logging.getLogger(__name__)


def parse_seniority(texts: Iterable[str | None]) -> str | None:
    combined = " ".join(_normalize(text or "") for text in texts)
    if not combined:
        return None

    positions: dict[str, int] = {}
    for seniority, keywords in SENIORITY_KEYWORDS.items():
        matches = [
            combined.find(keyword.lower()) for keyword in keywords if _contains(combined, keyword)
        ]
        matches = [match for match in matches if match >= 0]
        if matches:
            positions[seniority] = min(matches)

    if not positions:
        logger.debug("No seniority parsed from text")
        return None
    result = min(positions, key=lambda key: positions[key])
    logger.debug("Parsed seniority=%s", result)
    return result


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _contains(text: str, term: str) -> bool:
    escaped = re.escape(_normalize(term)).replace("\\ ", r"\s+")
    return bool(re.search(rf"(?<![\w+#.]){escaped}(?![\w+#.])", text, flags=re.IGNORECASE))
