from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from decimal import Decimal

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SalaryInfo:
    salary_min: Decimal | None = None
    salary_max: Decimal | None = None
    salary_currency: str | None = None


def parse_salary(text: str | None) -> SalaryInfo:
    if not text:
        return SalaryInfo()
    normalized = text.replace("\xa0", " ")
    currency = _parse_currency(normalized)
    values: list[Decimal] = []
    for match in re.findall(
        r"(?:R\$|\$|USD|BRL)?\s*(\d[\d\.,]{2,})(?:\s*k)?", normalized, flags=re.I
    ):
        value = _parse_number(match)
        if value is not None:
            values.append(value)
    if not values:
        logger.debug("No salary parsed")
        return SalaryInfo()
    if len(values) == 1:
        return SalaryInfo(salary_min=values[0], salary_max=values[0], salary_currency=currency)
    return SalaryInfo(salary_min=min(values), salary_max=max(values), salary_currency=currency)


def _parse_currency(text: str) -> str | None:
    lower = text.lower()
    if "usd" in lower or "us$" in lower:
        return "USD"
    if "brl" in lower or "r$" in lower:
        return "BRL"
    if "$" in lower:
        return "USD"
    return None


def _parse_number(raw: str) -> Decimal | None:
    compact = raw.strip().lower()
    multiplier = Decimal("1000") if compact.endswith("k") else Decimal("1")
    compact = compact.rstrip("k")
    if "," in compact and "." in compact:
        compact = compact.replace(".", "").replace(",", ".")
    elif "," in compact:
        compact = compact.replace(",", ".")
    try:
        value = Decimal(compact) * multiplier
    except Exception:
        return None
    if value < 100:
        value *= Decimal("1000")
    return value.quantize(Decimal("0.01"))
