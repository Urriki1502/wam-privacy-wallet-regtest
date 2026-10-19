"""K-10 original REGTEST wallet readiness, not portable-restore unlock.

READ-ONLY owner-preflight for an *already existing native-anchored wallet*.
Actual opening and signing still require the original managed GUI's separate
passphrase, native vault restore, real Core scanner sync and exact-intent
approvals. This never opens a WalletSession, bypasses crash residue, produces
an active signer, accesses Core wallet RPC, or changes a portable handoff.
"""
from __future__ import annotations

from pathlib import Path

class K10TestAccessError(ValueError):
    """Never include secrets or private platform paths."""


_EXPECTED={
    "status":"MANAGED_WALLET_ORIGINAL_CHECKPOINT_VERIFIED_LOCKED",
    "network":"regtest","wallet_locked":True,
    "signer_allowed":False,"broadcast_allowed":False,
    "balance_verified":False,"original_native_anchor_verified":True,
    "original_encrypted_checkpoint_verified":True,"mainnet_allowed":False,
    "supervisor_authenticated":True,
    "supervisor_core_identity_verified":True,
}


def inspect_original_regtest_test_readiness(
        root,core_dir,wsp_source,password,*,authorized=False):
    """Check only whether the ORIGINAL-wallet manual unlock may be attempted.

    The caller must supply the original wallet passphrase and native owner
    authorization. An apparently clean source/preflight cannot grant the
    K-10 moved-wallet restoration any signing permission.
    """
    if authorized is not True:
        raise K10TestAccessError("K10_ORIGINAL_TEST_CONSENT_REQUIRED")
    if (any(type(x) is not type(Path()) or not x.is_absolute()
            for x in (root,core_dir,wsp_source))
            or type(password) is not bytes or not 12<=len(password)<=1024):
        raise K10TestAccessError("K10_ORIGINAL_TEST_INPUT_DENIED")
    rpc=None
    try:
        from .managed_wallet_binding import verify_locked_wallet
        from .managed_scan_client import ManagedScanRpc
        from .supervisor_client import control
        from .core_supervisor import _profile_read
        from .wsp_live import REGTEST_GENESIS

        before=control(root,"status",timeout=3)
        if (type(before) is not dict
                or before.get("state")!="ready"
                or before.get("core_process_owned") is not True
                or type(before.get("height")) is not int
                or before["height"]<0):
            raise K10TestAccessError("K10_ORIGINAL_CORE_NOT_READY")
        profile=_profile_read(root)
        verified=verify_locked_wallet(
            root,core_dir,wsp_source,password,authorized=True)
        if type(verified) is not dict or verified!=_EXPECTED:
            raise K10TestAccessError("K10_ORIGINAL_OWNER_CHECKPOINT_DENIED")
        rpc=ManagedScanRpc(root,authorized_readonly=True)
        observed=rpc.attest()
        height=observed.get("blocks")
        tip=observed.get("bestblockhash")
        if (observed.get("chain")!="regtest"
                or type(height) is not int or height!=before["height"]
                or type(tip) is not str or len(tip)!=64
                or any(x not in "0123456789abcdef" for x in tip)
                or rpc.call("getblockhash",[0])!=REGTEST_GENESIS
                or rpc.call("getblockhash",[height])!=tip
                or rpc.call("getbestblockhash")!=tip):
            raise K10TestAccessError("K10_ORIGINAL_CHAIN_MISMATCH")
        if (control(root,"status",timeout=3)!=before
                or _profile_read(root)!=profile):
            raise K10TestAccessError("K10_ORIGINAL_STATE_CHANGED")
        return {
            "status":"K10_ORIGINAL_REGTEST_MANUAL_OPEN_PREFLIGHT_ONLY",
            "network":"regtest",
            "original_native_anchor_verified":True,
            "original_checkpoint_authenticated":True,
            "current_core_tip_read_verified":True,
            "manual_gui_original_wallet_open_may_be_attempted":True,
            "new_os_wallet_restored":False,
            "portable_clean_host_unlocked":False,
            "full_reservation_reconciliation_proven":False,
            "physical_recovery_qualified":False,
            "active_signer_session_created":False,
            "signer_allowed":False,
            "broadcast_allowed":False,
            "mainnet_allowed":False,
        }
    except K10TestAccessError:
        raise
    except Exception:
        raise K10TestAccessError("K10_ORIGINAL_TEST_PREFLIGHT_UNVERIFIED") from None
    finally:
        if rpc is not None:
            rpc.close()
