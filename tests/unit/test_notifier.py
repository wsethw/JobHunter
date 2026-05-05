from __future__ import annotations

import smtplib

import pytest
import requests

from app.config import Settings
from app.exceptions import NotificationConfigError, NotificationError
from app.notifier import Notifier, split_telegram_message


def test_format_daily_report_escapes_html(settings) -> None:
    message = Notifier(settings).format_daily_report(
        [
            {
                "title": "<script>alert(1)</script>",
                "company": "ACME & Co",
                "location": "Remote",
                "link": "https://example.com",
                "score": 86.5,
                "score_reasons": {"positive_reasons": ["encontrou Python"], "negative_reasons": []},
            }
        ],
        total_new=1,
    )
    assert "&lt;script&gt;" in message
    assert "Score: 86.50" in message


def test_send_telegram_with_mock(mocker) -> None:
    settings = Settings(
        _env_file=None,
        enable_telegram=True,
        telegram_bot_token="token",
        telegram_chat_id="123",
    )
    response = mocker.Mock()
    response.raise_for_status.return_value = None
    post = mocker.patch("app.notifier.requests.post", return_value=response)
    Notifier(settings)._send_telegram("hello")
    assert post.call_count == 1


def test_send_telegram_missing_config_raises(settings) -> None:
    with pytest.raises(NotificationConfigError):
        Notifier(settings)._send_telegram("hello")


def test_send_telegram_http_error_raises(mocker) -> None:
    settings = Settings(
        _env_file=None,
        enable_telegram=True,
        telegram_bot_token="token",
        telegram_chat_id="123",
    )
    response = mocker.Mock()
    response.raise_for_status.side_effect = requests.HTTPError("boom")
    mocker.patch("app.notifier.requests.post", return_value=response)
    with pytest.raises(NotificationError):
        Notifier(settings)._send_telegram("hello")


def test_send_email_with_mock(mocker) -> None:
    settings = Settings(
        _env_file=None,
        enable_email=True,
        email_host="smtp.example.com",
        email_from="bot@example.com",
        email_to="me@example.com",
    )
    smtp = mocker.MagicMock()
    mocker.patch("app.notifier.smtplib.SMTP", return_value=smtp)
    Notifier(settings)._send_email("<b>Hello</b>")
    smtp.__enter__.return_value.send_message.assert_called_once()


def test_send_email_failure_raises(mocker) -> None:
    settings = Settings(
        _env_file=None,
        enable_email=True,
        email_host="smtp.example.com",
        email_from="bot@example.com",
        email_to="me@example.com",
    )
    mocker.patch("app.notifier.smtplib.SMTP", side_effect=smtplib.SMTPException("fail"))
    with pytest.raises(NotificationError):
        Notifier(settings)._send_email("<b>Hello</b>")


def test_split_telegram_message() -> None:
    chunks = split_telegram_message("x\n" * 5000)
    assert len(chunks) > 1
