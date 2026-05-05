from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LocationInfo:
    remote_type: str | None = None
    country: str | None = None
    city: str | None = None
    normalized_location: str | None = None


def parse_location(location: str | None, description: str | None = None) -> LocationInfo:
    text = " ".join(part for part in [location, description] if part).lower()
    remote_type = _parse_remote_type(text)
    country = _parse_country(text, location)
    city = _parse_city(location)
    normalized = _normalize_location(location, remote_type)
    result = LocationInfo(
        remote_type=remote_type, country=country, city=city, normalized_location=normalized
    )
    logger.debug("Parsed location=%s", result)
    return result


def _parse_remote_type(text: str) -> str | None:
    if re.search(r"\b(100%\s*remoto|remoto|remote|home office|anywhere)\b", text):
        return "remote"
    if re.search(r"\b(híbrido|hibrido|hybrid)\b", text):
        return "hybrid"
    if re.search(r"\b(presencial|on[- ]?site)\b", text):
        return "onsite"
    return None


def _parse_country(text: str, location: str | None) -> str | None:
    if re.search(r"\b(brasil|brazil|br)\b", text):
        return "Brazil"
    if location and "," in location:
        country = location.split(",")[-1].strip()
        return country or None
    return None


def _parse_city(location: str | None) -> str | None:
    if not location:
        return None
    first = re.split(r"[,/|-]", location, maxsplit=1)[0].strip()
    if first and first.lower() not in {"remoto", "remote", "brasil", "brazil"}:
        return first[:120]
    return None


def _normalize_location(location: str | None, remote_type: str | None) -> str | None:
    if location and location.strip():
        return re.sub(r"\s+", " ", location).strip()
    if remote_type == "remote":
        return "Remote"
    if remote_type == "hybrid":
        return "Hybrid"
    if remote_type == "onsite":
        return "On-site"
    return None
