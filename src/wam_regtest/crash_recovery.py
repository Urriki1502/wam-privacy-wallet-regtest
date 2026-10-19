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


def _unique_json_pairs(pairs):
    obj={}
    for k,v in pairs:
        if k in obj:
            _deny("K09_ANCHORED_DUPLICATE_FIELD_DENIED")
        obj[k]=v
    return obj


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
            # Reserved publication prefixes must not be silently hidden from
            # recovery by truncated, unusual or attacker-supplied filenames.
            # Unknown state is a refusal, not an empty/clean inventory.
            if ((name.startswith(".stage-") and not stage)
                    or (name.startswith("snapshot-")
                        and (not snap or int(snap[1])==0))):
                _deny("K09_AMBIGUOUS_PUBLICATION_NAME_DENIED")
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
                # Catch both new valid candidates and new malformed names
                # introduced between the two read-only directory passes.
                snap=SNAPSHOT.fullmatch(entry.name)
                stage=STAGE.fullmatch(entry.name)
                if ((entry.name.startswith(".stage-") and not stage)
                        or (entry.name.startswith("snapshot-")
                            and (not snap or int(snap[1])==0))):
                    _deny("K09_AMBIGUOUS_PUBLICATION_NAME_DENIED")
                if stage or (snap and int(snap[1])>anchored_generation):
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



def _forensic_candidate_ledger(vault, password, record, original, plan, *,
                               core_read_rpc=None):
    """Read sealed stage/snapshot reservation evidence, never grant cleanup.

    The original native owner lease and vault lock are held by the caller.
    All residue bytes must pass their platform's strict no-follow/handle
    reader, including intact POSIX link-before-unlink pairs (nlink == 2).
    A torn stage or suspicious snapshot is UNKNOWN, never safe to discard.
    """
    from . import custody
    from .crash_ledger import (
        project_owner_ledger, compare_candidate_ledger, LedgerEvidenceError,
    )
    from .wsp_live import REGTEST_GENESIS
    from wam_sp.keystore import unseal

    if (plan["candidate_count"]>32 or plan["stage_count"]>8
            or plan["future_snapshot_count"]>8):
        _deny("K09_FORENSIC_SET_LIMIT_DENIED")
    if not callable(getattr(vault._storage,"read_crash_residue",None)):
        _deny("K09_NATIVE_FORENSIC_READER_REQUIRED")
    try:
        anchored=project_owner_ledger(original,password)
        observed_outpoints=set(anchored.reservations)
    except LedgerEvidenceError:
        _deny("K09_ANCHORED_LEDGER_UNVERIFIABLE")

    def identify():
        """Entire bounded candidate set and metadata; no pathname escapes."""
        members={}
        try:
            for entry in vault.directory.iterdir():
                stage=STAGE.fullmatch(entry.name)
                future=SNAPSHOT.fullmatch(entry.name)
                if not stage and not (future and int(future[1])>record[0]):
                    continue
                if len(members)>=32:
                    _deny("K09_FORENSIC_SET_LIMIT_DENIED")
                st=entry.lstat()
                if not stat.S_ISREG(st.st_mode) or st.st_nlink not in (1,2):
                    _deny("K09_FORENSIC_NATIVE_METADATA_DENIED")
                members[entry.name]=(
                    st.st_dev,st.st_ino,st.st_mode,st.st_uid,st.st_gid,
                    st.st_nlink,st.st_size,st.st_mtime_ns,st.st_ctime_ns,
                )
            return members
        except CrashRecoveryRefusal:
            raise
        except OSError:
            _deny("K09_FORENSIC_DIRECTORY_DENIED")

    original_index=identify()
    if (len(original_index)!=plan["candidate_count"]
            or sum(bool(STAGE.fullmatch(n)) for n in original_index)
               !=plan["stage_count"]
            or sum(bool(SNAPSHOT.fullmatch(n)) for n in original_index)
               !=plan["future_snapshot_count"]):
        _deny("K09_FORENSIC_DIRECTORY_CHANGED")

    names=sorted(original_index)
    counts={
        "future_snapshot_ledger_authenticated_count":0,
        "future_snapshot_ledger_unverifiable_count":0,
        "future_snapshot_account_changed_count":0,
        "future_snapshot_reservation_set_changed_count":0,
        "future_snapshot_irreversible_delta_count":0,
        "stage_content_authenticated_count":0,
        "stage_content_unverifiable_count":0,
        "stage_account_changed_count":0,
        "stage_reservation_set_changed_count":0,
        "stage_irreversible_delta_count":0,
    }
    total_bytes=0
    for name in names:
        is_stage=bool(STAGE.fullmatch(name))
        prefix="stage" if is_stage else "future_snapshot"
        entry=vault.directory/name
        before=original_index[name]
        # Reject changes BEFORE attempting native read, including a newly
        # substituted symlink, a re-linked inode or an ACL-modified source.
        current=identify()
        if current.get(name)!=before or set(current)!=set(original_index):
            _deny("K09_FORENSIC_CANDIDATE_CHANGED")
        total_bytes+=before[6]
        if total_bytes>64*1024*1024:
            _deny("K09_FORENSIC_BYTES_LIMIT_DENIED")
        try:
            encrypted=vault._storage.read_crash_residue(vault.directory,name)
            if type(encrypted) is not bytes or len(encrypted)!=before[6]:
                raise ValueError
            raw=unseal(encrypted,password,b"recovery")
            if not 2<=len(raw)<=32*1024*1024:
                raise ValueError
            candidate=json.loads(raw,object_pairs_hook=_unique_json_pairs)
            profile=custody.envelope_profile()
            generation=candidate.get("generation")
            if (type(candidate) is not dict
                    or set(candidate)!=set(profile)|{
                        "disposable_regtest","network","wallet_id",
                        "generation","keys","checkpoint"}
                    or any(type(candidate.get(k)) is not type(v)
                           or candidate[k]!=v for k,v in profile.items())
                    or candidate.get("disposable_regtest") is not True
                    or candidate.get("network")!=REGTEST_GENESIS
                    or candidate.get("wallet_id")!=vault.anchor.wallet_id
                    or type(generation) is not int
                    or not record[0]<generation<10**9
                    or (not is_stage and generation!=int(SNAPSHOT.fullmatch(name)[1]))):
                raise ValueError
            projection=project_owner_ledger(candidate,password)
            observed_outpoints.update(projection.reservations)
            relation=compare_candidate_ledger(anchored,projection)
            counts[("stage_content_authenticated_count" if is_stage else
                    "future_snapshot_ledger_authenticated_count")]+=1
            if not relation["same_account_identity"]:
                counts[prefix+"_account_changed_count"]+=1
            if relation["reservation_set_differs"]:
                counts[prefix+"_reservation_set_changed_count"]+=1
            if relation["candidate_irreversible_not_in_anchor"]:
                counts[prefix+"_irreversible_delta_count"]+=1
        except CrashRecoveryRefusal:
            raise
        except Exception:
            # Torn, wrong-password, wrong account, changed profile, failed
            # native ACL/handle read are unverified, never cleanup evidence.
            counts[("stage_content_unverifiable_count" if is_stage else
                    "future_snapshot_ledger_unverifiable_count")]+=1
        if identify()!=original_index:
            _deny("K09_FORENSIC_CANDIDATE_CHANGED")

    if (_candidate_inventory(vault.directory,record[0])!=plan
            or identify()!=original_index):
        _deny("K09_FORENSIC_DIRECTORY_CHANGED")
    core_evidence={}
    if core_read_rpc is not None:
        from .crash_chain_evidence import observe_recent_core_spends
        core_evidence=observe_recent_core_spends(
            core_read_rpc,frozenset(observed_outpoints),authorized=True)
    return {
        "forensic_status":"K09_SEALED_WSP_LEDGER_PREVIEW_ONLY",
        **core_evidence,
        **counts,
        "core_reservation_or_reorg_reconciled":False,
        "safe_to_discard_proven":False,
        "operator_discard_available":False,
        "wallet_unlocked":False,
        "signer_allowed":False,
        "broadcast_allowed":False,
    }



def inspect_owner_crash_residue(vault, password, *, authorized=False,
                               audit_reservations=False, core_read_rpc=None,
                               authorized_core_observation=False):
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
    if type(audit_reservations) is not bool:
        _deny("K09_FORENSIC_SCOPE_DENIED")
    # Chain observation is a separate explicit operator choice and cannot
    # silently accompany an ordinary wallet password/preview action.
    if type(authorized_core_observation) is not bool:
        _deny("K09_CORE_OBSERVATION_SCOPE_DENIED")
    if (core_read_rpc is None and authorized_core_observation
            or core_read_rpc is not None
            and (not audit_reservations or not authorized_core_observation)):
        _deny("K09_CORE_SEPARATE_CONSENT_REQUIRED")
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
            data=json.loads(raw,object_pairs_hook=_unique_json_pairs)
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
            forensic=(_forensic_candidate_ledger(
                vault,password,record,data,plan,
                core_read_rpc=core_read_rpc)
                if audit_reservations else {})
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
                **forensic,
                "wallet_unlocked":False,
                "signer_allowed":False,"broadcast_allowed":False,
                "automatic_cleanup_allowed":False,
            }
    except CrashRecoveryRefusal:
        raise
    except Exception:
        _deny("K09_OWNER_CRASH_PREVIEW_DENIED")
