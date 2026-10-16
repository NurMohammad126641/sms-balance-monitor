"""Portal definitions (YAML) plus credentials (environment variables).

The YAML describes *how* to read a portal: URL, CSS/XPath selectors, optional OTP step and the
low-balance threshold. It only names the environment variables that hold the username and
password, so it is safe to commit.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """Raised when the portal configuration or credentials are missing or invalid."""


@dataclass(frozen=True)
class OtpStep:
    """A portal that sends an OTP: wait for a person to type it in a visible browser."""

    page_url_contains: str
    done_url_contains: str
    timeout_seconds: int = 300


@dataclass(frozen=True)
class Portal:
    name: str
    label: str
    url: str
    username_env: str
    password_env: str
    username_selector: str
    password_selector: str
    balance_selector: str
    submit_selector: str = ""
    dismiss_selectors: list[str] = field(default_factory=list)
    hover_selector: str = ""
    otp: OtpStep | None = None
    low_balance: Decimal = Decimal("0")
    currency: str = "BDT"

    def credentials(self) -> tuple[str, str]:
        user = os.getenv(self.username_env, "")
        password = os.getenv(self.password_env, "")
        pairs = ((self.username_env, user), (self.password_env, password))
        missing = [env for env, value in pairs if not value]
        if missing:
            raise ConfigError(f"{self.name}: set {', '.join(missing)} in the environment")
        return user, password


def _required(item: dict[str, Any], key: str, where: str) -> Any:
    value = item.get(key)
    if value in (None, ""):
        raise ConfigError(f"{where}: missing '{key}'")
    return value


def load_portals(path: str | Path) -> list[Portal]:
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"Config file not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    portals: list[Portal] = []
    for item in raw.get("portals") or []:
        name = _required(item, "name", "portal")
        where = f"portal '{name}'"
        selectors = item.get("selectors") or {}
        otp = item.get("otp")
        portals.append(
            Portal(
                name=name,
                label=item.get("label", name),
                url=_required(item, "url", where),
                username_env=_required(item, "username_env", where),
                password_env=_required(item, "password_env", where),
                username_selector=_required(selectors, "username", where),
                password_selector=_required(selectors, "password", where),
                balance_selector=_required(selectors, "balance", where),
                submit_selector=selectors.get("submit", ""),
                dismiss_selectors=list(selectors.get("dismiss") or []),
                hover_selector=selectors.get("hover_before_balance", ""),
                otp=OtpStep(
                    page_url_contains=_required(otp, "page_url_contains", where),
                    done_url_contains=_required(otp, "done_url_contains", where),
                    timeout_seconds=int(otp.get("timeout_seconds", 300)),
                )
                if otp
                else None,
                low_balance=Decimal(str(item.get("low_balance", 0))),
                currency=item.get("currency", "BDT"),
            )
        )
    names = [p.name for p in portals]
    if len(names) != len(set(names)):
        raise ConfigError("Portal names must be unique")
    if not portals:
        raise ConfigError("No portals configured")
    return portals
