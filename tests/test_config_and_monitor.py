from decimal import Decimal
from pathlib import Path

import pytest

from sms_balance.config import ConfigError, Portal, load_portals
from sms_balance.monitor import build_message, check_all

ROOT = Path(__file__).resolve().parents[1]


def portal(name="p1", low="1000", **kw) -> Portal:
    base = {
        "name": name,
        "label": name.upper(),
        "url": "https://example.com",
        "username_env": "P_USER",
        "password_env": "P_PASS",
        "username_selector": "#u",
        "password_selector": "#p",
        "balance_selector": "#b",
        "low_balance": Decimal(low),
    }
    base.update(kw)
    return Portal(**base)


def test_shipped_example_config_loads():
    portals = load_portals(ROOT / "config" / "portals.yaml")

    names = [p.name for p in portals]
    assert names == ["bulk_sms_primary", "bulk_sms_backup", "api_sms_gateway"]
    gateway = portals[2]
    assert gateway.otp is not None and gateway.otp.timeout_seconds == 300
    assert gateway.hover_selector.startswith("xpath:")
    assert portals[0].low_balance == Decimal("5000")


def test_credentials_come_from_environment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("P_USER", "alice")
    monkeypatch.setenv("P_PASS", "s3cret")

    assert portal().credentials() == ("alice", "s3cret")


def test_missing_credentials_name_the_variables(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("P_USER", raising=False)
    monkeypatch.delenv("P_PASS", raising=False)

    with pytest.raises(ConfigError, match="P_USER, P_PASS"):
        portal().credentials()


def test_duplicate_portal_names_are_rejected(tmp_path: Path):
    entry = (
        "  - {name: a, url: u, username_env: U, password_env: P,"
        " selectors: {username: '#u', password: '#p', balance: '#b'}}\n"
    )
    path = tmp_path / "portals.yaml"
    path.write_text("portals:\n" + entry + entry, encoding="utf-8")

    with pytest.raises(ConfigError, match="unique"):
        load_portals(path)


def test_check_all_isolates_failures_and_flags_low_balances():
    portals = [portal("ok", low="1000"), portal("low", low="1000"), portal("broken")]
    balances = {"ok": Decimal("5000"), "low": Decimal("250.5")}

    def reader(p: Portal) -> Decimal:
        if p.name == "broken":
            raise TimeoutError("login page did not load")
        return balances[p.name]

    readings = check_all(portals, reader)
    subject, body, attention = build_message(readings)

    assert [r.ok for r in readings] == [True, True, False]
    assert [r.low for r in readings] == [False, True, False]
    assert attention is True
    assert subject == "[ACTION NEEDED] SMS balance: 1 low, 1 unreadable"
    assert "LOW: 250.50 BDT  <-- LOW" in body
    assert "BROKEN: could not read balance (TimeoutError" in body


def test_all_good_message():
    readings = check_all([portal("a")], lambda p: Decimal("123456.7"))

    subject, body, attention = build_message(readings)

    assert attention is False
    assert subject == "SMS balance update: all portals OK"
    assert body == "A: 123,456.70 BDT"
