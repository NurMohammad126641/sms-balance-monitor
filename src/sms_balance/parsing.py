"""Turn whatever a portal shows ("Cur. Balance: ৳ 1,23,456.50 BDT") into a number."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

# Bangla digits appear on some local portals.
_BANGLA_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
_NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


class BalanceParseError(ValueError):
    """Raised when no amount can be found in the text."""


def parse_amount(text: str) -> Decimal:
    """Return the first amount in ``text``.

    Handles currency symbols and codes, thousands separators in both Western (1,234,567) and
    South Asian (12,34,567) grouping, surrounding labels, and Bangla digits.
    """
    if text is None:
        raise BalanceParseError("No balance text")
    normalised = str(text).translate(_BANGLA_DIGITS)
    match = _NUMBER.search(normalised)
    if not match:
        raise BalanceParseError(f"No amount found in {text!r}")
    try:
        return Decimal(match.group(0).replace(",", ""))
    except InvalidOperation as exc:
        raise BalanceParseError(f"Unreadable amount in {text!r}") from exc
