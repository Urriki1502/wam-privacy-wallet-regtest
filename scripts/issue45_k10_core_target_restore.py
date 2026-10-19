"""K-10 isolated REGTEST destination restore of an offline Core SQLite backup.

This is executable native Core qualification, NOT Fusion wallet import.
Runs ONLY in a fresh disposable Core, using the pre-existing K-04 narrow
RPC allowlist. The source must be a deliberately created REGTEST fixture
whose exact backup digest and PUBLIC descriptor digest were already
recorded by the origin. No owner/miner wallets, Keychain copies, native
anchors, Core wallet key export, Fusion signer or broadcast permission.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from hashlib import sha256
from pathlib import Path
import re
import tempfile

from wam_regtest.core import verified_core_paths
from wam_regtest.core_sqlite_import import (
    inspect_sqlite_backup, stage_verified_backup, verify_restored_core_wallet,
)
from wam_regtest.custody import create_directory
from wam_regtest.owned_start import disposable_core
from wam_regtest.wsp_live import REGTEST_GENESIS

from scripts.issue45_k04_sqlite_e2e import _wallet_rpc

HASH=re.compile(r"[0-9a-f]{64}\Z")


class K10CoreTransferRefusal(ValueError):
    """Constant non-secret error category, never raw RPC or wallet output."""


def _deny(code):
    raise K10CoreTransferRefusal(code)


def _scope(core_dir, backup, backup_sha256, descriptor_sha256, authorized):
    if authorized is not True:
        _deny("K10_CORE_TRANSFER_EXPLICIT_TEST_CONSENT_REQUIRED")
    if (type(core_dir) is not type(Path) or not core_dir.is_absolute()
            or type(backup) is not type(Path) or not backup.is_absolute()
            or core_dir.is_symlink() or backup.is_symlink()
            or type(backup_sha256) is not str or not HASH.fullmatch(backup_sha256)
            or type(descriptor_sha256) is not str
            or not HASH.fullmatch(descriptor_sha256)):
        _deny("K10_CORE_TRANSFER_INPUT_DENIED")


def qualify_isolated_core_restore(core_dir, backup, *,
                                  expected_backup_sha256,
                                  expected_descriptor_sha256,
                                  authorized=False):
    """Restore a named PUBLIC disposable SQLite fixture in isolated WAM Core.

    The origin digest is a caller-supplied expected value. This routine
    cannot attest a foreign origin's physical machine, runner signature,
    trusted prior receipt, or any earlier WSP history. It must never
    operate on the owner's persistent Core process or data directory.
    """
    _scope(core_dir,backup,expected_backup_sha256,
           expected_descriptor_sha256,authorized)
    try:
        _,_,binary=verified_core_paths(core_dir)
        original=inspect_sqlite_backup(backup)
        if (original.file_sha256!=expected_backup_sha256
                or original.format!="sqlite"
                or original.network!="UNVERIFIED"):
            _deny("K10_CORE_TRANSFER_SOURCE_HASH_DENIED")

        with tempfile.TemporaryDirectory(prefix="k10-core-target-disposable-") as tmp:
            root=Path(tmp).resolve(strict=True)
            staging=root/"staging"
            create_directory(staging)
            staged,copy_receipt=stage_verified_backup(
                backup,staging,authorized=True)
            if copy_receipt!=original:
                _deny("K10_CORE_TRANSFER_COPY_UNVERIFIED")
            before=inspect_sqlite_backup(staged)
            if before!=original:
                _deny("K10_CORE_TRANSFER_COPY_UNVERIFIED")

            with disposable_core(core_dir,authorized=True) as target:
                if (target.receipt["wamd_sha256"]!=binary["wamd_sha256"]
                        or target.receipt["wam_cli_sha256"]!=binary["wam_cli_sha256"]):
                    _deny("K10_CORE_TRANSFER_BINARY_CHANGED")
                isolated=target.read.attest()
                if (isolated.get("chain")!="regtest"
                        or isolated.get("blocks")!=0
                        or _wallet_rpc(target,None,"getblockhash","0")!=REGTEST_GENESIS):
                    _deny("K10_CORE_TRANSFER_WRONG_CHAIN")
                restored=_wallet_rpc(
                    target,None,"restorewallet",
                    "k04-reviewed",str(staged),restore_source=staged)
                if (type(restored) is not dict
                        or restored.get("name")!="k04-reviewed"
                        or restored.get("warnings")):
                    _deny("K10_CORE_TRANSFER_RESTORE_UNVERIFIED")
                info=_wallet_rpc(target,"k04-reviewed","getwalletinfo")
                listing=_wallet_rpc(
                    target,"k04-reviewed","listdescriptors","false")
                verified=verify_restored_core_wallet(
                    chain="regtest",genesis=REGTEST_GENESIS,
                    wallet_info=info,descriptor_listing=listing)
                if verified["descriptor_identity_sha256"]!=expected_descriptor_sha256:
                    _deny("K10_CORE_TRANSFER_DESCRIPTOR_MISMATCH")
                if (target.read.attest().get("chain")!="regtest"
                        or _wallet_rpc(target,None,"getblockhash","0")!=REGTEST_GENESIS):
                    _deny("K10_CORE_TRANSFER_CHAIN_CHANGED")
                if (inspect_sqlite_backup(backup)!=original
                        or inspect_sqlite_backup(staged)!=original):
                    _deny("K10_CORE_TRANSFER_SOURCE_CHANGED")
                return {
                    "status":"K10_CORE_SQLITE_ISOLATED_RESTORE_VERIFIED",
                    "network":"regtest",
                    "core_native_restorewallet_observed":True,
                    "descriptor_public_identity_matched_expected":True,
                    "source_backup_byte_identity_preserved":True,
                    "disposable_owned_core_attested":True,
                    "fixture_core_sqlite_format_verified":True,
                    "destination_restored_into_fusion":False,
                    "origin_os_provenance_verified":False,
                    "cross_os_physical_qualified":False,
                    "original_wsp_history_reconciled":False,
                    "signed_uncertain_reservations_reconciled":False,
                    "new_native_anchor_created":False,
                    "safe_to_unlock":False,
                    "signer_allowed":False,
                    "broadcast_allowed":False,
                    "mainnet_allowed":False,
                }
    except K10CoreTransferRefusal:
        raise
    except Exception:
        _deny("K10_CORE_TRANSFER_RESTORE_FAILED")


def main():
    parser=argparse.ArgumentParser(
        description="Restore disposable Core-native REGTEST SQLite in isolated Core")
    parser.add_argument("--core-dir",type=Path,required=True)
    parser.add_argument("--backup",type=Path,required=True)
    parser.add_argument("--expected-backup-sha256",required=True)
    parser.add_argument("--expected-public-descriptor-sha256",required=True)
    parser.add_argument("--confirm-disposable-regtest",action="store_true")
    args=parser.parse_args()
    try:
        result=qualify_isolated_core_restore(
            args.core_dir,args.backup,
            expected_backup_sha256=args.expected_backup_sha256,
            expected_descriptor_sha256=args.expected_public_descriptor_sha256,
            authorized=args.confirm_disposable_regtest)
        print(result["status"])
        return 0
    except K10CoreTransferRefusal as error:
        print(error.args[0])
        return 1


if __name__=="__main__":
    raise SystemExit(main())
