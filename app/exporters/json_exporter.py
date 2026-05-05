from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any


def export_jobs_json(
    jobs: Sequence[Mapping[str, Any]], path: str | Path = "exports/jobs.json"
) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(list(jobs), default=_json_default, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output


def _json_default(value: Any) -> str | float:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return str(value)
