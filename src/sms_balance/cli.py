"""``sms-balance list`` and ``sms-balance check``."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections.abc import Sequence
from functools import partial

from dotenv import load_dotenv

from sms_balance.alerts import channels_from_env, dispatch
from sms_balance.config import ConfigError, load_portals
from sms_balance.monitor import build_message, check_all
from sms_balance.portal import read_balance

DEFAULT_CONFIG = "config/portals.yaml"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sms-balance", description=__doc__)
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="portal definitions (YAML)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="show configured portals")
    check = sub.add_parser("check", help="read every balance and send the update")
    check.add_argument("--only", nargs="+", metavar="NAME", help="check only these portals")
    check.add_argument("--headed", action="store_true",
                       help="show the browser (needed for portals with an OTP step)")
    check.add_argument("--no-alerts", action="store_true", help="print instead of sending")
    check.add_argument("--always-send", action="store_true",
                       help="send the update even when every balance is fine")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv()
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper(),
                        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    args = _parser().parse_args(argv)
    try:
        portals = load_portals(args.config)
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2

    if args.command == "list":
        for p in portals:
            otp = " (OTP: needs --headed)" if p.otp else ""
            print(f"{p.name:<20} low below {p.low_balance} {p.currency}  {p.url}{otp}")
        return 0

    selected = [p for p in portals if not args.only or p.name in args.only]
    readings = check_all(selected, partial(read_balance, headless=not args.headed))
    subject, body, needs_attention = build_message(readings)
    print(f"{subject}\n{body}")

    channels = [] if args.no_alerts else channels_from_env()
    if channels and (needs_attention or args.always_send):
        dispatch(channels, subject, body)
    return 1 if any(not r.ok for r in readings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
