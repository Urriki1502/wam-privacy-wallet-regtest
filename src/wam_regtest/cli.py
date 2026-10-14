"""CLI entry for real Core only. No synthetic RPC mode."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .core import CoreSmokeError, smoke_real_core


def main() -> int:
    ap = argparse.ArgumentParser(prog="wam-regtest")
    sub = ap.add_subparsers(dest="command", required=True)
    smoke = sub.add_parser("smoke", help="Run signed real WAM Core v0.1.11 on fresh REGTEST only")
    smoke.add_argument("--core-dir", required=True, type=Path)
    smoke.add_argument("--confirm-disposable-regtest", action="store_true", help="Approve keyless local Core process and disposable test wallet")
    smoke.add_argument("--report", type=Path, help="Write a redacted public receipt")
    args = ap.parse_args()
    try:
        if args.command == "smoke":
            outcome = smoke_real_core(args.core_dir.expanduser().absolute(), explicit_consent=args.confirm_disposable_regtest)
            if args.report:
                if args.report.exists() or not args.report.parent.is_dir():
                    raise CoreSmokeError("CORE_REPORT_PATH_DENIED")
                args.report.write_text(json.dumps(outcome, sort_keys=True, indent=2) + "\n")
            print(json.dumps(outcome, sort_keys=True))
            return 0
        raise CoreSmokeError("CORE_COMMAND_DENIED")
    except CoreSmokeError as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
