from __future__ import annotations

import html
import logging
import smtplib
from collections.abc import Mapping, Sequence
from datetime import date
from email.message import EmailMessage
from typing import Any

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import Settings

logger = logging.getLogger(__name__)


class Notifier:
    """Send daily reports through Telegram and optional SMTP e-mail."""

    telegram_api_base = "https://api.telegram.org"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        logger.debug("Notifier initialized telegram=%s email=%s", settings.telegram_enabled, settings.email_enabled)

    def send_daily_report(self, jobs: Sequence[Mapping[str, Any]], total_new: int) -> None:
        if not jobs and total_new == 0:
            logger.info("No new jobs to notify")
        message = self.format_daily_report(jobs, total_new)

        if self.settings.telegram_enabled:
            self._send_telegram(message)
        else:
            logger.warning("Telegram notification skipped because token/chat_id are not configured")

        if self.settings.email_enabled:
            self._send_email(message)
        else:
            logger.info("Email notification skipped because it is disabled or incomplete")

    def format_daily_report(
        self,
        jobs: Sequence[Mapping[str, Any]],
        total_new: int,
        report_date: date | None = None,
    ) -> str:
        current_date = report_date or date.today()
        lines = [f"🤖 <b>JobHunter Daily Report – {current_date:%Y-%m-%d}</b>", ""]

        if jobs:
            for index, job in enumerate(jobs[:10], start=1):
                title = html.escape(str(job.get("title") or "Sem título"))
                company = html.escape(str(job.get("company") or "Empresa não informada"))
                location = html.escape(str(job.get("location") or "Local não informado"))
                link = html.escape(str(job.get("link") or ""))
                score = float(job.get("score") or 0)
                lines.extend(
                    [
                        f"<b>{index}. {title}</b>",
                        f"Empresa: {company}",
                        f"Local: {location}",
                        f"Score: {score:.2f}",
                        f'<a href="{link}">Abrir vaga</a>',
                        "",
                    ]
                )
        else:
            lines.append("Nenhuma vaga nova compatível encontrada nesta execução.")
            lines.append("")

        lines.append(f"Total de vagas novas hoje: {total_new}")
        return "\n".join(lines)

    @retry(
        retry=retry_if_exception_type(requests.RequestException),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _send_telegram(self, message: str) -> None:
        assert self.settings.telegram_bot_token
        assert self.settings.telegram_chat_id

        url = f"{self.telegram_api_base}/bot{self.settings.telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": self.settings.telegram_chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        logger.info("Telegram report sent chat_id=%s", self.settings.telegram_chat_id)

    def _send_email(self, html_message: str) -> None:
        assert self.settings.email_host
        assert self.settings.email_from
        assert self.settings.email_to

        plain_text = (
            html_message.replace("<b>", "")
            .replace("</b>", "")
            .replace("<a href=\"", "")
            .replace("\">Abrir vaga</a>", "")
        )

        message = EmailMessage()
        message["Subject"] = "JobHunter Daily Report"
        message["From"] = self.settings.email_from
        message["To"] = self.settings.email_to
        message.set_content(plain_text)
        message.add_alternative(html_message, subtype="html")

        logger.info("Sending email report to=%s host=%s", self.settings.email_to, self.settings.email_host)
        with smtplib.SMTP(self.settings.email_host, self.settings.email_port, timeout=30) as smtp:
            if self.settings.email_use_tls:
                smtp.starttls()
            if self.settings.email_username and self.settings.email_password:
                smtp.login(self.settings.email_username, self.settings.email_password)
            smtp.send_message(message)
        logger.info("Email report sent to=%s", self.settings.email_to)
