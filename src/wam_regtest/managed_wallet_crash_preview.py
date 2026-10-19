"""Owner-initiated GUI entrypoint for K-09 *read-only* crash forensics.

Use existing persistent supervisor, immutable Core, pinned WSP and original
native vault/anti-rollback anchor. Never create a replacement wallet, open
signer, mutate residue, alter Core or infer a successful restoration.
"""
from __future__ import annotations

from pathlib import Path

class CrashPreviewError(ValueError):
    pass

def inspect_managed_crash_preview(root,core_dir,wsp_source,password,*,
                                  authorized=False,observe_recent_core=False,
                                  keychain=None):
    if authorized is not True or type(observe_recent_core) is not bool:
        raise CrashPreviewError("K09_MANAGED_PREVIEW_CONSENT_DENIED")
    if (type(root) is not type(Path) or not root.is_absolute()
            or type(core_dir) is not type(Path) or not core_dir.is_absolute()
            or type(wsp_source) is not type(Path) or not wsp_source.is_absolute()
            or type(password) is not bytes or not 12<=len(password)<=1024):
        raise CrashPreviewError("K09_MANAGED_PREVIEW_INPUT_DENIED")
    rpc=None
    try:
        from . import custody
        from .core import verified_core_paths
        from .core_supervisor import _profile_read
        from .managed_wallet_reopen import read,make
        from .managed_scan_client import ManagedScanRpc
        from .supervisor_client import control
        from .supervisor_store import _root
        from .vault import CheckpointVault
        from .crash_recovery import inspect_owner_crash_residue
        from .wsp_live import _pinned_source, REGTEST_GENESIS

        _root(root)
        before=control(root,"status",timeout=3)
        if (type(before) is not dict or before.get("state")!="ready"
                or before.get("core_process_owned") is not True
                or type(before.get("height")) is not int):
            raise CrashPreviewError("K09_MANAGED_CORE_NOT_READY")
        core_profile=_profile_read(root)
        _,_,receipt=verified_core_paths(core_dir)
        if (core_profile.get("network")!="regtest"
                or core_profile.get("genesis")!=REGTEST_GENESIS
                or core_profile.get("core_sha256")!=receipt["wamd_sha256"]
                or core_profile.get("cli_sha256")!=receipt["wam_cli_sha256"]
                or receipt.get("platform")!=custody.platform_name()):
            raise CrashPreviewError("K09_MANAGED_CORE_MISMATCH")
        _pinned_source(wsp_source)
        folder=root/"chain"/"wallet-vault"
        storage=custody.storage()
        storage.validate_directory(root/"chain")
        storage.validate_directory(folder)
        wallet=read(folder,password)
        if wallet!=make(wallet["wallet_id"],receipt):
            raise CrashPreviewError("K09_MANAGED_WALLET_MISMATCH")
        anchor=custody.anchor(wallet["wallet_id"],keychain)
        vault=CheckpointVault(folder,anchor,wsp_source)
        if observe_recent_core:
            rpc=ManagedScanRpc(root,authorized_readonly=True)
        result=inspect_owner_crash_residue(
            vault,password,authorized=True,audit_reservations=True,
            core_read_rpc=rpc,
            authorized_core_observation=observe_recent_core)
        after=control(root,"status",timeout=3)
        if after!=before or _profile_read(root)!=core_profile:
            raise CrashPreviewError("K09_MANAGED_SUPERVISOR_CHANGED")
        mandatory={
            "status":"K09_OWNER_VERIFIED_READ_ONLY_RESIDUE_PREVIEW",
            "network":"regtest",
            "original_anchor_verified":True,
            "original_owner_envelope_authenticated":True,
            "safe_to_discard_proven":False,
            "operator_discard_available":False,
            "wallet_unlocked":False,
            "signer_allowed":False,
            "broadcast_allowed":False,
            "automatic_cleanup_allowed":False,
        }
        if (type(result) is not dict or
                any(result.get(k)!=v for k,v in mandatory.items())):
            raise CrashPreviewError("K09_MANAGED_EVIDENCE_INVALID")
        # The original result is already redacted and bounded. Never expose
        # any private paths, account identity, outpoints or exception details.
        return result
    except CrashPreviewError:
        raise
    except Exception:
        raise CrashPreviewError("K09_MANAGED_PREVIEW_UNVERIFIED") from None
    finally:
        if rpc is not None:
            rpc.close()
