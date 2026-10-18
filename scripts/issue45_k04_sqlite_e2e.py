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
import time

from wam_regtest.core import _read_cli,verified_core_paths
from wam_regtest.custody import create_directory
from wam_regtest.core_sqlite_import import (
    inspect_sqlite_backup,stage_verified_backup,verify_restored_core_wallet,
)
from wam_regtest.owned_start import disposable_core
from wam_regtest.v1_contracts import core_descriptor_identity
from wam_regtest.wsp_live import REGTEST_GENESIS


def _wallet_rpc(owned,wallet,method,*params,backup_target=None,restore_source=None):
    """Strictly scoped test-only Core CLI; NEVER widen managed RPC authority.

    This wrapper only operates on a caller-held disposable_core() instance
    whose actual process, loopback socket and WAM REGTEST chain are attested.
    Wallet names and method/parameter arity are fixed for this PUBLIC fixture.
    """
    commands={
        (None,"createwallet"):("k04-source",),
        ("k04-source","getwalletinfo"):(),
        ("k04-source","getnewaddress"):(),
        (None,"generatetoaddress"):None,
        (None,"getblockchaininfo"):(),
        (None,"getblockhash"):("0",),
        ("k04-source","listdescriptors"):("false",),
        ("k04-source","backupwallet"):None,
        (None,"restorewallet"):None,
        ("k04-reviewed","getwalletinfo"):(),
        ("k04-reviewed","listdescriptors"):("false",),
    }
    key=(wallet,method)
    if (key not in commands or
            (commands[key] is not None and params!=commands[key])):
        raise ValueError("K04_FIXTURE_RPC_SCOPE_DENIED")
    if key==(None,"generatetoaddress"):
        if (len(params)!=2 or params[0]!="101"
                or type(params[1]) is not str
                or not 15<=len(params[1])<=150):
            raise ValueError("K04_FIXTURE_MINING_SCOPE_DENIED")
    if key==("k04-source","backupwallet"):
        if (type(backup_target) is not type(Path())
                or not backup_target.is_absolute()
                or backup_target.name!="core-wallet-backup.dat"
                or params!=(str(backup_target),)):
            raise ValueError("K04_FIXTURE_BACKUP_PATH_DENIED")
    elif backup_target is not None:
        raise ValueError("K04_FIXTURE_BACKUP_UNEXPECTED")
    if key==(None,"restorewallet"):
        if (type(restore_source) is not type(Path())
                or not restore_source.is_absolute()
                or restore_source.suffix!=".dat"
                or params!=("k04-reviewed",str(restore_source))):
            raise ValueError("K04_FIXTURE_RESTORE_PATH_DENIED")
    elif restore_source is not None:
        raise ValueError("K04_FIXTURE_RESTORE_UNEXPECTED")
    if owned.process.poll() is not None:
        raise ValueError("K04_FIXTURE_OWNED_CORE_EXITED")
    observed=owned.read.attest()
    if observed.get("chain")!="regtest" or observed.get("blocks",0)<0:
        raise ValueError("K04_FIXTURE_CHAIN_UNVERIFIED")
    base=[str(owned.cli),f"-datadir={owned.directory}"]
    if wallet is not None:
        base.append(f"-rpcwallet={wallet}")
    if __import__("sys").platform=="win32":
        # Global Windows read_cli deliberately rejects wallet-specific RPC.
        # Scope ONLY this disposable fixture's verified WAM Core CLI; do not
        # grant getwalletinfo/restorewallet to GUI, scanner or common RPC.
        from wam_regtest.windows_core_regtest_smoke import _rpc,_host_env
        from wam_regtest.windows_core_transport import verified_core_paths
        from wam_regtest.network_policy import local_rpc_port
        _,verified_cli,_=verified_core_paths(owned.cli.parent)
        if verified_cli!=owned.cli:
            raise ValueError("K04_FIXTURE_CLI_IDENTITY_DENIED")
        return _rpc(owned.cli,owned.directory,local_rpc_port(owned.directory),
                    _host_env(owned.directory),*(base[2:]+[method,*params]),
                    timeout=45)
    return _read_cli(base+[method,*params],timeout=45)


def _stable_disposable_core_backup(source):
    """Only the just-written PUBLIC REGTEST fixture may wait for its backup.

    On Windows the Core SQLite backup creation and observed file length can
    race very briefly. Never treat an inconsistent file as imported; wait
    boundedly for two independent, byte-for-byte matching immutable reads.
    This is NOT used by the real GUI/importer or for supplied user wallets.
    No short/incomplete read is ever accepted.
    """
    from wam_regtest.core_sqlite_import import (
        inspect_sqlite_backup,CoreSqliteImportError,
    )
    deadline=time.monotonic()+8
    previous=None
    while time.monotonic()<deadline:
        try:
            observed=inspect_sqlite_backup(source)
            if observed==previous:
                return observed
            previous=observed
        except CoreSqliteImportError as error:
            if error.args!=("K04_SQLITE_SIZE_OR_SHORT_READ_CHANGED",):
                raise
            previous=None
        time.sleep(.2)
    raise ValueError("K04_DISPOSABLE_SOURCE_NOT_STABLE")


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
            # K-06: native Core descriptor identities cannot become WSP
            # scan/spend identities, regardless of wallet name or .dat path.
            from wam_regtest.account_isolation import (
                CoreAccount,AccountRegistry,AccountIsolationError,
            )
            source_account=CoreAccount.from_core_public(
                name="k04-source",chain=chain["chain"],genesis=genesis,
                wallet_info=source_info,descriptors=source_desc)
            if AccountRegistry(core=(source_account,)).public_summary()[
                    "balances_aggregated"] is not False:
                raise ValueError("K06_CORE_BALANCE_MIX_DENIED")
            _wallet_rpc(source,"k04-source","backupwallet",str(exported),
                        backup_target=exported)
            preliminary=_stable_disposable_core_backup(exported)
            # A separate open/hash must independently agree with the two
            # stable native-fd reads. Do not accept an incomplete backup.
            source_sha=sha256(exported.read_bytes()).hexdigest()
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
                                     "k04-reviewed",str(staged),
                                     restore_source=staged)
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
                restored_account=CoreAccount.from_core_public(
                    name="k04-reviewed",chain=target_chain["chain"],
                    genesis=target_genesis,wallet_info=target_info,
                    descriptors=target_desc)
                if (restored_account.descriptor_identity
                        !=source_account.descriptor_identity):
                    raise ValueError("K06_CORE_IDENTITY_CHANGED")
                # The SAME descriptor set under a different Core wallet
                # name must never be registered as a second independent
                # owner; no WSP signer can ever claim this Core identity.
                try:
                    AccountRegistry(core=(source_account,restored_account))
                except AccountIsolationError as err:
                    if err.args!=("K06_CORE_DESCRIPTOR_OVERLAP_DENIED",):
                        raise
                else:
                    raise ValueError("K06_DUPLICATE_CORE_OWNER_NOT_REFUSED")
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
                    "k06_genuine_core_descriptor_owner_isolation":True,
                    "k06_core_duplicate_owner_refused":True,
                    "k06_core_keys_not_reinterpreted_as_wsp":True,
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
