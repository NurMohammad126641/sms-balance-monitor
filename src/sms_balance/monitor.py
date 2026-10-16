"""Check every portal, decide what needs attention and format the message."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal

from sms_balance.config import Portal

log = logging.getLogger(__name__)

BalanceReader = Callable[[Portal], Decimal]


@dataclass(frozen=True)
class Reading:
    portal: Portal
    balance: Decimal | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.balance is not None

    @property
    def low(self) -> bool:
        return self.ok and self.balance <= self.portal.low_balance

    def line(self) -> str:
        if not self.ok:
            return f"{self.portal.label}: could not read balance ({self.error})"
        flag = "  <-- LOW" if self.low else ""
        return f"{self.portal.label}: {self.balance:,.2f} {self.portal.currency}{flag}"


def check_all(portals: Sequence[Portal], reader: BalanceReader) -> list[Reading]:
    """Read every portal one after another; a failure on one does not stop the rest."""
    readings: list[Reading] = []
    for portal in portals:
        try:
            readings.append(Reading(portal, balance=reader(portal)))
        except Exception as exc:
            log.exception("Reading %s failed", portal.name)
            readings.append(Reading(portal, error=f"{type(exc).__name__}: {exc}"[:200]))
    return readings


def build_message(readings: Sequence[Reading]) -> tuple[str, str, bool]:
    """Return ``(subject, body, needs_attention)`` for the daily balance update."""
    low = [r for r in readings if r.low]
    failed = [r for r in readings if not r.ok]
    if low or failed:
        problems = []
        if low:
            problems.append(f"{len(low)} low")
        if failed:
            problems.append(f"{len(failed)} unreadable")
        subject = f"[ACTION NEEDED] SMS balance: {', '.join(problems)}"
    else:
        subject = "SMS balance update: all portals OK"
    body = "\n".join(r.line() for r in readings)
    return subject, body, bool(low or failed)
