from __future__ import annotations

import logging
import re
from collections.abc import Sequence

from app.scrapers.base import Job, TECH_ALIASES

logger = logging.getLogger(__name__)


TITLE_WEIGHT = 16.0
STACK_WEIGHT = 10.0
DESCRIPTION_WEIGHT = 4.0


def score_job(job: Job, desired_stack: Sequence[str], desired_seniority: str = "senior") -> float:
    """Return a 0-100 compatibility score for a normalized job."""

    if not desired_stack:
        logger.warning("Desired stack is empty; returning score=0 for link=%s", job.link)
        return 0.0

    desired = [_canonical_tech(item) for item in desired_stack if item.strip()]
    if not desired:
        return 0.0

    title = _normalize(job.title)
    stack_text = _normalize(" ".join(job.stack))
    description = _normalize(job.description or "")

    raw_score = 0.0
    max_score = len(desired) * (TITLE_WEIGHT + STACK_WEIGHT + DESCRIPTION_WEIGHT)
    matched_techs: list[str] = []

    for tech in desired:
        aliases = TECH_ALIASES.get(tech, [tech])
        tech_score = 0.0
        if any(_contains(title, alias) for alias in aliases):
            tech_score += TITLE_WEIGHT
        if any(_contains(stack_text, alias) for alias in aliases):
            tech_score += STACK_WEIGHT
        if any(_contains(description, alias) for alias in aliases):
            tech_score += DESCRIPTION_WEIGHT

        if tech_score > 0:
            matched_techs.append(tech)
        raw_score += min(tech_score, TITLE_WEIGHT + STACK_WEIGHT + DESCRIPTION_WEIGHT)

    base_score = (raw_score / max_score) * 100.0
    seniority_factor = _seniority_factor(job.seniority, desired_seniority)
    final_score = max(0.0, min(100.0, base_score * seniority_factor))

    logger.info(
        "Scored job link=%s score=%.2f seniority=%s desired_seniority=%s matched=%s",
        job.link,
        final_score,
        job.seniority,
        desired_seniority,
        matched_techs,
    )
    return round(final_score, 2)


def _seniority_factor(job_seniority: str | None, desired_seniority: str) -> float:
    desired = (desired_seniority or "any").lower()
    found = (job_seniority or "unknown").lower()

    if desired == "any":
        return 1.0
    if found == "unknown":
        return 0.85
    if found == desired:
        return 1.0

    matrix = {
        "senior": {"junior": 0.0, "pleno": 0.65},
        "pleno": {"junior": 0.35, "senior": 0.85},
        "junior": {"pleno": 0.55, "senior": 0.35},
    }
    factor = matrix.get(desired, {}).get(found, 0.5)
    logger.debug("Seniority factor desired=%s found=%s factor=%s", desired, found, factor)
    return factor


def _canonical_tech(value: str) -> str:
    normalized = _normalize(value)
    for canonical, aliases in TECH_ALIASES.items():
        if normalized == canonical or normalized in [_normalize(alias) for alias in aliases]:
            return canonical
    return normalized


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _contains(text: str, term: str) -> bool:
    escaped = re.escape(_normalize(term)).replace("\\ ", r"\s+")
    return bool(re.search(rf"(?<![\w+#.]){escaped}(?![\w+#.])", text, flags=re.IGNORECASE))
