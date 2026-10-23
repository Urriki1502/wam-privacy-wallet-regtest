"""K-09: owner-consented adoption of ONE completely published N+1 checkpoint.

This is intentionally narrower than general crash-residue repair. Incomplete
.stage files, linked stages, multi-orphan sets, divergent identities, unlocked
runtimes and competing owners stay blocked. Never discard an encrypted
checkpoint, reset an anchor, create a wallet, or replay a transaction.

Only a managed, authenticated REGTEST caller can enter the mutating path.
This is NOT mainnet migration or final Q19/K-09 acceptance.
"""
from __future__ import annotations

from hashlib import sha256
import hmac
import json
from pathlib import Path

from .crash_ledger import (
    project_owner_ledger, require_irreversible_continuity,
)
from .crash_recovery import (
    _candidate_inventory, _unique_json_pairs,
)
from .vault import CheckpointVault, VaultError


class K09AdoptionRefusal(ValueError):
    """Fixed, redacted error code, never user-controlled data."""


def _deny(reason):
    raise K09AdoptionRefusal(reason)


def _authenticated_payload(ciphertext, password, wallet_id, generation):
    """Authenticate the EXACT self-describing V1 envelope and nested WSP state.

    This intentionally duplicates the strict keys in vault._load_payload:
    the latter cannot run while an N+1 orphan is present. A validly *resealed*
    payload missing self-identifying fields must be rejected.
    """
    from . import custody
    from wam_sp.keystore import unseal
    from wam_sp.watcher import GENESIS
    if (type(ciphertext) is not bytes
            or not 52 <= len(ciphertext) <= 32 * 1024 * 1024 + 52
            or type(generation) is not int
            or not 1 <= generation < 10**9):
        _deny("K09_ADOPTION_ENVELOPE_DENIED")
    try:
        raw = unseal(ciphertext, password, b"recovery")
        if not 2 <= len(raw) <= 32 * 1024 * 1024:
            raise ValueError
        payload = json.loads(raw, object_pairs_hook=_unique_json_pairs)
        profile = custody.envelope_profile()
        if (type(payload) is not dict
                or set(payload) != set(profile) | {
                    "disposable_regtest", "network", "wallet_id",
                    "generation", "keys", "checkpoint"}
                or any(type(payload.get(key)) is not type(value)
                       or payload[key] != value
                       for key, value in profile.items())
                or payload.get("disposable_regtest") is not True
                or payload.get("network") != GENESIS
                or payload.get("wallet_id") != wallet_id
                or type(payload.get("generation")) is not int
                or payload["generation"] != generation):
            raise ValueError
        ledger = project_owner_ledger(payload, password)
        return ledger
    except Exception:
        _deny("K09_ADOPTION_PAYLOAD_IDENTITY_DENIED")


def _adopt_published_next(vault, password, *, authorized=False,
                          confirm_anchor_advance=False, locked_guard=None):
    """Private primitive under original native lease; no GUI/signer access.

    The guard is produced by the managed supervisor entrypoint, not by GUI
    recovery-result flags. Refuse *all* stages, even authentic ones, until a
    separately qualified stage publication/cleanup protocol exists.
    """
    from . import custody
    from wam_sp.file_lock import exclusive_file_lock

    if (authorized is not True or confirm_anchor_advance is not True
            or type(vault) is not CheckpointVault
            or type(password) is not bytes
            or not 12 <= len(password) <= 1024
            or not callable(locked_guard)):
        _deny("K09_ADOPTION_OPERATOR_CONSENT_DENIED")

    try:
        with vault.anchor.lease(), exclusive_file_lock(vault.directory / ".vault.lock"):
            vault._storage.validate_directory(vault.directory)
            if locked_guard() is not True:
                _deny("K09_ADOPTION_MANAGED_STATE_CHANGED")
            record = vault.anchor.read()
            if (type(record) is not tuple or len(record) != 2
                    or type(record[0]) is not int
                    or not 1 <= record[0] < 10**9 - 1
                    or type(record[1]) is not str
                    or len(record[1]) != 64
                    or record != vault._expected):
                _deny("K09_ADOPTION_ANCHOR_DENIED")
            current = vault._storage.read(vault.directory, vault._filename(record[0]))
            if not hmac.compare_digest(sha256(current).hexdigest(), record[1]):
                _deny("K09_ADOPTION_ANCHORED_DIGEST_DENIED")
            old = _authenticated_payload(current, password, vault.anchor.wallet_id,
                                         record[0])
            plan = _candidate_inventory(vault.directory, record[0])
            if (plan["stage_count"] != 0 or plan["future_snapshot_count"] != 1
                    or plan["candidate_count"] != 1
                    or plan["multiple_future_generations"]):
                _deny("K09_ADOPTION_AMBIGUOUS_RESIDUE_DENIED")

            next_generation = record[0] + 1
            name = vault._filename(next_generation)
            # Ordinary native custody read demands a complete published file
            # and normal link-count/DACL/owner guarantees, unlike forensic
            # read_crash_residue which tolerates POSIX hardlink crash pairs.
            candidate = vault._storage.read(vault.directory, name)
            future = _authenticated_payload(candidate, password,
                                            vault.anchor.wallet_id, next_generation)
            require_irreversible_continuity(old, future)
            target = (next_generation, sha256(candidate).hexdigest())

            # Re-evaluate entire residue set, original anchor and file bytes
            # immediately before the monotonic native compare-and-swap.
            if (_candidate_inventory(vault.directory, record[0]) != plan
                    or vault.anchor.read() != record
                    or vault._expected != record
                    or locked_guard() is not True
                    or vault._storage.read(vault.directory, name) != candidate):
                _deny("K09_ADOPTION_EVIDENCE_CHANGED")

            vault.anchor._advance_unlocked(record, target)
            if vault.anchor.read() != target:
                _deny("K09_ADOPTION_ANCHOR_NOT_CONFIRMED")
            vault._expected = target
            # Now the new envelope must also pass the *ordinary* vault reader.
            # No implicit unlock: this only verifies the post-adoption state.
            vault._load_payload(password, target)
            if locked_guard() is not True or vault.anchor.read() != target:
                _deny("K09_ADOPTION_POSTCONDITION_DENIED")
            return {
                "status": "K09_OWNER_AUTHENTICATED_NEXT_SNAPSHOT_ADOPTED",
                "network": "regtest",
                "generation": next_generation,
                "wallet_unlocked": False,
                "signer_allowed": False,
                "broadcast_allowed": False,
                "reservation_release_allowed": False,
                "automatic_cleanup_allowed": False,
                "mainnet_allowed": False,
            }
    except K09AdoptionRefusal:
        raise
    except Exception:
        _deny("K09_ADOPTION_UNVERIFIED")


def adopt_managed_next_published(root, core_dir, wsp_source, password, *,
                                 authorized=False, confirm_anchor_advance=False,
                                 keychain=None):
    """Strict managed-Core entrypoint for owner-approved N+1 adoption.

    Requires unchanged authenticated supervisor status and original signed
    Core/WSP profile; an existing plaintext runtime or SQLite sidecar is a
    separate Q05 recovery problem. Leaves the wallet LOCKED afterward.
    """
    if authorized is not True or confirm_anchor_advance is not True:
        _deny("K09_ADOPTION_OPERATOR_CONSENT_DENIED")
    if (type(root) is not type(Path()) or not root.is_absolute()
            or type(core_dir) is not type(Path()) or not core_dir.is_absolute()
            or type(wsp_source) is not type(Path()) or not wsp_source.is_absolute()
            or type(password) is not bytes or not 12 <= len(password) <= 1024):
        _deny("K09_ADOPTION_INPUT_DENIED")
    try:
        from . import custody
        from .core import verified_core_paths
        from .core_supervisor import _profile_read
        from .managed_wallet_reopen import read, make
        from .supervisor_client import control
        from .supervisor_store import _root
        from .wsp_live import _pinned_source, REGTEST_GENESIS

        _root(root)
        before = control(root, "status", timeout=3)
        if (type(before) is not dict or before.get("state") != "ready"
                or before.get("core_process_owned") is not True
                or type(before.get("height")) is not int):
            _deny("K09_ADOPTION_MANAGED_CORE_DENIED")
        profile = _profile_read(root)
        _, _, receipt = verified_core_paths(core_dir)
        if (profile.get("network") != "regtest"
                or profile.get("genesis") != REGTEST_GENESIS
                or profile.get("core_sha256") != receipt["wamd_sha256"]
                or profile.get("cli_sha256") != receipt["wam_cli_sha256"]
                or receipt.get("platform") != custody.platform_name()):
            _deny("K09_ADOPTION_CORE_IDENTITY_DENIED")
        _pinned_source(wsp_source)
        datadir = root / "chain"
        folder = datadir / "wallet-vault"
        store = custody.storage()
        store.validate_directory(datadir)
        store.validate_directory(folder)
        identity = read(folder, password)
        if identity != make(identity["wallet_id"], receipt):
            _deny("K09_ADOPTION_WALLET_IDENTITY_DENIED")
        anchor = custody.anchor(identity["wallet_id"], keychain)
        vault = CheckpointVault(folder, anchor, wsp_source)

        def locked_guard():
            files = tuple(datadir / ("wallet-runtime.sqlite" + suffix)
                          for suffix in ("", "-wal", "-shm", "-journal"))
            if any(p.exists() or p.is_symlink() for p in files):
                return False
            return (control(root, "status", timeout=3) == before
                    and _profile_read(root) == profile)

        return _adopt_published_next(
            vault, password, authorized=True,
            confirm_anchor_advance=True, locked_guard=locked_guard)
    except K09AdoptionRefusal:
        raise
    except Exception:
        _deny("K09_ADOPTION_MANAGED_PRECONDITION_DENIED")
