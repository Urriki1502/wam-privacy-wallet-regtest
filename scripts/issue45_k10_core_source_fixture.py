"""K-10: generate a Core-native SQLite REGTEST fixture for private transfer.

The fixture is created by a fresh OWNED disposable Core, never by attaching
to the original user/miner wallet. It contains a Core wallet's PRIVATE
REGTEST keys: handle it as sensitive test material and NEVER publish it
to a repository, CI artifact, log, bug report or unrestricted directory.

Only a new owner-private output directory is accepted. No overwrite.
This does not prove physical machine origin, signed runner provenance,
or portable Fusion reservation/signer recovery.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re

from wam_regtest.core import verified_core_paths
from wam_regtest.core_sqlite_import import inspect_sqlite_backup
from wam_regtest.custody import create_directory
from wam_regtest.owned_start import disposable_core
from wam_regtest.v1_contracts import core_descriptor_identity
from wam_regtest.wsp_live import REGTEST_GENESIS

from scripts.issue45_k04_sqlite_e2e import (
    _wallet_rpc, _stable_disposable_core_backup,
)


class K10SourceFixtureError(ValueError):
    pass


def generate_disposable_core_fixture(core_dir, new_private_directory, *,
                                     authorized=False):
    """Make an explicit Core-native fixture; retain evidence, no wallet reuse."""
    if authorized is not True:
        raise K10SourceFixtureError("K10_SOURCE_FIXTURE_CONSENT_REQUIRED")
    if (type(core_dir) is not type(Path()) or not core_dir.is_absolute()
            or type(new_private_directory) is not type(Path())
            or not new_private_directory.is_absolute()
            or new_private_directory==core_dir
            or new_private_directory.is_symlink()
            or new_private_directory.exists()):
        raise K10SourceFixtureError("K10_SOURCE_FIXTURE_OUTPUT_DENIED")
    try:
        _,_,receipt=verified_core_paths(core_dir)
        # The directory is created exactly once. Ambiguous partial contents
        # are NEVER removed or replaced after a failed fixture operation.
        create_directory(new_private_directory)
        source=new_private_directory/"core-wallet-backup.dat"
        with disposable_core(core_dir,authorized=True) as owned:
            if (owned.receipt["wamd_sha256"]!=receipt["wamd_sha256"]
                    or owned.receipt["wam_cli_sha256"]!=receipt["wam_cli_sha256"]):
                raise ValueError
            _wallet_rpc(owned,None,"createwallet","k04-source")
            info=_wallet_rpc(owned,"k04-source","getwalletinfo")
            if (type(info) is not dict or info.get("format")!="sqlite"
                    or info.get("descriptors") is not True):
                raise ValueError
            chain=_wallet_rpc(owned,None,"getblockchaininfo")
            if (chain.get("chain")!="regtest"
                    or _wallet_rpc(owned,None,"getblockhash","0")!=REGTEST_GENESIS):
                raise ValueError
            if owned.read.attest().get("blocks")!=0:
                raise ValueError
            address=_wallet_rpc(owned,"k04-source","getnewaddress")
            blocks=_wallet_rpc(owned,None,"generatetoaddress","101",address)
            if type(blocks) is not list or len(blocks)!=101:
                raise ValueError
            listing=_wallet_rpc(owned,"k04-source","listdescriptors","false")
            descriptor_hash=core_descriptor_identity(listing)
            _wallet_rpc(owned,"k04-source","backupwallet",
                        str(source),backup_target=source)
            backup=_stable_disposable_core_backup(source)
            if backup!=inspect_sqlite_backup(source):
                raise ValueError
            manifest={
                "schema":"wam-fusion-k10-disposable-core-transfer/v1",
                "fixture_type":"CORE_SQLITE_PRIVATE_REGTEST_ONLY",
                "chain":"regtest",
                "genesis":REGTEST_GENESIS,
                "source_platform":receipt["platform"],
                "core_sha256":receipt["wamd_sha256"],
                "backup_sha256":backup.file_sha256,
                "backup_bytes":backup.byte_count,
                "public_descriptor_sha256":descriptor_hash,
                "physical_machine_origin_attested":False,
                "cross_os_core_restore_qualified":False,
                "fusion_wallet_restored":False,
                "signer_allowed":False,
                "broadcast_allowed":False,
                "mainnet_allowed":False,
            }
            name=new_private_directory/"public-manifest.json"
            fd=None
            try:
                flags=(os.O_CREAT|os.O_EXCL|os.O_WRONLY
                       |getattr(os,"O_NOFOLLOW",0)
                       |getattr(os,"O_BINARY",0)
                       |getattr(os,"O_CLOEXEC",0))
                fd=os.open(name,flags,0o600)
                payload=json.dumps(
                    manifest,sort_keys=True,separators=(",",":"),
                    ensure_ascii=True).encode("ascii")+b"\n"
                written=0
                while written<len(payload):
                    step=os.write(fd,payload[written:])
                    if step<=0:
                        raise OSError
                    written+=step
                os.fsync(fd)
            finally:
                if fd is not None:os.close(fd)
            if inspect_sqlite_backup(source)!=backup:
                raise ValueError
            return manifest
    except K10SourceFixtureError:
        raise
    except Exception:
        raise K10SourceFixtureError("K10_SOURCE_FIXTURE_NOT_QUALIFIED") from None


def main():
    p=argparse.ArgumentParser(
        description="Create sensitive PRIVATE disposable REGTEST transfer fixture")
    p.add_argument("--core-dir",required=True,type=Path)
    p.add_argument("--new-private-output-dir",required=True,type=Path)
    p.add_argument("--confirm-disposable-regtest",action="store_true")
    options=p.parse_args()
    try:
        report=generate_disposable_core_fixture(
            options.core_dir,options.new_private_output_dir,
            authorized=options.confirm_disposable_regtest)
        print("K10_SOURCE_PRIVATE_DISPOSABLE_FIXTURE_GENERATED")
        print("PRIVATE BACKUP — keep offline, do not publish or attach to issues.")
        print("Backup SHA-256: "+report["backup_sha256"])
        print("Public descriptor SHA-256: "+report["public_descriptor_sha256"])
        return 0
    except K10SourceFixtureError as exc:
        print(exc.args[0])
        return 1


if __name__=="__main__":
    raise SystemExit(main())
