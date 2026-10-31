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


class SeededNativeCheckpointError(ValueError):
    """Fixed refusal vocabulary: never expose paths, seeds or RPC details."""


def _directory(owner, seed_folder):
    if (type(seed_folder) is not type(Path()) or not seed_folder.is_absolute()
            or seed_folder.parent != owner.directory):
        raise SeededNativeCheckpointError("Q06_NATIVE_CHECKPOINT_FOREIGN_OWNER")
    seed_id = _folder(seed_folder)
    return seed_id, owner.directory / ("bip39-12-scan-" + seed_id)


def _native(folder, seed_id, source, keychain=None):
    """Use actual Q05 private-file and native-anchor enforcement, not shims."""
    _pinned_source(source)
    storage = custody.storage()
    storage.validate_directory(folder.parent)
    storage.validate_directory(folder)
    anchor_id = sha256(b"wam-q06-scan-anchor/v1" + bytes.fromhex(seed_id)).hexdigest()[:32]
    anchor = custody.anchor(anchor_id, keychain)
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
                         authorized=False, keychain=None):
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
            storage, anchor = _native(directory, seed_id, source, keychain)
            with anchor.lease():
                record = _record(anchor.read())
                _exact_namespace(directory, {FILE})
                ciphertext = storage.read(directory, FILE)
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
                        or type(data["generation"]) is not int or data["generation"] != 1
                        or data["seed_id"] != seed_id or data["anchor_id"] != anchor.wallet_id
                        or data["owner_binding"] != binding
                        or data["network"] != "regtest" or data["genesis"] != REGTEST_GENESIS
                        or data["account_id"] != public["account_id"]
                        or data["receive_code"] != public["receive_code"]):
                    raise SeededNativeCheckpointError("Q06_NATIVE_CHECKPOINT_PROFILE_DENIED")
                candidate = base64.b64decode(data["candidate"], validate=True)
                if sha256(candidate).hexdigest() != data["candidate_sha256"]:
                    raise SeededNativeCheckpointError("Q06_NATIVE_CHECKPOINT_CANDIDATE_DENIED")
                if _owned_tip(owner) != (data["height"], data["tip"]):
                    raise SeededNativeCheckpointError("Q06_NATIVE_CHECKPOINT_TIP_CHANGED")
                if anchor.read() != record:
                    raise SeededNativeCheckpointError("Q06_NATIVE_CHECKPOINT_ANCHOR_CHANGED")
                return candidate, {
                    "schema": SCHEMA, "status": "ENCRYPTED_CANDIDATE_NEEDS_FRESH_SQLITE_RESTORE",
                    "height": data["height"], "tip": data["tip"],
                    "account_id": public["account_id"],
                    "signer_allowed": False, "broadcast_allowed": False,
                    "mainnet_allowed": False,
                }
    except Exception:
        raise SeededNativeCheckpointError("Q06_NATIVE_CHECKPOINT_READ_DENIED") from None
