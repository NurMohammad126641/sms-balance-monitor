"""Drive real headless Chrome against tests/fixtures/portal.html (runs in CI)."""

import shutil
from decimal import Decimal
from pathlib import Path

import pytest
from selenium.common.exceptions import TimeoutException

from sms_balance.config import Portal
from sms_balance.portal import read_balance

FIXTURE = (Path(__file__).parent / "fixtures" / "portal.html").resolve().as_uri()
BROWSERS = ("google-chrome", "chrome", "chromium", "chromium-browser")
HAS_CHROME = any(shutil.which(b) for b in BROWSERS)

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(not HAS_CHROME, reason="Chrome is not installed"),
]


@pytest.fixture(autouse=True)
def demo_credentials(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DEMO_USER", "demo-user")
    monkeypatch.setenv("DEMO_PASS", "demo-pass")


def demo_portal(**kw) -> Portal:
    base = {
        "name": "demo",
        "label": "Demo portal",
        "url": FIXTURE,
        "username_env": "DEMO_USER",
        "password_env": "DEMO_PASS",
        "username_selector": "#name",
        "password_selector": "#password",
        "submit_selector": "#login-btn",
        "dismiss_selectors": ["xpath://button[span[contains(text(), 'Agree')]]"],
        "balance_selector": "xpath://li[contains(., 'Cur. Balance:')]//span",
    }
    base.update(kw)
    return Portal(**base)


def test_logs_in_dismisses_popup_and_reads_balance():
    assert read_balance(demo_portal(), timeout=10) == Decimal("123456.50")


def test_hover_reveals_balance_in_bangla_digits():
    portal = demo_portal(
        hover_selector="#dollar",
        balance_selector="xpath://div[@id='balance-tip']/strong",
    )

    assert read_balance(portal, timeout=10) == Decimal("42000.75")


def test_wrong_password_times_out(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DEMO_PASS", "wrong")

    with pytest.raises(TimeoutException):
        read_balance(demo_portal(dismiss_selectors=[]), timeout=3)
