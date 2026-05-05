from __future__ import annotations

import pytest

from app.config import Settings, parse_list, redact_url


def test_parse_list_csv_and_json() -> None:
    assert parse_list("Python, FastAPI,, PostgreSQL") == ["Python", "FastAPI", "PostgreSQL"]
    assert parse_list('["Python", "Docker"]') == ["Python", "Docker"]


def test_parse_list_invalid_json_raises() -> None:
    with pytest.raises(ValueError, match="Invalid JSON list"):
        parse_list('["Python"')


def test_settings_validates_sources_and_exposes_lists() -> None:
    settings = Settings(_env_file=None, sources_raw="github_backendbr,programathor")
    assert settings.sources == ["github_backendbr", "programathor"]
    assert "Python" in settings.must_have_stack
    assert settings.telegram_enabled is False


def test_settings_rejects_unknown_source() -> None:
    with pytest.raises(ValueError, match="Unknown source"):
        Settings(_env_file=None, sources_raw="unknown")


def test_settings_validates_email_when_enabled() -> None:
    with pytest.raises(ValueError, match="ENABLE_EMAIL"):
        Settings(_env_file=None, enable_email=True)


def test_redacts_secrets() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://user:pass@localhost:5432/db",
        telegram_bot_token="token",
    )
    assert settings.redacted_dict()["telegram_bot_token"] == "***REDACTED***"
    assert redact_url(settings.database_url) == "postgresql+psycopg://user:***@localhost:5432/db"
