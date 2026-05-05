from __future__ import annotations

from app.tasks import _finalize_execution_log


def test_finalize_execution_log_success_and_failure(monkeypatch, mocker) -> None:
    repo = mocker.Mock()
    session = mocker.Mock()

    class Scope:
        def __enter__(self):
            return session

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr("app.tasks.session_scope", lambda: Scope())
    monkeypatch.setattr("app.tasks.ExecutionLogsRepository", lambda _session: repo)

    _finalize_execution_log(
        execution_log_id=1,
        sources_scraped=1,
        jobs_found=2,
        jobs_new=1,
        status="success",
        error_message=None,
    )
    repo.finish_success.assert_called_once()

    _finalize_execution_log(
        execution_log_id=1,
        sources_scraped=0,
        jobs_found=0,
        jobs_new=0,
        status="failed",
        error_message="boom",
    )
    repo.finish_failed.assert_called_once()
