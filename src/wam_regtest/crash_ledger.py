"""K-09 authenticated WSP checkpoint *forensics*, never restore authority.

This only reads already-decrypted in-memory contents of a native-owner-sealed
REGTEST checkpoint. It does not open wallets, nodes, sockets or files, and no
signing/broadcast/cleanup decision may be inferred from its output.
"""
from __future__ import annotations

import base64
import json
import re

from wam_sp.keystore import unseal
from wam_sp.state import decode_checkpoint
from wam_sp.watcher import GENESIS


_HASH = re.compile(r"[0-9a-f]{64}\Z")
_STATES = frozenset(("draft", "signed", "uncertain", "broadcast", "manual"))
_IRREVERSIBLE = frozenset(("signed", "uncertain", "broadcast", "manual"))


class LedgerEvidenceError(ValueError):
    """Fixed non-secret error code; never interpolate checkpoint contents."""


class _LedgerProjection:
    __slots__ = ("account_identity", "reservations", "reservation_records", "irreversible")

    def __init__(self, account_identity, reservations, reservation_records, irreversible):
        self.account_identity = account_identity
        self.reservations = reservations
        self.reservation_records = reservation_records
        self.irreversible = irreversible

    def __repr__(self):
        return "<K09LedgerProjection redacted>"


def _decode_envelope(encoded):
    if type(encoded) is not str or not 50 <= len(encoded) <= 32 * 1024 * 1024:
        raise LedgerEvidenceError("K09_NESTED_ENVELOPE_DENIED")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, base64.binascii.Error):
        raise LedgerEvidenceError("K09_NESTED_ENVELOPE_DENIED") from None
    if not 52 <= len(raw) <= 32 * 1024 * 1024 + 52:
        raise LedgerEvidenceError("K09_NESTED_ENVELOPE_DENIED")
    return raw


def project_owner_ledger(payload, password):
    """Return sealed-ledger identity and reservations without exporting secrets.

    Native pinned WSP backs both the keys and scanner checkpoint. Exact
    account identity is independently derived from the restored in-memory
    keyring, not accepted from the checkpoint JSON alone. This is diagnostic
    evidence, *not* a completeness or chain-reconciliation proof.
    """
    if (type(payload) is not dict or type(password) is not bytes
            or not 12 <= len(password) <= 1024):
        raise LedgerEvidenceError("K09_LEDGER_SCOPE_DENIED")
    from .bip39_durable import restore_keyring
    ring = None
    try:
        ring = restore_keyring(_decode_envelope(payload["keys"]), password)
        accounts = [a.identity() for a in ring.accounts()]
        if not 1 <= len(accounts) <= 16:
            raise ValueError
        identity = json.dumps(
            {"version": 2, "network": GENESIS, "accounts": accounts},
            sort_keys=True, separators=(",", ":"),
        )
        checkpoint = unseal(
            _decode_envelope(payload["checkpoint"]), password, b"checkpoint"
        )
        decoded = decode_checkpoint(checkpoint, identity)
        rows = decoded["tables"]["reservations"]
        reservations = set()
        reservation_records = set()
        irreversible = set()
        for row in rows:
            if (type(row[0]) is not str or not _HASH.fullmatch(row[0])
                    or type(row[1]) is not int or not 0 <= row[1] < 2**32
                    or type(row[2]) is not str or not 1 <= len(row[2]) <= 128
                    or type(row[3]) is not str or row[3] not in _STATES
                    or type(row[4]) is not int or not 0 <= row[4] < 2**63):
                raise ValueError
            key = (row[0], row[1])
            if key in reservations:
                raise ValueError
            reservations.add(key)
            # Same outpoint with changed state/token/time is NOT the same
            # reservation. A disappearance of 'signed' may imply lost intent.
            reservation_records.add(tuple(row))
            if row[3] in _IRREVERSIBLE:
                irreversible.add((row[0], row[1], row[3]))
        return _LedgerProjection(
            identity, frozenset(reservations), frozenset(reservation_records),
            frozenset(irreversible)
        )
    except LedgerEvidenceError:
        raise
    except Exception:
        raise LedgerEvidenceError("K09_LEDGER_AUTH_OR_FORMAT_DENIED") from None
    finally:
        if ring is not None:
            ring.close()


def compare_candidate_ledger(anchored, candidate):
    """Return redacted *risk indicators*; never an authorization to discard."""
    if type(anchored) is not _LedgerProjection or type(candidate) is not _LedgerProjection:
        raise LedgerEvidenceError("K09_LEDGER_COMPARISON_DENIED")
    return {
        "same_account_identity": candidate.account_identity == anchored.account_identity,
        "reservation_set_differs": candidate.reservation_records != anchored.reservation_records,
        "candidate_irreversible_not_in_anchor": bool(
            candidate.irreversible - anchored.irreversible
        ),
        "ledger_reconciled_with_core": False,
        "safe_to_discard_proven": False,
    }


def require_irreversible_continuity(anchored, candidate):
    """K-09 adoption gate: a later checkpoint cannot forget irreversible locks.

    This is deliberately stricter than normal scanner history reconciliation.
    An existing signed/uncertain/broadcast/manual reservation retains its
    outpoint, token and creation time. Only forward transitions are allowed.
    This does NOT grant anchor, unlock, signing or broadcast authority.
    """
    if (type(anchored) is not _LedgerProjection
            or type(candidate) is not _LedgerProjection
            or candidate.account_identity != anchored.account_identity):
        raise LedgerEvidenceError("K09_ADOPTION_ACCOUNT_IDENTITY_DENIED")

    future = {(row[0], row[1]): row
              for row in candidate.reservation_records}
    transitions = {
        "signed": frozenset(("signed", "uncertain", "broadcast")),
        "uncertain": frozenset(("uncertain", "broadcast")),
        "broadcast": frozenset(("broadcast",)),
        "manual": frozenset(("manual",)),
    }
    for previous in anchored.reservation_records:
        if previous[3] not in _IRREVERSIBLE:
            continue
        current = future.get((previous[0], previous[1]))
        if (current is None
                or current[2] != previous[2]
                or current[4] != previous[4]
                or current[3] not in transitions[previous[3]]):
            raise LedgerEvidenceError("K09_ADOPTION_IRREVERSIBLE_LOCK_DENIED")
    return True
