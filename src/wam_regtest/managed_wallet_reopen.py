"""T05 encrypted create-once locator for the SAME native-anchored WSP wallet.

This is not an alternative vault/anchor or a new seed format. Only the wallet
identifier and immutable REGTEST Core identity are sealed with the existing
WSP envelope and stored under native private custody. The checkpoint, keys,
reservations and history remain in CheckpointVault.
"""
from __future__ import annotations

import json
import re

FILENAME = "managed-reopen.enc"
SCHEMA = "wam-t05-managed-wallet-reopen/v1"
CONTEXT = b"recovery"  # Existing WSP purpose allowlist; exact schema isolates content.


class ManagedWalletReopenError(ValueError):
    pass


def _pairs(pairs):
    result={}
    for key,value in pairs:
        if key in result:
            raise ManagedWalletReopenError("MANAGED_WALLET_DUPLICATE_FIELD_DENIED")
        result[key]=value
    return result


def _validate(profile):
    if (type(profile) is not dict
            or set(profile)!={"schema","wallet_id","network","genesis",
                               "core_sha256","cli_sha256","mainnet_allowed"}
            or profile.get("schema")!=SCHEMA
            or profile.get("network")!="regtest"
            or profile.get("mainnet_allowed") is not False
            or type(profile.get("wallet_id")) is not str
            or re.fullmatch(r"[0-9a-f]{32}",profile["wallet_id"]) is None
            or any(type(profile.get(key)) is not str
                   or re.fullmatch(r"[0-9a-f]{64}",profile[key]) is None
                   for key in ("core_sha256","cli_sha256"))
            ):
        raise ManagedWalletReopenError("MANAGED_WALLET_PROFILE_DENIED")
    from .wsp_live import REGTEST_GENESIS
    if profile.get("genesis")!=REGTEST_GENESIS:
        raise ManagedWalletReopenError("MANAGED_WALLET_CHAIN_DENIED")
    return profile


def make(wallet_id, receipt):
    from .wsp_live import REGTEST_GENESIS
    if type(receipt) is not dict:
        raise ManagedWalletReopenError("MANAGED_WALLET_CORE_RECEIPT_DENIED")
    return _validate({
        "schema":SCHEMA, "wallet_id":wallet_id,
        "network":"regtest","genesis":REGTEST_GENESIS,
        "core_sha256":receipt.get("wamd_sha256"),
        "cli_sha256":receipt.get("wam_cli_sha256"),
        "mainnet_allowed":False,
    })


def publish(directory, profile, password):
    """Create-only; an existing/corrupt locator is never replaced or repaired."""
    from . import custody
    from wam_sp.keystore import seal
    value=_validate(profile)
    if type(password) is not bytes or not 12<=len(password)<=1024:
        raise ManagedWalletReopenError("MANAGED_WALLET_PASSWORD_DENIED")
    data=json.dumps(value,sort_keys=True,separators=(",",":")).encode("ascii")
    try:
        storage=custody.storage()
        storage.validate_directory(directory)
        storage.publish(directory,FILENAME,seal(data,password,CONTEXT))
        observed=read(directory,password)
        if observed!=value:
            raise ManagedWalletReopenError("MANAGED_WALLET_PUBLICATION_UNVERIFIED")
    except ManagedWalletReopenError:
        raise
    except Exception:
        raise ManagedWalletReopenError("MANAGED_WALLET_PUBLICATION_DENIED") from None
    return value


def read(directory,password):
    from . import custody
    from wam_sp.keystore import unseal
    if type(password) is not bytes or not 12<=len(password)<=1024:
        raise ManagedWalletReopenError("MANAGED_WALLET_PASSWORD_DENIED")
    try:
        storage=custody.storage()
        storage.validate_directory(directory)
        ciphertext=storage.read(directory,FILENAME)
        raw=unseal(ciphertext,password,CONTEXT)
        if not 2<=len(raw)<=1024:
            raise ManagedWalletReopenError("MANAGED_WALLET_PROFILE_DENIED")
        profile=json.loads(raw.decode("ascii"),object_pairs_hook=_pairs)
        return _validate(profile)
    except ManagedWalletReopenError:
        raise
    except Exception:
        # Neither private file paths nor decryption errors go to the GUI.
        raise ManagedWalletReopenError("MANAGED_WALLET_READ_DENIED") from None


def preflight_existing_checkpoint(core_dir, datadir, wsp_source, password, *,
                                  authorized=False, keychain=None):
    """Explicit READ-ONLY reattachment preflight; not a live wallet/session.

    Validate exact signed Core binary, pinned WSP code, native custody, original
    wallet identity, original OS anti-rollback anchor and encrypted checkpoint.
    No database, scanner, keyring or wallet RPC is instantiated. A positive
    receipt NEVER permits balance display, signing or broadcast.
    """
    from pathlib import Path
    from . import custody
    from .core import verified_core_paths
    from .vault import CheckpointVault
    from .wsp_live import _pinned_source
    if authorized is not True:
        raise ManagedWalletReopenError("MANAGED_WALLET_PREFLIGHT_CONSENT_REQUIRED")
    if (type(core_dir) is not type(Path()) or not core_dir.is_absolute()
            or type(datadir) is not type(Path()) or not datadir.is_absolute()
            or type(wsp_source) is not type(Path()) or not wsp_source.is_absolute()):
        raise ManagedWalletReopenError("MANAGED_WALLET_PREFLIGHT_PATH_DENIED")
    if type(password) is not bytes or not 12<=len(password)<=1024:
        raise ManagedWalletReopenError("MANAGED_WALLET_PASSWORD_DENIED")
    try:
        _,_,receipt=verified_core_paths(core_dir)
        _pinned_source(wsp_source)
        if receipt["platform"]!=custody.platform_name():
            raise ManagedWalletReopenError("MANAGED_WALLET_PREFLIGHT_PLATFORM_DENIED")
        storage=custody.storage()
        storage.validate_directory(datadir)
        folder=datadir/"wallet-vault"
        storage.validate_directory(folder)
        profile=read(folder,password)
        if profile!=make(profile["wallet_id"],receipt):
            raise ManagedWalletReopenError("MANAGED_WALLET_CORE_CHANGED_DENIED")
        anchor=custody.anchor(profile["wallet_id"],keychain)
        vault=CheckpointVault(folder,anchor,wsp_source)
        # Stable native wallet lease excludes an in-flight anchor generation
        # replacement while the existing sealed snapshot is authenticated.
        with anchor.lease():
            record=anchor.read()
            if record is None or vault._expected!=record:
                raise ManagedWalletReopenError("MANAGED_WALLET_ANCHOR_CHANGED_DENIED")
            payload=vault._load_payload(password,record)
            if payload["wallet_id"]!=profile["wallet_id"] or payload["generation"]!=record[0]:
                raise ManagedWalletReopenError("MANAGED_WALLET_CHECKPOINT_MISMATCH")
            if anchor.read()!=record:
                raise ManagedWalletReopenError("MANAGED_WALLET_ANCHOR_CHANGED_DENIED")
        return {
            "status":"MANAGED_WALLET_ORIGINAL_CHECKPOINT_VERIFIED_LOCKED",
            "network":"regtest",
            "wallet_locked":True,
            "signer_allowed":False,
            "broadcast_allowed":False,
            "balance_verified":False,
            "original_native_anchor_verified":True,
            "original_encrypted_checkpoint_verified":True,
            "mainnet_allowed":False,
        }
    except ManagedWalletReopenError:
        raise
    except Exception:
        # No errors, failed credential details, file paths or secret values
        # may escape into GUI/logs. Never auto-create a replacement wallet.
        raise ManagedWalletReopenError("MANAGED_WALLET_PREFLIGHT_DENIED") from None
