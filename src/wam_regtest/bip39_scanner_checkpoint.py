"""Q06 Stage B2a — encrypted BIP39 scanner checkpoint *candidate* codec.

This is NOT a native-anchored on-disk checkpoint, trusted Core observation,
operational wallet or recovery authorization. Caller must bind it to the
original owned Core and durable native-anchor CAS in a later step; no GUI,
spending authority, automatic replay or mainnet usage is exposed here.
"""
import base64
from hashlib import sha256
import json
import re

from .bip39_12 import Bip39Regtest12Keys, PROFILE
from .bip39_seed_vault import _password
from .wsp_live import REGTEST_GENESIS

SCHEMA = "wam-q06-bip39-scanner-checkpoint-candidate/v1"
_NAMES = ("blocks", "coins", "cache", "contacts", "reservations", "history",
          "mempool_coins", "mempool_spends", "labels", "intents", "outbox")


class SeededCheckpointError(ValueError):
    """Only fixed public error codes, never private material or path text."""


def _identity(keys, scanner, owner_binding):
    from wam_sp.scanner import Scanner
    if (type(keys) is not Bip39Regtest12Keys or type(scanner) is not Scanner
            or type(owner_binding) is not str
            or re.fullmatch(r"[0-9a-f]{64}", owner_binding) is None):
        raise SeededCheckpointError("Q06_CHECKPOINT_CONTEXT_DENIED")
    if scanner.accounts != keys.accounts():
        raise SeededCheckpointError("Q06_CHECKPOINT_ACCOUNT_MISMATCH")
    return keys.public_metadata()


def _tip(tip):
    if (type(tip) is not tuple or len(tip) != 2 or type(tip[0]) is not int
            or not 0 <= tip[0] <= 1_000_000 or type(tip[1]) is not str
            or re.fullmatch(r"[0-9a-f]{64}", tip[1]) is None):
        raise SeededCheckpointError("Q06_CHECKPOINT_TIP_DENIED")
    return tip


def encode_candidate(keys, scanner, password, *, owner_binding, trusted_tip):
    """Encrypt scanner state in memory; never call file publication or Core RPC.

    A trusted owner MUST compare Core tip and flush Core before later
    publication. That condition is deliberately not claimed by this codec.
    """
    public = _identity(keys, scanner, owner_binding)
    secret = _password(password)
    _tip(trusted_tip)
    try:
        scanner.assert_current()
        if scanner.store.tip() != trusted_tip:
            raise SeededCheckpointError("Q06_CHECKPOINT_TIP_CHANGED")
        encrypted_state = scanner.checkpoint(secret)
        from wam_sp.keystore import seal
        payload = {
            "schema": SCHEMA, "profile": PROFILE, "network": "regtest",
            "genesis": REGTEST_GENESIS, "owner_binding": owner_binding,
            "account_id": public["account_id"], "receive_code": public["receive_code"],
            "height": trusted_tip[0], "tip": trusted_tip[1],
            "checkpoint_sha256": sha256(encrypted_state).hexdigest(),
            "checkpoint": base64.b64encode(encrypted_state).decode("ascii"),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii")
        return seal(raw, secret, b"recovery")
    except SeededCheckpointError:
        raise
    except Exception:
        raise SeededCheckpointError("Q06_CHECKPOINT_EXPORT_DENIED") from None


def decode_candidate(keys, scanner, encrypted, password, *, owner_binding):
    """Restore into EMPTY scanner only; never mark ready before Core resync.

    The returned public receipt explicitly denies signer/broadcast. The
    caller must verify the original Core+native anchor before publication
    and independently resync against a genuine attested REGTEST Core.
    """
    public = _identity(keys, scanner, owner_binding)
    secret = _password(password)
    try:
        if scanner.ready or scanner.verified_tip is not None:
            raise ValueError
        if any(scanner.store.db.execute(
                "SELECT count(*) FROM " + name).fetchone()[0] for name in _NAMES):
            raise ValueError
        from wam_sp.keystore import unseal
        value = json.loads(unseal(encrypted, secret, b"recovery"))
        fields = {"schema", "profile", "network", "genesis", "owner_binding",
                  "account_id", "receive_code", "height", "tip",
                  "checkpoint_sha256", "checkpoint"}
        if (type(value) is not dict or set(value) != fields
                or value["schema"] != SCHEMA or value["profile"] != PROFILE
                or value["network"] != "regtest" or value["genesis"] != REGTEST_GENESIS
                or value["owner_binding"] != owner_binding
                or value["account_id"] != public["account_id"]
                or value["receive_code"] != public["receive_code"]):
            raise ValueError
        claimed_tip = _tip((value["height"], value["tip"]))
        blob = base64.b64decode(value["checkpoint"], validate=True)
        if sha256(blob).hexdigest() != value["checkpoint_sha256"]:
            raise ValueError
        scanner.restore(blob, secret)
        if scanner.ready or scanner.store.tip() != claimed_tip:
            raise ValueError
        return {
            "profile": PROFILE, "chain": "regtest",
            "account_id": public["account_id"], "receive_code": public["receive_code"],
            "claimed_height": claimed_tip[0], "claimed_tip": claimed_tip[1],
            "status": "RESTORED_UNVERIFIED_NEEDS_REAL_CORE_RESYNC",
            "signer_allowed": False, "broadcast_allowed": False,
            "mainnet_allowed": False,
        }
    except Exception:
        raise SeededCheckpointError("Q06_CHECKPOINT_RESTORE_DENIED") from None
