from __future__ import annotations

import logging
import re
from collections.abc import Iterable

logger = logging.getLogger(__name__)


def parse_contract_type(texts: Iterable[str | None]) -> str | None:
    text = " ".join((item or "").lower() for item in texts)
    patterns = [
        ("pj", r"\b(pj|pessoa jurídica|pessoa juridica)\b"),
        ("clt", r"\bclt\b"),
        ("freelancer", r"\b(freela|freelancer|contractor)\b"),
        ("internship", r"\b(estágio|estagio|internship)\b"),
    ]
    for value, pattern in patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            logger.debug("Parsed contract_type=%s", value)
            return value
    return None
