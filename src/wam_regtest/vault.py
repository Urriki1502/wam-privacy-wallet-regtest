"""Encrypted REGTEST test-wallet snapshots with a separate macOS Keychain anchor.

Reuse pinned WSP AES-GCM/scrypt, key backup and SQLite checkpoints. Keep only
ciphertext in the vault. SQLite exists in a disposable private runtime while
unlocked. Anchor protects wallet-directory rollback while the Keychain item
remains intact; no claim against same-user malware or rollback of Keychain.
"""
import base64
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from . import encrypted_storage


class VaultError(ValueError):
    pass


class KeychainAnchor:
    """Only a public generation/digest is stored; never a key or passphrase.

    A supplied keychain is used only by acceptance tests. Normal GUI uses the
    user's default macOS Keychain without changing its search list/settings.
    """
    def __init__(self, wallet_id, keychain=None):
        if sys.platform != "darwin" or not re.fullmatch(r"[0-9a-f]{32}", wallet_id):
            raise VaultError("VAULT_MACOS_SCOPE_DENIED")
        self.wallet_id = wallet_id
        self.keychain = keychain
        if keychain is not None and (type(keychain) is not type(Path())
                or not keychain.is_absolute() or keychain.is_symlink()):
            raise VaultError("VAULT_KEYCHAIN_SCOPE_DENIED")

    def _run(self, args):
        try:
            result = subprocess.run(
                ["/usr/bin/security", *args, *([] if self.keychain is None else [str(self.keychain)])],
                capture_output=True, timeout=15, check=False,
                env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
            )
            if len(result.stdout) > 256:
                raise VaultError("VAULT_KEYCHAIN_REPLY_DENIED")
            return result.returncode, result.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            raise VaultError("VAULT_KEYCHAIN_UNAVAILABLE") from None

    def read(self):
        status, raw = self._run(["find-generic-password", "-s", "org.wamcoin.regtest.checkpoint",
                                 "-a", self.wallet_id, "-w"])
        if status == 44:  # errSecItemNotFound; other errors are never absence.
            return None
        if status or not re.fullmatch(rb"[1-9][0-9]{0,8}:[0-9a-f]{64}", raw):
            raise VaultError("VAULT_KEYCHAIN_READ_DENIED")
        serial, digest = raw.decode("ascii").split(":")
        return int(serial), digest

    def advance(self, previous, current):
        if self.read() != previous:
            raise VaultError("VAULT_ANCHOR_CHANGED")
        serial, digest = current
        if (type(serial) is not int or not 1 <= serial < 10**9
                or serial != (1 if previous is None else previous[0] + 1)
                or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise VaultError("VAULT_ANCHOR_SEQUENCE_DENIED")
        status, _ = self._run(["add-generic-password", "-U", "-s",
                               "org.wamcoin.regtest.checkpoint", "-a", self.wallet_id,
                               "-w", f"{serial}:{digest}"])
        if status or self.read() != current:
            raise VaultError("VAULT_KEYCHAIN_WRITE_DENIED")


class CheckpointVault:
    def __init__(self, directory, anchor, source):
        from .wsp_live import _pinned_source
        _pinned_source(source)
        self.directory, self.anchor = directory, anchor
        # Validate custody before reading an anchor or invoking cryptography.
        fd = encrypted_storage.open_macos_private_directory(directory)
        os.close(fd)

    @staticmethod
    def _filename(serial):
        return f"snapshot-{serial:09d}.enc"

    def save(self, ring, scanner, password):
        from wam_sp.file_lock import exclusive_file_lock
        from wam_sp.keystore import seal
        from wam_sp.watcher import GENESIS
        scanner.assert_current()
        if ring.accounts() != scanner.accounts:
            raise VaultError("VAULT_ACCOUNT_MISMATCH")
        with exclusive_file_lock(self.directory / ".vault.lock"):
            previous = self.anchor.read()
            if previous is not None:
                self._load_payload(password, previous)
            serial = 1 if previous is None else previous[0] + 1
            payload = {
                "version": 1, "disposable_regtest": True, "network": GENESIS,
                "wallet_id": self.anchor.wallet_id, "generation": serial,
                "keys": base64.b64encode(ring.backup(password)).decode("ascii"),
                "checkpoint": base64.b64encode(scanner.checkpoint(password)).decode("ascii"),
            }
            raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            ciphertext = seal(raw, password, b"recovery")
            encrypted_storage.publish(self.directory, self._filename(serial), ciphertext)
            current = serial, sha256(ciphertext).hexdigest()
            # A crash before/while anchoring leaves an orphan, never a silently
            # accepted old generation. Ambiguous writes fail closed.
            self.anchor.advance(previous, current)
            return current

    def _load_payload(self, password, record):
        from wam_sp.keystore import unseal
        from wam_sp.watcher import GENESIS
        ciphertext = encrypted_storage.read(self.directory, self._filename(record[0]))
        if sha256(ciphertext).hexdigest() != record[1]:
            raise VaultError("VAULT_ROLLBACK_OR_TAMPER_DENIED")
        try:
            payload = json.loads(unseal(ciphertext, password, b"recovery"))
            if (set(payload) != {"version", "disposable_regtest", "network",
                    "wallet_id", "generation", "keys", "checkpoint"}
                    or payload["version"] != 1 or payload["disposable_regtest"] is not True
                    or payload["network"] != GENESIS
                    or payload["wallet_id"] != self.anchor.wallet_id
                    or type(payload["generation"]) is not int
                    or payload["generation"] != record[0]):
                raise ValueError
            return payload
        except (ValueError, TypeError, KeyError):
            raise VaultError("VAULT_AUTHENTICATION_DENIED") from None

    def restore(self, runtime_path, password):
        """Return NOT-current scanner. Caller must sync to real attested Core.

        No balance or signing may rely solely on restored checkpoint state.
        """
        from wam_sp.keystore import Keyring
        from wam_sp.scanner import Scanner
        from wam_sp.file_lock import exclusive_file_lock
        if runtime_path.exists() or runtime_path.is_symlink():
            raise VaultError("VAULT_FRESH_RUNTIME_REQUIRED")
        ring = scanner = None
        try:
            with exclusive_file_lock(self.directory / ".vault.lock"):
                record = self.anchor.read()
                if record is None:
                    raise VaultError("VAULT_ANCHOR_MISSING_DENIED")
                payload = self._load_payload(password, record)
                ring = Keyring.restore(base64.b64decode(payload["keys"], validate=True), password)
                scanner = Scanner(runtime_path, ring.accounts())
                scanner.restore(base64.b64decode(payload["checkpoint"], validate=True), password)
                if scanner.ready or self.anchor.read() != record:
                    raise VaultError("VAULT_RESTORE_STATE_DENIED")
                return ring, scanner
        except Exception:
            if scanner is not None:
                scanner.close()
            if ring is not None:
                ring.close()
            raise VaultError("VAULT_RESTORE_DENIED") from None

    def backup(self, destination, name):
        from wam_sp.file_lock import exclusive_file_lock
        with exclusive_file_lock(self.directory / ".vault.lock"):
            record = self.anchor.read()
            if record is None:
                raise VaultError("VAULT_ANCHOR_MISSING_DENIED")
            ciphertext = encrypted_storage.read(self.directory, self._filename(record[0]))
            if sha256(ciphertext).hexdigest() != record[1]:
                raise VaultError("VAULT_ROLLBACK_OR_TAMPER_DENIED")
            encrypted_storage.publish(destination, name, ciphertext)
            if self.anchor.read() != record:
                raise VaultError("VAULT_ANCHOR_CHANGED")
            return record
