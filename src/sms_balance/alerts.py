"""Deliver the balance update by email and/or a Microsoft Teams incoming webhook.

The original bot posted to Skype, which has since been retired; Teams webhooks are the
straightforward replacement. Channels are enabled only when their variables are set.
"""

from __future__ import annotations

import logging
import os
import smtplib
from collections.abc import Sequence
from email.message import EmailMessage
from typing import Protocol

import requests

log = logging.getLogger(__name__)


class Channel(Protocol):
    def send(self, subject: str, body: str) -> None: ...


class EmailChannel:
    def __init__(self, host: str, port: int, user: str, password: str, sender: str,
                 recipients: Sequence[str], use_ssl: bool = False) -> None:
        self.host, self.port = host, port
        self.user, self.password = user, password
        self.sender, self.recipients = sender, list(recipients)
        self.use_ssl = use_ssl

    def send(self, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.sender
        msg["To"] = ", ".join(self.recipients)
        msg.set_content(body)
        if self.use_ssl:
            with smtplib.SMTP_SSL(self.host, self.port, timeout=30) as smtp:
                self._deliver(smtp, msg)
        else:
            with smtplib.SMTP(self.host, self.port, timeout=30) as smtp:
                smtp.starttls()
                self._deliver(smtp, msg)

    def _deliver(self, smtp: smtplib.SMTP, msg: EmailMessage) -> None:
        if self.user:
            smtp.login(self.user, self.password)
        smtp.send_message(msg)


class TeamsChannel:
    def __init__(self, url: str) -> None:
        self.url = url

    def send(self, subject: str, body: str) -> None:
        text = f"**{subject}**\n\n" + body.replace("\n", "  \n")
        requests.post(self.url, json={"text": text}, timeout=15).raise_for_status()


def channels_from_env() -> list[Channel]:
    channels: list[Channel] = []
    host = os.getenv("SMTP_HOST")
    recipients = [r.strip() for r in os.getenv("ALERT_EMAIL_TO", "").split(",") if r.strip()]
    if host and recipients:
        user = os.getenv("SMTP_USER", "")
        channels.append(
            EmailChannel(
                host=host,
                port=int(os.getenv("SMTP_PORT", "587")),
                user=user,
                password=os.getenv("SMTP_PASSWORD", ""),
                sender=os.getenv("ALERT_EMAIL_FROM") or user,
                recipients=recipients,
                use_ssl=os.getenv("SMTP_SSL", "false").lower() in {"1", "true", "yes"},
            )
        )
    if os.getenv("TEAMS_WEBHOOK_URL"):
        channels.append(TeamsChannel(os.environ["TEAMS_WEBHOOK_URL"]))
    return channels


def dispatch(channels: Sequence[Channel], subject: str, body: str) -> int:
    delivered = 0
    for channel in channels:
        try:
            channel.send(subject, body)
            delivered += 1
        except Exception:
            log.exception("Delivery via %s failed", type(channel).__name__)
    return delivered
