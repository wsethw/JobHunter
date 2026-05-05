from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field

from app.scrapers.base import TECH_ALIASES, Job

logger = logging.getLogger(__name__)

TITLE_WEIGHT = 18.0
STACK_WEIGHT = 12.0
DESCRIPTION_WEIGHT = 5.0


@dataclass(slots=True)
class ScoreResult:
    value: float
    matched_techs: list[str] = field(default_factory=list)
    missing_techs: list[str] = field(default_factory=list)
    seniority_factor: float = 1.0
    positive_reasons: list[str] = field(default_factory=list)
    negative_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def score_job(job: Job, desired_stack: Sequence[str], desired_seniority: str = "senior") -> float:
    """Backward-compatible helper returning only the numeric score."""

    return score_job_detailed(
        job=job,
        must_have_stack=[],
        nice_to_have_stack=desired_stack,
        desired_seniority=desired_seniority,
    ).value


def score_job_detailed(
    *,
    job: Job,
    must_have_stack: Sequence[str],
    nice_to_have_stack: Sequence[str],
    desired_seniority: str = "senior",
    negative_keywords: Sequence[str] | None = None,
    preferred_location: Sequence[str] | None = None,
    remote_only: bool = False,
) -> ScoreResult:
    """Return a 0-100 score plus human-readable reasons."""

    negative_keywords = negative_keywords or []
    preferred_location = preferred_location or []
    must = [_canonical_tech(item) for item in must_have_stack if item.strip()]
    nice = [_canonical_tech(item) for item in nice_to_have_stack if item.strip()]
    desired = _unique(must + nice)

    if not desired:
        logger.warning("No stack configured; score=0 for link=%s", job.link)
        return ScoreResult(value=0.0, negative_reasons=["stack desejada não configurada"])

    title = _normalize(job.title)
    stack_text = _normalize(" ".join(job.stack))
    description = _normalize(job.description or "")
    location = _normalize(job.location or "")
    combined = " ".join([title, stack_text, description, location])

    raw_score = 0.0
    max_score = 0.0
    matched: list[str] = []
    missing: list[str] = []
    positive: list[str] = []
    negative: list[str] = []

    for tech in desired:
        required = tech in must
        multiplier = 1.35 if required else 1.0
        tech_score = 0.0
        max_score += (TITLE_WEIGHT + STACK_WEIGHT + DESCRIPTION_WEIGHT) * multiplier
        aliases = TECH_ALIASES.get(tech, [tech])

        if any(_contains(title, alias) for alias in aliases):
            tech_score += TITLE_WEIGHT * multiplier
        if any(_contains(stack_text, alias) for alias in aliases):
            tech_score += STACK_WEIGHT * multiplier
        if any(_contains(description, alias) for alias in aliases):
            tech_score += DESCRIPTION_WEIGHT * multiplier

        if tech_score > 0:
            matched.append(_display_tech(tech))
            raw_score += min(
                tech_score, (TITLE_WEIGHT + STACK_WEIGHT + DESCRIPTION_WEIGHT) * multiplier
            )
        else:
            missing.append(_display_tech(tech))

    if matched:
        positive.append(f"encontrou {', '.join(matched)}")
    if missing:
        negative.append(f"não encontrou {', '.join(missing)}")

    missing_must = [
        _display_tech(tech) for tech in must if tech in {_canonical_tech(item) for item in missing}
    ]
    if missing_must:
        negative.append(f"faltam tecnologias obrigatórias: {', '.join(missing_must)}")

    base_score = (raw_score / max_score) * 100.0 if max_score else 0.0

    seniority_factor = _seniority_factor(job.seniority, desired_seniority)
    if seniority_factor == 1:
        positive.append(f"senioridade compatível: {job.seniority or 'não informada'}")
    elif seniority_factor == 0:
        negative.append(f"senioridade incompatível: {job.seniority or 'não informada'}")
    else:
        negative.append(f"senioridade com penalidade: {job.seniority or 'não informada'}")

    contextual_bonus = 0.0
    contextual_penalty = 0.0
    remote_type = _normalize(job.remote_type or "")
    if remote_only and remote_type not in {"remote", "remoto"} and "remot" not in combined:
        contextual_penalty += 20.0
        negative.append("vaga não parece remota")
    elif remote_type in {"remote", "remoto"} or "remot" in combined:
        contextual_bonus += 7.0
        positive.append("vaga remota")

    if preferred_location and any(
        _contains(combined, location_item) for location_item in preferred_location
    ):
        contextual_bonus += 4.0
        positive.append("localização aderente à preferência")

    if job.salary_min or job.salary_max:
        contextual_bonus += 4.0
        positive.append("salário informado")
    else:
        contextual_penalty += 3.0
        negative.append("salário não informado")

    for keyword in negative_keywords:
        if keyword and _contains(combined, keyword):
            contextual_penalty += 12.0
            negative.append(f"palavra negativa encontrada: {keyword}")

    if missing_must:
        contextual_penalty += 25.0

    final_score = base_score * seniority_factor + contextual_bonus - contextual_penalty
    final_score = max(0.0, min(100.0, final_score))

    result = ScoreResult(
        value=round(final_score, 2),
        matched_techs=matched,
        missing_techs=missing,
        seniority_factor=seniority_factor,
        positive_reasons=_unique(positive),
        negative_reasons=_unique(negative),
    )
    logger.info(
        "Scored job link=%s score=%.2f matched=%s missing=%s",
        job.link,
        result.value,
        result.matched_techs,
        result.missing_techs,
    )
    return result


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
    return matrix.get(desired, {}).get(found, 0.5)


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


def _display_tech(canonical: str) -> str:
    return {
        "aws": "AWS",
        "gcp": "GCP",
        "ci/cd": "CI/CD",
        "node.js": "Node.js",
        "sqlalchemy": "SQLAlchemy",
        "postgresql": "PostgreSQL",
        "fastapi": "FastAPI",
        "graphql": "GraphQL",
    }.get(canonical, canonical.title())


def _unique(items: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.lower()
        if key not in seen:
            result.append(item)
            seen.add(key)
    return result
