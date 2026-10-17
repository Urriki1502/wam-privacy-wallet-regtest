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
