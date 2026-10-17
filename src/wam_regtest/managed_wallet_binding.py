"""T05/Q05: a bounded, read-only binding between Fusion supervisor and vault.

This is NOT a wallet RPC bridge and never provides an unlocked wallet,
balance, WSP scanning, signing, broadcast, or access to Core credentials.
It cross-checks the authenticated live owner and immutable Core profile
before and after verifying the ORIGINAL platform-anchored checkpoint.
"""
from __future__ import annotations

from pathlib import Path

from .managed_wallet_reopen import preflight_existing_checkpoint
from .supervisor_client import control
from .core_supervisor import _profile_read
from .supervisor_store import _root
from .core import verified_core_paths
from .wsp_live import REGTEST_GENESIS


class ManagedWalletBindingError(ValueError):
    pass


def verify_locked_wallet(root, core_dir, wsp_source, password, *,
                         authorized=False, keychain=None):
    """Operator-initiated, fail-closed, *non-spending* checkpoint verification."""
    if authorized is not True:
        raise ManagedWalletBindingError("MANAGED_WALLET_BINDING_CONSENT_REQUIRED")
    if (type(root) is not type(Path()) or not root.is_absolute()
            or type(core_dir) is not type(Path()) or not core_dir.is_absolute()
            or type(wsp_source) is not type(Path()) or not wsp_source.is_absolute()
            or type(password) is not bytes or not 12 <= len(password) <= 1024):
        raise ManagedWalletBindingError("MANAGED_WALLET_BINDING_INPUT_DENIED")
    try:
        _root(root)
        before=control(root,"status",timeout=3)
        if (before["state"]!="ready" or before["core_process_owned"] is not True
                or type(before["height"]) is not int):
            raise ManagedWalletBindingError("MANAGED_WALLET_BINDING_CORE_NOT_READY")
        profile=_profile_read(root)
        _,_,receipt=verified_core_paths(core_dir)
        if (profile["network"]!="regtest" or profile["genesis"]!=REGTEST_GENESIS
                or profile["core_sha256"]!=receipt["wamd_sha256"]
                or profile["cli_sha256"]!=receipt["wam_cli_sha256"]):
            raise ManagedWalletBindingError("MANAGED_WALLET_BINDING_CORE_MISMATCH")
        checkpoint=preflight_existing_checkpoint(
            core_dir,root/"chain",wsp_source,password,
            authorized=True,keychain=keychain)
        expected={
            "status":"MANAGED_WALLET_ORIGINAL_CHECKPOINT_VERIFIED_LOCKED",
            "network":"regtest","wallet_locked":True,
            "signer_allowed":False,"broadcast_allowed":False,
            "balance_verified":False,"original_native_anchor_verified":True,
            "original_encrypted_checkpoint_verified":True,
            "mainnet_allowed":False,
        }
        if checkpoint!=expected:
            raise ManagedWalletBindingError("MANAGED_WALLET_BINDING_CHECKPOINT_UNVERIFIED")
        after=control(root,"status",timeout=3)
        if after!=before or _profile_read(root)!=profile:
            raise ManagedWalletBindingError("MANAGED_WALLET_BINDING_STATE_CHANGED")
        # The original credential and checkpoint were authenticated, but NO
        # WSP scanner was run and NO live balance/receive history is attested.
        return dict(expected,supervisor_authenticated=True,
                    supervisor_core_identity_verified=True)
    except ManagedWalletBindingError:
        raise
    except Exception:
        # Strip external exception details, passwords and filesystem paths.
        raise ManagedWalletBindingError("MANAGED_WALLET_BINDING_DENIED") from None
