"""K-10 genuine same-host disposable REGTEST Core SQLite transfer smoke.

Run on each native test OS with a qualified WAM Core. This is NOT the six
cross-OS handoffs: backup and original Core runtime live only in temporary
private storage and are never published as CI artifacts or loaded into
Fusion. Signed/uncertain WSP reservations and native anchors remain LOCKED.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import tempfile

from scripts.issue45_k10_core_source_fixture import (
    generate_disposable_core_fixture,
)
from scripts.issue45_k10_core_target_restore import (
    qualify_isolated_core_restore,
)


def prove_same_host_disposable_transfer(core_dir,*,authorized=False):
    if authorized is not True or type(core_dir) is not type(Path()) or not core_dir.is_absolute():
        raise ValueError("K10_LOCAL_DISPOSABLE_SCOPE_DENIED")
    try:
        with tempfile.TemporaryDirectory(prefix="k10-verified-private-transfer-") as tmp:
            source=Path(tmp).resolve(strict=True)/"private-source"
            manifest=generate_disposable_core_fixture(
                core_dir,source,authorized=True)
            checked=qualify_isolated_core_restore(
                core_dir,source/"core-wallet-backup.dat",
                expected_backup_sha256=manifest["backup_sha256"],
                expected_descriptor_sha256=manifest["public_descriptor_sha256"],
                authorized=True)
            if (checked["status"]!="K10_CORE_SQLITE_ISOLATED_RESTORE_VERIFIED"
                    or checked["core_native_restorewallet_observed"] is not True
                    or checked["descriptor_public_identity_matched_expected"] is not True
                    or checked["source_backup_byte_identity_preserved"] is not True
                    or checked["signer_allowed"] is not False
                    or checked["broadcast_allowed"] is not False):
                raise ValueError
        return {
            "status":"K10_REAL_CORE_SQLITE_SAME_OS_QUARANTINE_PASS",
            "regtest":True,
            "private_disposable_backup_deleted_with_temp_scope":True,
            "actual_core_source_and_target_rpc_verified":True,
            "source_and_target_descriptor_public_identity_equal":True,
            "cross_os_physical_transfer_qualified":False,
            "original_wsp_reservations_reconciled":False,
            "fusion_wallet_restored":False,
            "native_anchor_created":False,
            "signer_allowed":False,
            "broadcast_allowed":False,
            "mainnet_allowed":False,
        }
    except Exception:
        raise ValueError("K10_LOCAL_DISPOSABLE_TRANSFER_FAILED") from None


def main():
    parser=argparse.ArgumentParser(
        description="Same-OS genuine Core SQLite transfer smoke, REGTEST only")
    parser.add_argument("--core-dir",required=True,type=Path)
    parser.add_argument("--confirm-disposable-regtest",action="store_true")
    args=parser.parse_args()
    try:
        result=prove_same_host_disposable_transfer(
            args.core_dir,authorized=args.confirm_disposable_regtest)
        print(result["status"])
        return 0
    except ValueError as error:
        print(error.args[0])
        return 1


if __name__=="__main__":
    raise SystemExit(main())
