"""Q06 Stage B1 — encrypted, native-anchored BIP39-12 seed container.

A separate REGTEST-only container; never migrate/modify Q05's Keyring,
CheckpointVault or native profile. This stores encrypted BIP39 recovery
material, not SQLite history, a funded wallet or a signed transaction.
The caller must keep its own 12-word human backup. No mainnet.
"""
from hashlib import sha256
import json
from pathlib import Path
import re
import secrets

from . import custody
from .bip39_12 import Bip39Regtest12Keys, PROFILE, normalize_phrase
from .wsp_live import REGTEST_GENESIS, _pinned_source

FORMAT = "wam-q06-bip39-12-native-seed/v1"
FILE = "seed-000000001.enc"
FOLDER = re.compile(r"bip39-12-([0-9a-f]{32})")


class Bip39SeedCustodyError(ValueError):
    """Fixed public refusal vocabulary; no secret or filesystem path output."""


def _password(password):
    if type(password) is not str:
        raise Bip39SeedCustodyError("Q06_SEED_PASSWORD_DENIED")
    try:
        size = len(password.encode("utf-8"))
    except UnicodeError:
        raise Bip39SeedCustodyError("Q06_SEED_PASSWORD_DENIED") from None
    if not 12 <= size <= 1024:
        raise Bip39SeedCustodyError("Q06_SEED_PASSWORD_DENIED")
    return password.encode("utf-8")


def _folder(folder):
    if (type(folder) is not type(Path()) or not folder.is_absolute()
            or ".." in folder.parts or folder.is_symlink()):
        raise Bip39SeedCustodyError("Q06_SEED_FOLDER_DENIED")
    match = FOLDER.fullmatch(folder.name)
    if not match:
        raise Bip39SeedCustodyError("Q06_SEED_FOLDER_DENIED")
    return match.group(1)


def _native(folder, source, keychain=None):
    """Never accept a synthetic anchor/storage through the public API."""
    _pinned_source(source)
    wallet_id = _folder(folder)
    storage = custody.storage()
    storage.validate_directory(folder.parent)
    storage.validate_directory(folder)
    anchor = custody.anchor(wallet_id, keychain)
    # Reuse Q05 native anchor types and exact platform witness requirements.
    from .vault import CheckpointVault
    # Q05 verifies type, native witness and pinned source in this constructor.
    CheckpointVault(folder, anchor, source)
    return wallet_id, storage, anchor


def _record(value):
    if (type(value) is not tuple or len(value) != 2 or value[0] != 1
            or type(value[0]) is not int or type(value[1]) is not str
            or re.fullmatch(r"[0-9a-f]{64}", value[1]) is None):
        raise Bip39SeedCustodyError("Q06_SEED_ANCHOR_REQUIRED")
    return value


def create_seed_container(parent, source, password, phrase, *,
                          authorized_disposable=False, keychain=None):
    """Fresh create-only native container; preserves orphan on a failed CAS.

    Returns (folder, PUBLIC metadata). The mnemonic is never emitted in a
    return value, log, artifact or filename. Existing Q05 vault is untouched.
    """
    if authorized_disposable is not True:
        raise Bip39SeedCustodyError("Q06_SEED_REGTEST_CONSENT_REQUIRED")
    _pinned_source(source)
    secret = _password(password)
    if type(parent) is not type(Path()) or not parent.is_absolute() or ".." in parent.parts:
        raise Bip39SeedCustodyError("Q06_SEED_PARENT_DENIED")
    custody.storage().validate_directory(parent)
    # Stage B1 is a distinct profile. Never place it beside an existing Q05
    # wallet; this release has no migration/dual-profile conflict resolver.
    if any((parent / name).exists() or (parent / name).is_symlink()
           for name in ("wallet-vault", "supervisor.wallet")):
        raise Bip39SeedCustodyError("Q06_SEED_Q05_PROFILE_CONFLICT")
    canonical = normalize_phrase(phrase)
    with Bip39Regtest12Keys(canonical, source=source, authorized_disposable=True) as keys:
        public = keys.public_metadata()
        wallet_id = secrets.token_hex(16)
        folder = parent / ("bip39-12-" + wallet_id)
        # No existing-folder adoption and no cleanup after a failed write.
        if folder.exists() or folder.is_symlink():
            raise Bip39SeedCustodyError("Q06_SEED_FOLDER_EXISTS")
        custody.create_directory(folder)
        try:
            ident, storage, anchor = _native(folder, source, keychain)
            if ident != wallet_id:
                raise Bip39SeedCustodyError("Q06_SEED_OWNER_MISMATCH")
            with anchor.lease():
                if anchor.read() is not None:
                    raise Bip39SeedCustodyError("Q06_SEED_ANCHOR_EXISTS")
                from wam_sp.keystore import seal
                payload = {
                    "format": FORMAT, "wallet_id": ident,
                    "generation": 1, "profile": PROFILE,
                    "chain": "regtest", "genesis": REGTEST_GENESIS,
                    "phrase": canonical, "account_id": public["account_id"],
                    "receive_code": public["receive_code"],
                }
                raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
                ciphertext = seal(raw, secret, b"recovery")
                storage.publish(folder, FILE, ciphertext)
                record = (1, sha256(ciphertext).hexdigest())
                anchor._advance_unlocked(None, record)
                if anchor.read() != record:
                    raise Bip39SeedCustodyError("Q06_SEED_ANCHOR_UNVERIFIED")
            return folder, public
        except Exception:
            # Fail closed; DO NOT delete an orphan or normalize an uncertain
            # generation. Original ciphertext/native anchor remain available.
            raise Bip39SeedCustodyError("Q06_SEED_CREATE_DENIED") from None


def open_seed_container(folder, source, password, *, keychain=None):
    """Reopen only if independent native generation/digest and GCM match.

    Never reset a missing anchor, create a directory, write, recover an orphan
    or use user-supplied mnemonic as authority for an existing anchored wallet.
    Caller owns the returned secret-bearing keys and must close them.
    """
    secret = _password(password)
    try:
        ident, storage, anchor = _native(folder, source, keychain)
        with anchor.lease():
            record = _record(anchor.read())
            ciphertext = storage.read(folder, FILE)
            if sha256(ciphertext).hexdigest() != record[1]:
                raise Bip39SeedCustodyError("Q06_SEED_DIGEST_DENIED")
            from wam_sp.keystore import unseal
            payload = json.loads(unseal(ciphertext, secret, b"recovery"))
            if (type(payload) is not dict or set(payload) != {
                    "format", "wallet_id", "generation", "profile", "chain",
                    "genesis", "phrase", "account_id", "receive_code"}
                    or payload["format"] != FORMAT
                    or payload["wallet_id"] != ident
                    or type(payload["generation"]) is not int or payload["generation"] != 1
                    or payload["profile"] != PROFILE or payload["chain"] != "regtest"
                    or payload["genesis"] != REGTEST_GENESIS
                    or type(payload["account_id"]) is not str
                    or type(payload["receive_code"]) is not str):
                raise Bip39SeedCustodyError("Q06_SEED_PROFILE_DENIED")
            keys = Bip39Regtest12Keys(
                payload["phrase"], source=source, authorized_disposable=True,
            )
            try:
                meta = keys.public_metadata()
                if (meta["account_id"] != payload["account_id"]
                        or meta["receive_code"] != payload["receive_code"]
                        or anchor.read() != record):
                    raise Bip39SeedCustodyError("Q06_SEED_IDENTITY_DENIED")
                return keys
            except Exception:
                keys.close()
                raise
    except Exception:
        raise Bip39SeedCustodyError("Q06_SEED_REOPEN_DENIED") from None
