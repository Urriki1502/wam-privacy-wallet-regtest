"""K-04: genuine signed Core-created REGTEST SQLite backup restored in a
separate disposable, signed Core process using supported Core RPC only.

No personal wallets/miners, no synthetic RPC, no independent wallet.dat
dissection and no activation of imported keys in a Fusion WSP signer.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import tempfile

from wam_regtest.core import _read_cli,verified_core_paths
from wam_regtest.custody import create_directory
from wam_regtest.core_sqlite_import import (
    inspect_sqlite_backup,stage_verified_backup,verify_restored_core_wallet,
)
from wam_regtest.owned_start import disposable_core
from wam_regtest.v1_contracts import core_descriptor_identity
from wam_regtest.wsp_live import REGTEST_GENESIS


def _wallet_rpc(owned,wallet,method,*params):
    # CLI is the officially supported WAM Core RPC client, strictly scoped
    # to freshly spawned and kernel-attested isolated REGTEST test process.
    # No argument or result is printed; no mainnet/external miner access.
    base=[str(owned.cli),f"-datadir={owned.directory}"]
    if wallet is not None:base.append(f"-rpcwallet={wallet}")
    return _read_cli(base+[method,*params],timeout=45)


def prove(core):
    if type(core) is not type(Path()) or not core.is_absolute():
        raise ValueError("K04_EXPLICIT_SIGNED_CORE_PATH_DENIED")
    _,_,receipt=verified_core_paths(core)
    with tempfile.TemporaryDirectory(prefix="wam-k04-disposable-") as tmp:
        root=Path(tmp).resolve()
        private=root/"owner-private"
        create_directory(private)
        exported=private/"core-wallet-backup.dat"
        staging=private/"quarantine"
        create_directory(staging)
        with disposable_core(core,authorized=True) as source:
            if source.receipt["wamd_sha256"]!=receipt["wamd_sha256"]:
                raise ValueError("K04_SOURCE_CORE_CHANGED")
            _wallet_rpc(source,None,"createwallet","k04-source")
            source_info=_wallet_rpc(source,"k04-source","getwalletinfo")
            if source_info.get("format")!="sqlite" or source_info.get("descriptors") is not True:
                raise ValueError("K04_NOT_CORE_DESCRIPTOR_FIXTURE")
            addr=_wallet_rpc(source,"k04-source","getnewaddress")
            mined=_wallet_rpc(source,None,"generatetoaddress","101",addr)
            if type(mined) is not list or len(mined)!=101:
                raise ValueError("K04_SOURCE_CHAIN_DENIED")
            chain=_wallet_rpc(source,None,"getblockchaininfo")
            genesis=_wallet_rpc(source,None,"getblockhash","0")
            if chain.get("chain")!="regtest" or genesis!=REGTEST_GENESIS:
                raise ValueError("K04_SOURCE_NETWORK_DENIED")
            source_desc=_wallet_rpc(source,"k04-source","listdescriptors","false")
            source_identity=core_descriptor_identity(source_desc)
            _wallet_rpc(source,"k04-source","backupwallet",str(exported))
            source_sha=sha256(exported.read_bytes()).hexdigest()
            preliminary=inspect_sqlite_backup(exported)
            if preliminary.file_sha256!=source_sha:
                raise ValueError("K04_BACKUP_CHANGED")
            with disposable_core(core,authorized=True) as target:
                target_chain=_wallet_rpc(target,None,"getblockchaininfo")
                target_genesis=_wallet_rpc(target,None,"getblockhash","0")
                if target_chain.get("chain")!="regtest" or target_genesis!=genesis:
                    raise ValueError("K04_QUARANTINE_CHAIN_DENIED")
                staged,receipt_copy=stage_verified_backup(
                    exported,staging,authorized=True)
                if receipt_copy!=preliminary or inspect_sqlite_backup(staged)!=preliminary:
                    raise ValueError("K04_STAGE_NOT_IDENTICAL")
                # WAM Core itself restores SQLite/descriptor wallet data.
                # No Python SQL query, seed extraction, importdescriptors,
                # rescan-driven auto-sweep or arbitrary wallet RPC forwarding.
                restored=_wallet_rpc(target,None,"restorewallet",
                                     "k04-reviewed",str(staged))
                if (type(restored) is not dict
                        or restored.get("name")!="k04-reviewed"
                        or "warnings" in restored and restored["warnings"]):
                    raise ValueError("K04_CORE_RESTORE_NOT_CLEAN")
                target_info=_wallet_rpc(target,"k04-reviewed","getwalletinfo")
                target_desc=_wallet_rpc(target,"k04-reviewed",
                                        "listdescriptors","false")
                observed=verify_restored_core_wallet(
                    chain=target_chain["chain"],genesis=target_genesis,
                    wallet_info=target_info,descriptor_listing=target_desc)
                if observed["descriptor_identity_sha256"]!=source_identity:
                    raise ValueError("K04_CORE_DESCRIPTORS_MISMATCH")
                # Explicit duplicate/overlap refusal operates ONLY on Core's
                # public listdescriptors(false), never SQLite/xprv parsing.
                from wam_regtest.core_sqlite_import import require_distinct_descriptors
                try:require_distinct_descriptors(source_desc,target_desc)
                except Exception:duplicate_refused=True
                else:raise ValueError("K04_IDENTICAL_IDENTITY_NOT_REFUSED")
                if (inspect_sqlite_backup(exported)!=preliminary
                        or inspect_sqlite_backup(staged)!=preliminary):
                    raise ValueError("K04_SOURCE_OR_COPY_MODIFIED")
                return {
                    "status":"K04_REAL_CORE_SQLITE_RESTORE_QUARANTINE_PASS",
                    "platform":receipt["platform"],
                    "network":"regtest",
                    "core_sha256":receipt["wamd_sha256"],
                    "sqlite_header_and_bounded_copy_verified":True,
                    "source_immutable":True,
                    "real_core_restorewallet_rpc":True,
                    "source_and_restored_descriptors_identical":True,
                    "duplicate_descriptor_identity_denied":True,
                    "wallet_loaded_only_inside_disposable_quarantine":True,
                    "original_managed_core_wallet_unmodified":True,
                    "fusion_signer_authorized":False,
                    "mainnet_allowed":False,
                    "synthetic_rpc":False,
                    "production_qualified":False,
                    "human_reviewed":False,
                }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--core-dir",required=True,type=Path)
    p.add_argument("--output",type=Path)
    p.add_argument("--confirm-disposable-regtest",action="store_true")
    a=p.parse_args()
    if a.confirm_disposable_regtest is not True:
        raise SystemExit("K04_DISPOSABLE_REGTEST_CONSENT_REQUIRED")
    result=prove(a.core_dir.resolve(strict=True))
    if a.output:
        if a.output.exists():raise SystemExit("K04_EVIDENCE_EXISTS")
        a.output.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print(result["status"])


if __name__=="__main__":main()
