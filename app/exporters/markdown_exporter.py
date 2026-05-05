from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


def export_jobs_markdown(
    jobs: Sequence[Mapping[str, Any]],
    path: str | Path = "exports/daily_report.md",
) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# JobHunter Daily Report", ""]
    for index, job in enumerate(jobs, start=1):
        lines.extend(
            [
                f"## {index}. {job.get('title', 'Sem título')}",
                "",
                f"- Empresa: {job.get('company') or 'não informada'}",
                f"- Local: {job.get('location') or 'não informado'}",
                f"- Score: {float(job.get('score') or 0):.2f}",
                f"- Link: {job.get('link')}",
                "",
            ]
        )
    output.write_text("\n".join(lines), encoding="utf-8")
    return output
