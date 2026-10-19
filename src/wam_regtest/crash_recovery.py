"""K-09 operator-only, READ-ONLY crash residue inventory.

The DEV WAM review identified TWO publication crash windows:
1. .stage-<hex> survives power loss during the long ciphertext write/fsync
   or after POSIX link but before unlink (both stage+snapshot still present).
2. snapshot-(anchored_generation+K).enc survives power loss before the native
   OS anchor advances; multiple crashes can leave a SET of future snapshots.

Neither form grants authority to remove encrypted data. A future snapshot may
include signed or uncertain reservations that were never persisted elsewhere.
This module ONLY produces a fixed, redacted LOCKED inventory after native
owner credential authentication; no path, name, byte, password or key escapes.

NO DELETE, QUARANTINE, RESTORE, ANCHOR REWRITE, SIGN, OR BROADCAST API HERE.
"""
from __future__ import annotations

from hashlib import sha256
import base64
import json
import os
from pathlib import Path
import re
import stat


STAGE=re.compile(r"\.stage-[0-9a-f]{32}\Z")
SNAPSHOT=re.compile(r"snapshot-([0-9]{9})\.enc\Z")
DIGEST=re.compile(r"[0-9a-f]{64}\Z")
MAX_CANDIDATES=32


class CrashRecoveryRefusal(ValueError):
    pass


def _deny(reason):
    raise CrashRecoveryRefusal(reason)


def _candidate_inventory(directory, anchored_generation):
    """Bounded, non-authorizing POSIX/Windows native-private directory view.

    Caller must hold original per-wallet native lease and vault file lock,
    and must have checked native vault directory custody and anchor identity.
    These paths are ONLY lstat'ed for a read-only count; a later destructive
    operation cannot use this snapshot to justify unlink or OS handle reuse.
    """
    if (type(directory) is not type(Path()) or not directory.is_absolute()
            or type(anchored_generation) is not int
            or not 1<=anchored_generation<10**9):
        _deny("K09_RESIDUE_SCOPE_DENIED")
    try:
        first={}
        for entry in directory.iterdir():
            name=entry.name
            snap=SNAPSHOT.fullmatch(name)
            stage=STAGE.fullmatch(name)
            if not stage and not (snap and int(snap[1])>anchored_generation):
                continue
            if len(first)>=MAX_CANDIDATES:
                _deny("K09_RESIDUE_COUNT_EXCEEDED")
            info=entry.lstat()
            if (not stat.S_ISREG(info.st_mode)
                    or not 1<=info.st_nlink<=2):
                _deny("K09_RESIDUE_NATIVE_METADATA_DENIED")
            first[name]=(
                info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,
                info.st_ctime_ns,info.st_nlink,
                bool(stage),0 if not snap else int(snap[1]),
            )
        # A preview is NOT a trusted snapshot of mutable files. At least
        # reject any ordinary same-process mutation between two inspections.
        seen={}
        for entry in directory.iterdir():
            if entry.name not in first:
                if (STAGE.fullmatch(entry.name)
                        or (SNAPSHOT.fullmatch(entry.name)
                            and int(SNAPSHOT.fullmatch(entry.name)[1])
                            >anchored_generation)):
                    _deny("K09_RESIDUE_CHANGED")
                continue
            info=entry.lstat()
            if not stat.S_ISREG(info.st_mode):
                _deny("K09_RESIDUE_NATIVE_METADATA_DENIED")
            seen[entry.name]=(
                info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,
                info.st_ctime_ns,info.st_nlink,
                first[entry.name][6],first[entry.name][7],
            )
        if first!=seen:
            _deny("K09_RESIDUE_CHANGED")
        stages=[meta for meta in first.values() if meta[6]]
        future=[meta for meta in first.values() if not meta[6]]
        # A stage and a future snapshot may be POSIX hard links to the
        # same encrypted data when the process died between link/unlink.
        # This is evidence of a *possibility*, NOT cleanup authorization.
        pairs=sum(1 for s in stages if any(
            (s[0],s[1])==(x[0],x[1]) for x in future))
        if pairs>len(stages):
            _deny("K09_RESIDUE_IDENTITY_DENIED")
        return {
            "stage_count":len(stages),
            "future_snapshot_count":len(future),
            "stage_future_snapshot_link_pairs":pairs,
            "multiple_future_generations":len({m[7] for m in future})>1,
            "oldest_anchored_generation":anchored_generation,
            "candidate_count":len(first),
            "candidates_authenticated":False,
            "safe_to_discard_proven":False,
            "signed_or_uncertain_reservations_reconciled":False,
            "operator_discard_available":False,
            "mainnet_allowed":False,
        }
    except CrashRecoveryRefusal:
        raise
    except (OSError,ValueError,TypeError):
        _deny("K09_RESIDUE_INSPECTION_DENIED")


def inspect_owner_crash_residue(vault, password, *, authorized=False):
    """Authenticated *read-only* preview under the real native wallet lease.

    Locked original owner must supply the existing password. We check the
    native-anchored ciphertext SHA and authenticate its exact REGTEST owner
    envelope. Never call vault.restore(), never interpret residue ciphertext,
    never delete/relabel a stage/snapshot or change the native anchor.
    """
    from .vault import CheckpointVault
    from . import custody
    from .wsp_live import REGTEST_GENESIS
    from wam_sp.file_lock import exclusive_file_lock
    from wam_sp.keystore import unseal
    if authorized is not True:
        _deny("K09_OPERATOR_CONSENT_REQUIRED")
    if (type(vault) is not CheckpointVault
            or type(password) is not bytes
            or not 12<=len(password)<=1024):
        _deny("K09_ORIGINAL_OWNER_INPUT_DENIED")
    try:
        with vault.anchor.lease(), exclusive_file_lock(
                vault.directory/".vault.lock"):
            vault._storage.validate_directory(vault.directory)
            record=vault.anchor.read()
            if (type(record) is not tuple or len(record)!=2
                    or type(record[0]) is not int
                    or not 1<=record[0]<10**9
                    or type(record[1]) is not str
                    or not DIGEST.fullmatch(record[1])
                    or record!=vault._expected):
                _deny("K09_NATIVE_ANCHOR_DENIED")
            ciphertext=vault._storage.read(
                vault.directory,vault._filename(record[0]))
            if sha256(ciphertext).hexdigest()!=record[1]:
                _deny("K09_ANCHORED_CIPHERTEXT_CHANGED")
            raw=unseal(ciphertext,password,b"recovery")
            if not 2<=len(raw)<=32*1024*1024:
                _deny("K09_ANCHORED_PAYLOAD_DENIED")
            data=json.loads(raw)
            profile=custody.envelope_profile()
            from wam_sp.watcher import GENESIS
            if (type(data) is not dict
                    or set(data)!=set(profile)|{
                        "disposable_regtest","network","wallet_id",
                        "generation","keys","checkpoint"}
                    or any(type(data[key]) is not type(value)
                           or data[key]!=value for key,value in profile.items())
                    or data.get("disposable_regtest") is not True
                    or data.get("network")!=GENESIS
                    or data["network"]!=REGTEST_GENESIS
                    or data.get("wallet_id")!=vault.anchor.wallet_id
                    or type(data.get("generation")) is not int
                    or data["generation"]!=record[0]
                    or any(type(data.get(k)) is not str
                           or not 50<=len(data[k])<=32*1024*1024
                           for k in ("keys","checkpoint"))):
                _deny("K09_ANCHORED_OWNER_IDENTITY_DENIED")
            plan=_candidate_inventory(vault.directory,record[0])
            if vault.anchor.read()!=record or vault._expected!=record:
                _deny("K09_NATIVE_ANCHOR_CHANGED")
            return {
                "status":"K09_OWNER_VERIFIED_READ_ONLY_RESIDUE_PREVIEW",
                "network":"regtest",
                "anchored_generation":record[0],
                "original_anchor_verified":True,
                "original_owner_envelope_authenticated":True,
                **{k:v for k,v in plan.items()
                   if k!="oldest_anchored_generation"},
                "wallet_unlocked":False,
                "signer_allowed":False,"broadcast_allowed":False,
                "automatic_cleanup_allowed":False,
            }
    except CrashRecoveryRefusal:
        raise
    except Exception:
        _deny("K09_OWNER_CRASH_PREVIEW_DENIED")
