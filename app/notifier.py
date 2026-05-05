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
from app.exceptions import NotificationConfigError, NotificationError

logger = logging.getLogger(__name__)

TELEGRAM_MESSAGE_LIMIT = 4096
TELEGRAM_SAFE_CHUNK_SIZE = 3800


class Notifier:
    """Send daily reports through Telegram and optional SMTP e-mail."""

    telegram_api_base = "https://api.telegram.org"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        logger.debug(
            "Notifier initialized telegram=%s email=%s",
            settings.telegram_enabled,
            settings.email_enabled,
        )

    def send_daily_report(self, jobs: Sequence[Mapping[str, Any]], total_new: int) -> None:
        if not jobs and not self.settings.send_empty_report:
            logger.info("No new jobs and empty reports disabled; notification skipped")
            return

        message = self.format_daily_report(jobs, total_new)

        if self.settings.telegram_enabled:
            self._send_telegram(message)
        else:
            logger.info("Telegram notification skipped because it is disabled or incomplete")

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
                lines.extend(self._format_job(index, job))
        else:
            lines.append("Nenhuma vaga nova compatível encontrada nesta execução.")
            lines.append("")

        lines.append(f"<b>Total de vagas novas hoje: {int(total_new)}</b>")
        return "\n".join(lines)

    def _format_job(self, index: int, job: Mapping[str, Any]) -> list[str]:
        title = html.escape(str(job.get("title") or "Sem título"))
        company = html.escape(str(job.get("company") or "Empresa não informada"))
        location = html.escape(str(job.get("location") or "Local não informado"))
        link = html.escape(str(job.get("link") or ""))
        score = float(job.get("score") or 0)
        remote_type = html.escape(str(job.get("remote_type") or "não informado"))
        contract_type = html.escape(str(job.get("contract_type") or "não informado"))
        salary = self._format_salary(job)
        score_reasons = job.get("score_reasons") or {}
        positive = [
            html.escape(str(reason)) for reason in score_reasons.get("positive_reasons", [])[:3]
        ]
        negative = [
            html.escape(str(reason)) for reason in score_reasons.get("negative_reasons", [])[:2]
        ]

        lines = [
            f"<b>{index}. {title}</b>",
            f"Empresa: {company}",
            f"Local: {location}",
            f"Modelo: {remote_type}",
            f"Contrato: {contract_type}",
            f"Salário: {salary}",
            f"Score: {score:.2f}",
        ]
        if positive or negative:
            lines.append("Motivos:")
            lines.extend(f"- {reason}" for reason in positive)
            lines.extend(f"- penalidade: {reason}" for reason in negative)
        if link:
            lines.append(f'<a href="{link}">Abrir vaga</a>')
        lines.append("")
        return lines

    def _format_salary(self, job: Mapping[str, Any]) -> str:
        salary_min = job.get("salary_min")
        salary_max = job.get("salary_max")
        currency = html.escape(str(job.get("salary_currency") or ""))
        if salary_min and salary_max:
            return html.escape(
                f"{currency} {float(salary_min):,.2f} - {float(salary_max):,.2f}".strip()
            )
        if salary_min:
            return html.escape(f"{currency} {float(salary_min):,.2f}".strip())
        return "não informado"

    def _send_telegram(self, message: str) -> None:
        if not self.settings.telegram_bot_token or not self.settings.telegram_chat_id:
            raise NotificationConfigError("Telegram token/chat_id are required")

        for chunk in split_telegram_message(message):
            try:
                self._post_telegram(chunk)
            except requests.RequestException as exc:
                raise NotificationError(f"Telegram request failed: {exc}") from exc
        logger.info("Telegram report sent chat_id=%s", self.settings.telegram_chat_id)

    @retry(
        retry=retry_if_exception_type(requests.RequestException),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _post_telegram(self, message: str) -> None:
        token = self.settings.telegram_bot_token
        chat_id = self.settings.telegram_chat_id
        if not token or not chat_id:
            raise NotificationConfigError("Telegram token/chat_id are required")
        url = f"{self.telegram_api_base}/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": self.settings.telegram_parse_mode,
            "disable_web_page_preview": True,
        }
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()

    def _send_email(self, html_message: str) -> None:
        if (
            not self.settings.email_host
            or not self.settings.email_from
            or not self.settings.email_to
        ):
            raise NotificationConfigError("Email host/from/to are required")
        try:
            self._deliver_email(html_message)
        except (OSError, smtplib.SMTPException) as exc:
            raise NotificationError(f"Email delivery failed: {exc}") from exc

    @retry(
        retry=retry_if_exception_type((OSError, smtplib.SMTPException)),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _deliver_email(self, html_message: str) -> None:
        if (
            not self.settings.email_host
            or not self.settings.email_from
            or not self.settings.email_to
        ):
            raise NotificationConfigError("Email host/from/to are required")
        plain_text = strip_html(html_message)

        message = EmailMessage()
        message["Subject"] = "JobHunter Daily Report"
        message["From"] = self.settings.email_from
        message["To"] = self.settings.email_to
        message.set_content(plain_text)
        message.add_alternative(html_message, subtype="html")

        logger.info(
            "Sending email report to=%s host=%s", self.settings.email_to, self.settings.email_host
        )
        with smtplib.SMTP(self.settings.email_host, self.settings.email_port, timeout=30) as smtp:
            if self.settings.email_use_tls:
                smtp.starttls()
            if self.settings.email_username and self.settings.email_password:
                smtp.login(self.settings.email_username, self.settings.email_password)
            smtp.send_message(message)
        logger.info("Email report sent to=%s", self.settings.email_to)


def split_telegram_message(message: str) -> list[str]:
    if len(message) <= TELEGRAM_MESSAGE_LIMIT:
        return [message]
    chunks: list[str] = []
    current: list[str] = []
    current_length = 0
    for line in message.splitlines(keepends=True):
        if current_length + len(line) > TELEGRAM_SAFE_CHUNK_SIZE and current:
            chunks.append("".join(current))
            current = []
            current_length = 0
        current.append(line)
        current_length += len(line)
    if current:
        chunks.append("".join(current))
    return chunks


def strip_html(value: str) -> str:
    cleaned = value.replace("<b>", "").replace("</b>", "").replace("<br>", "\n").replace("</a>", "")
    cleaned = cleaned.replace('">Abrir vaga', " - Abrir vaga")
    cleaned = cleaned.replace('<a href="', "")
    return html.unescape(cleaned)
