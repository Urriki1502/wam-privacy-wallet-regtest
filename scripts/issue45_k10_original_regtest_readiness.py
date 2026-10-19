"""Check original WAM Fusion REGTEST owner/custody before manual Send / Sign.

READ-ONLY. No imported/transported wallet recovery, signer session, RPC
wallet mutation or auto-broadcast. Requires a terminal and never accepts
a password on argv, in environment variables or from redirected stdin.
"""
from __future__ import annotations

import argparse
from getpass import getpass
from pathlib import Path
import sys

from wam_regtest.k10_original_test_access import (
    inspect_original_regtest_test_readiness,
)


def main():
    parser=argparse.ArgumentParser(
        description="Check ORIGINAL REGTEST wallet readiness; not an unlock")
    parser.add_argument("--root",required=True,type=Path)
    parser.add_argument("--core-dir",required=True,type=Path)
    parser.add_argument("--wsp-source",required=True,type=Path)
    parser.add_argument("--confirm-original-regtest-test-only",
                        action="store_true")
    options=parser.parse_args()
    if (options.confirm_original_regtest_test_only is not True
            or not sys.stdin.isatty()):
        print("K10_ORIGINAL_TEST_INTERACTIVE_CONSENT_REQUIRED")
        return 2
    password=None
    try:
        password=getpass("Original REGTEST wallet passphrase: ").encode("utf-8")
        report=inspect_original_regtest_test_readiness(
            options.root.resolve(strict=True),
            options.core_dir.resolve(strict=True),
            options.wsp_source.resolve(strict=True),
            password,authorized=True)
        if (report.get("status")!=
                "K10_ORIGINAL_REGTEST_MANUAL_OPEN_PREFLIGHT_ONLY"
                or report.get(
                    "manual_gui_original_wallet_open_may_be_attempted") is not True
                or report.get("signer_allowed") is not False
                or report.get("broadcast_allowed") is not False):
            raise ValueError
        print("K10_ORIGINAL_REGTEST_MANUAL_OPEN_PREFLIGHT_ONLY")
        print("Original owner checkpoint and Core attested. "
              "Manual REGTEST Send / Sign may be attempted from the GUI.")
        print("NOT UNLOCKED. Imported/clean-OS wallets remain LOCKED.")
        return 0
    except Exception:
        # Strip native, wallet and credential details from console output.
        print("K10_ORIGINAL_TEST_PREFLIGHT_UNVERIFIED")
        return 1
    finally:
        password=None


if __name__=="__main__":
    raise SystemExit(main())
