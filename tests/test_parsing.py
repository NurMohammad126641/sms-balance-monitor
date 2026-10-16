from decimal import Decimal

import pytest

from sms_balance.parsing import BalanceParseError, parse_amount


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("12345", "12345"),
        ("Cur. Balance: 12,345.67 BDT", "12345.67"),
        ("৳ 1,23,456.50", "123456.50"),
        ("API Balance : ৪২,০০০.৭৫", "42000.75"),
        ("BDT -150.00", "-150.00"),
        ("  7  ", "7"),
    ],
)
def test_parses_common_balance_formats(text, expected):
    assert parse_amount(text) == Decimal(expected)


@pytest.mark.parametrize("text", ["", "N/A", "Balance: --", None])
def test_rejects_text_without_amount(text):
    with pytest.raises(BalanceParseError):
        parse_amount(text)
