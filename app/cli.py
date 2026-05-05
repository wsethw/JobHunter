from __future__ import annotations

import argparse
import json
import logging
from typing import Any

from app.config import get_settings, setup_logging
from app.db import session_scope
from app.exporters import export_jobs_csv, export_jobs_json, export_jobs_markdown
from app.notifier import Notifier
from app.repositories import JobsRepository
from app.services import PipelineService

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    setup_logging(settings)
    parser = build_parser()
    args = parser.parse_args(argv)
    result = args.func(args)
    if result is not None:
        print(json.dumps(result, default=str, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate-config")
    validate.set_defaults(func=validate_config)

    run_once = subparsers.add_parser("run-once")
    run_once.add_argument("--dry-run", action="store_true")
    run_once.set_defaults(func=run_once_command)

    notify = subparsers.add_parser("test-notification")
    notify.set_defaults(func=test_notification)

    list_jobs = subparsers.add_parser("list-jobs")
    list_jobs.add_argument("--limit", type=int, default=10)
    list_jobs.set_defaults(func=list_jobs_command)

    export = subparsers.add_parser("export")
    export.add_argument("--format", choices=["csv", "json", "markdown"], required=True)
    export.add_argument("--limit", type=int, default=100)
    export.set_defaults(func=export_command)
    return parser


def validate_config(_args: argparse.Namespace) -> dict[str, Any]:
    return {"status": "ok", "settings": get_settings().redacted_dict()}


def run_once_command(args: argparse.Namespace) -> dict[str, Any]:
    return PipelineService(settings=get_settings()).run(task_id="cli", dry_run=args.dry_run)


def test_notification(_args: argparse.Namespace) -> dict[str, str]:
    Notifier(get_settings()).send_daily_report([], total_new=0)
    return {"status": "sent_or_skipped"}


def list_jobs_command(args: argparse.Namespace) -> list[dict[str, Any]]:
    with session_scope() as session:
        jobs = JobsRepository(session).list_recent_jobs(limit=args.limit)
        return [job.to_dict() for job in jobs]


def export_command(args: argparse.Namespace) -> dict[str, str]:
    with session_scope() as session:
        jobs = [job.to_dict() for job in JobsRepository(session).list_recent_jobs(limit=args.limit)]
    if args.format == "csv":
        path = export_jobs_csv(jobs)
    elif args.format == "json":
        path = export_jobs_json(jobs)
    else:
        path = export_jobs_markdown(jobs)
    return {"path": str(path)}


if __name__ == "__main__":
    raise SystemExit(main())
