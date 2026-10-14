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
    smoke.add_argument("--wsp-source-root", type=Path, help="Pinned upstream WSP checkout; require actual live node and scanner")
    smoke.add_argument("--confirm-public-fixture-payment", action="store_true", help="Approve globally-known REGTEST fixture key signing and broadcast, no mainnet")
    smoke.add_argument("--confirm-real-gui-e2e", action="store_true", help="Assert native Qt UI against live Core BIP352/SQLite (CI/headless)")

    gui = sub.add_parser("gui", help="Open native Mac read-only public-demo wallet on an ALREADY RUNNING isolated Core REGTEST daemon")
    gui.add_argument("--core-dir", required=True, type=Path)
    gui.add_argument("--datadir", required=True, type=Path)
    gui.add_argument("--wsp-source-root", required=True, type=Path)
    gui.add_argument("--confirm-disposable-regtest", action="store_true")

    demo = sub.add_parser(
        "demo", help="One command: signed v0.1.11 Core -> genuine BIP352 payment -> interactive native Qt REGTEST"
    )
    demo.add_argument("--core-dir", required=True, type=Path)
    demo.add_argument("--wsp-source-root", required=True, type=Path)
    demo.add_argument("--confirm-disposable-regtest", action="store_true")
    demo.add_argument("--confirm-public-fixture-payment", action="store_true")
    args = ap.parse_args()
    try:
        if args.command == "smoke":
            outcome = smoke_real_core(args.core_dir.expanduser().absolute(), explicit_consent=args.confirm_disposable_regtest,
                                      wsp_source=(args.wsp_source_root.expanduser().absolute() if args.wsp_source_root else None),
                                      wsp_payment_e2e=args.confirm_public_fixture_payment,
                                      gui_e2e=args.confirm_real_gui_e2e)
            if args.report:
                if args.report.exists() or not args.report.parent.is_dir():
                    raise CoreSmokeError("CORE_REPORT_PATH_DENIED")
                args.report.write_text(json.dumps(outcome, sort_keys=True, indent=2) + "\n")
            print(json.dumps(outcome, sort_keys=True))
            return 0
        if args.command == "demo":
            if (args.confirm_disposable_regtest is not True
                    or args.confirm_public_fixture_payment is not True):
                raise CoreSmokeError("CORE_REAL_DEMO_CONSENT_DENIED")
            result = smoke_real_core(
                args.core_dir.expanduser().absolute(),
                explicit_consent=True,
                wsp_source=args.wsp_source_root.expanduser().absolute(),
                wsp_payment_e2e=True,
                interactive_demo=True,
            )
            if not result.get("interactive_demo_closed_cleanly"):
                raise CoreSmokeError("CORE_REAL_DEMO_NOT_CLOSED")
            print(json.dumps(result, sort_keys=True))
            return 0
        if args.command == "gui":
            if args.confirm_disposable_regtest is not True:
                raise CoreSmokeError("CORE_GUI_DISPOSABLE_REGTEST_CONSENT_DENIED")
            # Separate, running signed WAM Core required; never autostart or
            # attempt to upgrade an unknown process into a wallet.
            from .desktop import launch_readonly_wallet
            return launch_readonly_wallet(
                args.core_dir.expanduser().absolute(),
                args.datadir.expanduser().absolute(),
                args.wsp_source_root.expanduser().absolute(),
            )
        raise CoreSmokeError("CORE_COMMAND_DENIED")
    except CoreSmokeError as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
