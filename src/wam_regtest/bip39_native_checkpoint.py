"""Q06 Stage B2b: one-shot, native-anchored scanner checkpoint publication.

This is NOT a spend-capable managed wallet, a multi-generation checkpoint
journal, a crash recovery algorithm, or an owned-Core E2E qualification.
No Q05 backup format changes, mainnet, hidden replay or source bypass.
"""
import base64
from hashlib import sha256
import json
from pathlib import Path

from . import custody
from .bip39_seed_vault import (
    Bip39SeedCustodyError, _exact_namespace, _folder, _owner_binding,
    _owned_password, _record, open_owned_seed_container,
)
from .bip39_scanner_checkpoint import encode_candidate
from .wsp_live import REGTEST_GENESIS, _pinned_source

SCHEMA = "wam-q06-bip39-12-native-scanner-checkpoint/v1"
FILE = "snapshot-000000001.enc"
MAX_CHECKPOINT_GENERATIONS = 4096

def _scanner_anchor_record(value):
    if (type(value) not in (tuple, list) or len(value) != 2
            or type(value[0]) is not int or not 1 <= value[0] <= MAX_CHECKPOINT_GENERATIONS
            or type(value[1]) is not str or len(value[1]) != 64
            or any(c not in "0123456789abcdef" for c in value[1])):
        raise SeededNativeCheckpointError("Q06_SCANNER_ANCHOR_DENIED")
    return value

def _checkpoint_filename(generation):
    _scanner_anchor_record((generation, "0" * 64))
    return f"snapshot-{generation:09d}.enc"

def _checkpoint_names(generation):
    _checkpoint_filename(generation)
    return {_checkpoint_filename(i) for i in range(1, generation + 1)}



class SeededNativeCheckpointError(ValueError):
    """Fixed refusal vocabulary: never expose paths, seeds or RPC details."""


def _directory(owner, seed_folder):
    if (type(seed_folder) is not type(Path()) or not seed_folder.is_absolute()
            or seed_folder.parent != owner.directory):
        raise SeededNativeCheckpointError("Q06_NATIVE_CHECKPOINT_FOREIGN_OWNER")
    seed_id = _folder(seed_folder)
    return seed_id, owner.directory / ("bip39-12-scan-" + seed_id)


def _native(folder, seed_id, source, keychain=None, *, anchor_override=None):
    """Use actual Q05 private-file and native-anchor enforcement, not shims."""
    _pinned_source(source)
    storage = custody.storage()
    storage.validate_directory(folder.parent)
    storage.validate_directory(folder)
    anchor_id = sha256(b"wam-q06-scan-anchor/v1" + bytes.fromhex(seed_id)).hexdigest()[:32]
    anchor = custody.anchor(anchor_id, keychain)
    if anchor_override is not None:
        # Re-use precisely the already native-qualified anchor held by the
        # owner thread during signing. A second anchor object on the same
        # wallet is not re-entrant (macOS flock / Windows mutex / Linux witness).
        if (type(anchor_override) is not type(anchor)
                or anchor_override.wallet_id != anchor.wallet_id):
            raise SeededNativeCheckpointError("Q06_NATIVE_ANCHOR_IDENTITY_DENIED")
        anchor = anchor_override
    from .vault import CheckpointVault
    CheckpointVault(folder, anchor, source)  # native type/Keychain/Witness gate
    return storage, anchor


def _owned_tip(owner):
    from .managed_wallet_checkpoint import _owned
    from .wallet_session import WalletCoreCli
    _owned(owner)
    rpc = WalletCoreCli(owner.cli, owner.directory)
    try:
        rpc.attest()
        height, tip = rpc.call("getblockcount"), rpc.call("getbestblockhash")
        if (type(height) is not int or not 0 <= height <= 1_000_000
                or type(tip) is not str or len(tip) != 64
                or any(c not in "0123456789abcdef" for c in tip)):
            raise SeededNativeCheckpointError("Q06_NATIVE_CHECKPOINT_CORE_TIP_DENIED")
        _owned(owner)
        return height, tip
    finally:
        if getattr(rpc, "_transport", None) is not None:
            rpc._transport.close()


def publish_owned_candidate(owner, seed_folder, scanner, source, password, *,
                            authorized=False, keychain=None):
    """One-shot native CAS, after original-Core attestation and durable tip.

    A later save must be implemented as a separately reviewed multi-generation
    state machine. Existing snapshot or failed publication is NEVER repaired.
    """
    decoded = _owned_password(owner, source, password, authorized)
    seed_id, directory = _directory(owner, seed_folder)
    if directory.exists() or directory.is_symlink():
        raise SeededNativeCheckpointError("Q06_NATIVE_CHECKPOINT_EXISTS_OR_UNCERTAIN")
    try:
        with open_owned_seed_container(
                owner, seed_folder, source, password,
                authorized=authorized, keychain=keychain) as keys:
            binding = _owner_binding(owner)
            height, tip = _owned_tip(owner)
            if scanner.store.tip() != (height, tip):
                raise SeededNativeCheckpointError("Q06_NATIVE_CHECKPOINT_TIP_CHANGED")
            candidate = encode_candidate(
                keys, scanner, decoded, owner_binding=binding,
                trusted_tip=(height, tip),
            )
            # Q05 ensures owned-Core chain state is force-flushed before any
            # wallet checkpoint is admitted into native monotonic custody.
            from .managed_wallet_checkpoint import durable_core_checkpoint
            durable_core_checkpoint(owner, height, tip)
            if _owned_tip(owner) != (height, tip):
                raise SeededNativeCheckpointError("Q06_NATIVE_CHECKPOINT_TIP_CHANGED")
            storage = custody.storage()
            storage.validate_directory(owner.directory)
            if directory.exists() or directory.is_symlink():
                raise SeededNativeCheckpointError("Q06_NATIVE_CHECKPOINT_EXISTS_OR_UNCERTAIN")
            custody.create_directory(directory)
            storage, anchor = _native(directory, seed_id, source, keychain)
            with anchor.lease():
                if anchor.read() is not None:
                    raise SeededNativeCheckpointError("Q06_NATIVE_CHECKPOINT_ANCHOR_EXISTS")
                _exact_namespace(directory, set())
                if _owned_tip(owner) != (height, tip):
                    raise SeededNativeCheckpointError("Q06_NATIVE_CHECKPOINT_TIP_CHANGED")
                from wam_sp.keystore import seal
                payload = {
                    "schema": SCHEMA, "generation": 1,
                    "seed_id": seed_id, "anchor_id": anchor.wallet_id,
                    "owner_binding": binding, "network": "regtest",
                    "genesis": REGTEST_GENESIS, "height": height, "tip": tip,
                    "account_id": keys.public_metadata()["account_id"],
                    "receive_code": keys.public_metadata()["receive_code"],
                    "candidate_sha256": sha256(candidate).hexdigest(),
                    "candidate": base64.b64encode(candidate).decode("ascii"),
                }
                ciphertext = seal(
                    json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii"),
                    password, b"recovery",
                )
                storage.publish(directory, FILE, ciphertext)
                record = (1, sha256(ciphertext).hexdigest())
                anchor._advance_unlocked(None, record)
                if anchor.read() != record:
                    raise SeededNativeCheckpointError("Q06_NATIVE_CHECKPOINT_ANCHOR_UNVERIFIED")
            return {
                "schema": SCHEMA, "status": "ANCHORED_ENCRYPTED_CANDIDATE_ONLY",
                "height": height, "tip": tip, "account_id": keys.public_metadata()["account_id"],
                "signer_allowed": False, "broadcast_allowed": False,
                "mainnet_allowed": False,
            }
    except Exception:
        # If publication happened but CAS did not, the orphan remains for
        # explicit owner review. No cleanup and no automatic reattempt.
        raise SeededNativeCheckpointError("Q06_NATIVE_CHECKPOINT_PUBLISH_DENIED") from None


def read_owned_candidate(owner, seed_folder, source, password, *,
                         authorized=False, keychain=None,
                         allow_descendant=False, anchor_override=None):
    """Validate seed + original Core + checkpoint native CAS; return ciphertext.

    Does not create/overwrite any SQLite file. A later independent routine
    must recover into fresh native-protected SQLite, resync against real Core,
    and check anchored signed/uncertain reservations before enabling spending.
    """
    decoded = _owned_password(owner, source, password, authorized)
    seed_id, directory = _directory(owner, seed_folder)
    try:
        with open_owned_seed_container(
                owner, seed_folder, source, password,
                authorized=authorized, keychain=keychain) as keys:
            binding = _owner_binding(owner)
            storage, anchor = _native(directory, seed_id, source, keychain, anchor_override=anchor_override)
            with anchor.lease():
                record = _scanner_anchor_record(anchor.read())
                _exact_namespace(directory, _checkpoint_names(record[0]))
                ciphertext = storage.read(directory, _checkpoint_filename(record[0]))
                if sha256(ciphertext).hexdigest() != record[1]:
                    raise SeededNativeCheckpointError("Q06_NATIVE_CHECKPOINT_DIGEST_DENIED")
                from wam_sp.keystore import unseal
                data = json.loads(unseal(ciphertext, password, b"recovery"))
                required = {
                    "schema", "generation", "seed_id", "anchor_id", "owner_binding",
                    "network", "genesis", "height", "tip", "account_id",
                    "receive_code", "candidate_sha256", "candidate",
                }
                public = keys.public_metadata()
                if (type(data) is not dict or set(data) != required
                        or data["schema"] != SCHEMA
                        or type(data["generation"]) is not int or data["generation"] != record[0]
                        or data["seed_id"] != seed_id or data["anchor_id"] != anchor.wallet_id
                        or data["owner_binding"] != binding
                        or data["network"] != "regtest" or data["genesis"] != REGTEST_GENESIS
                        or data["account_id"] != public["account_id"]
                        or data["receive_code"] != public["receive_code"]):
                    raise SeededNativeCheckpointError("Q06_NATIVE_CHECKPOINT_PROFILE_DENIED")
                candidate = base64.b64decode(data["candidate"], validate=True)
                if sha256(candidate).hexdigest() != data["candidate_sha256"]:
                    raise SeededNativeCheckpointError("Q06_NATIVE_CHECKPOINT_CANDIDATE_DENIED")
                anchored_tip = (data["height"], data["tip"])
                current_tip = _owned_tip(owner)
                if allow_descendant is True:
                    _require_confirmed_descendant(owner, anchored_tip, current_tip)
                elif allow_descendant is False:
                    if current_tip != anchored_tip:
                        raise SeededNativeCheckpointError("Q06_NATIVE_CHECKPOINT_TIP_CHANGED")
                else:
                    raise SeededNativeCheckpointError("Q06_SCANNER_MODE_DENIED")
                if anchor.read() != record:
                    raise SeededNativeCheckpointError("Q06_NATIVE_CHECKPOINT_ANCHOR_CHANGED")
                return candidate, {
                    "schema": SCHEMA, "status": "ENCRYPTED_CANDIDATE_NEEDS_FRESH_SQLITE_RESTORE",
                    "height": data["height"], "tip": data["tip"],
                    "generation": record[0], "account_id": public["account_id"],
                    "signer_allowed": False, "broadcast_allowed": False,
                    "mainnet_allowed": False,
                }
    except Exception:
        raise SeededNativeCheckpointError("Q06_NATIVE_CHECKPOINT_READ_DENIED") from None


def _require_confirmed_descendant(owner, anchored_tip, live_tip):
    """No reorg crossing the anchored checkpoint tip; refuse all ambiguity."""
    old_height, old_hash = anchored_tip
    now_height, now_hash = live_tip
    if (type(old_height) is not int or type(now_height) is not int
            or not 0 <= old_height <= now_height <= 1_000_000
            or type(old_hash) is not str or type(now_hash) is not str
            or len(old_hash) != 64 or len(now_hash) != 64):
        raise SeededNativeCheckpointError("Q06_SCANNER_ANCESTRY_INVALID")
    if anchored_tip == live_tip:
        return
    if old_height == now_height:
        raise SeededNativeCheckpointError("Q06_SCANNER_REORG_DENIED")
    from .managed_wallet_checkpoint import _owned
    _owned(owner)
    if owner.read.call("getblockhash", [old_height]) != old_hash:
        raise SeededNativeCheckpointError("Q06_SCANNER_REORG_DENIED")
    _owned(owner)


def advance_owned_candidate(owner, seed_folder, scanner, source, password, *,
                            authorized=False, keychain=None, anchor_override=None):
    """Publish N+1 at the exact original Core tip; never activate a signer."""
    import os
    import secrets
    import stat
    import sys
    from .bip39_scanner_checkpoint import (
        decode_candidate, require_irreversible_preserved)
    from .managed_wallet_session import RuntimeGuard
    from .managed_wallet_checkpoint import durable_core_checkpoint
    from wam_sp.scanner import Scanner
    from wam_sp.keystore import seal

    clear = _owned_password(owner, source, password, authorized)
    seed_id, directory = _directory(owner, seed_folder)
    old_cipher, receipt = read_owned_candidate(
        owner, seed_folder, source, password,
        authorized=authorized, keychain=keychain, allow_descendant=True,
        anchor_override=anchor_override)
    anchored_tip = (receipt["height"], receipt["tip"])
    tip = _owned_tip(owner)
    _require_confirmed_descendant(owner, anchored_tip, tip)
    if scanner.store.tip() != tip:
        raise SeededNativeCheckpointError("Q06_SCANNER_TIP_CHANGED")
    scanner.assert_current()
    # Match Windows native create_managed_runtime allowlist; never broaden ACL rules.
    scratch = owner.directory / ("wallet-runtime-recovery-" + secrets.token_hex(8) + ".sqlite")
    if any(scratch.with_name(scratch.name + suffix).exists()
           or scratch.with_name(scratch.name + suffix).is_symlink()
           for suffix in ("", "-wal", "-shm", "-journal", ".scan.lock")):
        raise SeededNativeCheckpointError("Q06_SCANNER_RUNTIME_COLLISION")
    old_scanner = guard = None
    phase = "OPEN_NATIVE_SEED"
    try:
        with open_owned_seed_container(
                owner, seed_folder, source, password,
                authorized=authorized, keychain=keychain) as keys:
            if scanner.accounts != keys.accounts():
                raise SeededNativeCheckpointError("Q06_SCANNER_ACCOUNT_MISMATCH")
            if sys.platform == "win32":
                from .windows_private_storage import create_managed_runtime
                create_managed_runtime(scratch)
            phase = "CREATE_PRIOR_SCANNER"
            old_scanner = Scanner(scratch, keys.accounts())
            guard = RuntimeGuard(scratch)
            phase = "DECODE_PRIOR_CANDIDATE"
            decode_candidate(keys, old_scanner, old_cipher, clear,
                             owner_binding=_owner_binding(owner))
            def reservations(s):
                r = s.store.db.execute(
                    "SELECT txid,vout,token,state,created FROM reservations"
                ).fetchall()
                if len(r) != len({(v[0], v[1]) for v in r}):
                    raise SeededNativeCheckpointError("Q06_RESERVATION_DUPLICATE")
                return {(v[0], v[1]): (v[2], v[3], v[4]) for v in r}
            phase = "CHECK_RESERVATIONS"
            require_irreversible_preserved(
                reservations(old_scanner), reservations(scanner))
            old_scanner.close()
            old_scanner = None
            lock = scratch.with_name(scratch.name + ".scan.lock")
            if lock.exists() or lock.is_symlink():
                meta = lock.lstat()
                if (not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1
                        or lock.is_symlink()
                        or (sys.platform != "win32"
                            and (meta.st_uid != os.geteuid()
                                 or stat.S_IMODE(meta.st_mode) != 0o600))):
                    raise SeededNativeCheckpointError("Q06_SCANNER_LOCK_UNCERTAIN")
                lock.unlink()
            phase = "CLEAN_PRIOR_RUNTIME"
            guard.remove_owned()
            guard = None
            phase = "ENCODE_LATEST"
            candidate = encode_candidate(
                keys, scanner, clear, owner_binding=_owner_binding(owner),
                trusted_tip=tip)
            phase = "DURABLE_CORE"
            durable_core_checkpoint(owner, *tip)
            if _owned_tip(owner) != tip:
                raise SeededNativeCheckpointError("Q06_SCANNER_TIP_CHANGED")
            phase = "NATIVE_ANCHOR"
            storage, anchor = _native(directory, seed_id, source, keychain,
                                     anchor_override=anchor_override)
            with anchor.lease():
                original = _scanner_anchor_record(anchor.read())
                if original[0] != receipt["generation"]:
                    raise SeededNativeCheckpointError("Q06_SCANNER_ANCHOR_CHANGED")
                if original[0] == MAX_CHECKPOINT_GENERATIONS:
                    raise SeededNativeCheckpointError("Q06_SCANNER_GENERATION_LIMIT")
                _exact_namespace(directory, _checkpoint_names(original[0]))
                previous_file = storage.read(directory, _checkpoint_filename(original[0]))
                if sha256(previous_file).hexdigest() != original[1]:
                    raise SeededNativeCheckpointError("Q06_SCANNER_PRIOR_CHANGED")
                gen = original[0] + 1
                public = keys.public_metadata()
                payload = {
                    "schema": SCHEMA, "generation": gen,
                    "seed_id": seed_id, "anchor_id": anchor.wallet_id,
                    "owner_binding": _owner_binding(owner),
                    "network": "regtest", "genesis": REGTEST_GENESIS,
                    "height": tip[0], "tip": tip[1],
                    "account_id": public["account_id"],
                    "receive_code": public["receive_code"],
                    "candidate_sha256": sha256(candidate).hexdigest(),
                    "candidate": base64.b64encode(candidate).decode("ascii"),
                }
                cipher = seal(
                    json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii"),
                    password, b"recovery")
                phase = "PUBLISH_NPLUS1"
                storage.publish(directory, _checkpoint_filename(gen), cipher)
                updated = (gen, sha256(cipher).hexdigest())
                phase = "ADVANCE_NATIVE_CAS"
                anchor._advance_unlocked(original, updated)
                if anchor.read() != updated:
                    raise SeededNativeCheckpointError("Q06_SCANNER_ANCHOR_UNVERIFIED")
            return {"status": "ANCHORED_ENCRYPTED_CANDIDATE_ONLY",
                    "generation": gen, "height": tip[0], "tip": tip[1],
                    "signer_allowed": False, "broadcast_allowed": False,
                    "mainnet_allowed": False}
    except Exception:
        # Emit only fixed stage identifiers, never raw errors or secrets.
        if os.environ.get("CI") == "true":
            print("Q06_NPLUS1_DENIED_STAGE=" + phase, flush=True)
        raise SeededNativeCheckpointError("Q06_SCANNER_ADVANCE_DENIED") from None
    finally:
        if old_scanner is not None:
            old_scanner.close()
        if guard is not None:
            guard.close()
