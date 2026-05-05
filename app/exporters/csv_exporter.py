from __future__ import annotations

import csv
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


def export_jobs_csv(
    jobs: Sequence[Mapping[str, Any]], path: str | Path = "exports/jobs.csv"
) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = ["id", "title", "company", "location", "source", "score", "seniority", "link"]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(jobs)
    return output
