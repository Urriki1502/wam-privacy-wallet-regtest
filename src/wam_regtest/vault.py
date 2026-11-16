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
import stat
import tempfile
import threading
from contextlib import contextmanager
from . import encrypted_storage, custody


class VaultError(ValueError):
    pass


LEASE_DIRECTORY = ("Library", "Application Support", "WAM Fusion REGTEST", "wallet-leases")
LEGACY_LEASE_DIRECTORY = "wam-regtest-wallet-leases"
_CS_DARWIN_USER_TEMP_DIR = 65537


def stable_lease_root():
    """Per-user private lease root independent of the process environment."""
    import pwd
    home = Path(pwd.getpwuid(os.geteuid()).pw_dir)
    if not home.is_absolute() or ".." in home.parts:
        raise VaultError("VAULT_GLOBAL_LEASE_DENIED")
    return home.joinpath(*LEASE_DIRECTORY)


def _lease_roots():
    if sys.platform != "darwin":
        raise VaultError("VAULT_MACOS_SCOPE_DENIED")
    try:
        stable = stable_lease_root()
        default = Path(os.confstr(_CS_DARWIN_USER_TEMP_DIR)).resolve(strict=True)
        current = Path(tempfile.gettempdir()).resolve(strict=True)
    except (OSError, ValueError, KeyError, TypeError):
        raise VaultError("VAULT_GLOBAL_LEASE_DENIED") from None
    roots = [stable]
    for legacy in (default / LEGACY_LEASE_DIRECTORY, current / LEGACY_LEASE_DIRECTORY):
        if legacy not in roots:
            roots.append(legacy)
    return roots


def _ensure_private_directory(directory):
    # Create missing components owner-only; never chmod/repair an existing one.
    missing = []
    probe = directory
    while not (probe.exists() or probe.is_symlink()):
        missing.append(probe)
        probe = probe.parent
    for component in reversed(missing):
        try:
            component.mkdir(mode=0o700)
        except FileExistsError:
            pass


def _open_lock(root, name):
    """Open root (no-follow, private) and the lock file; bounded transient retry.

    Concurrent first creation in the same root changes the directory mtime
    (the strict validator reports MACOS_PRIVATE_DIRECTORY_CHANGED) and APFS
    can briefly return ENOENT for a racing O_CREAT. Only those two transient
    cases are retried, at most 5 times; metadata violations deny at once.
    Nothing is locked until flock below, so a retry never weakens exclusion.
    """
    import errno
    import time
    from .private_directory import MacosPrivateDirectoryError
    for attempt in range(5):
        if attempt:
            time.sleep(0.02 * attempt)
        try:
            _ensure_private_directory(root)
            dfd = encrypted_storage.open_macos_private_directory(root)
        except MacosPrivateDirectoryError as error:
            if error.args == ("MACOS_PRIVATE_DIRECTORY_CHANGED",):
                continue
            raise VaultError("VAULT_GLOBAL_LEASE_DENIED") from None
        except (OSError, ValueError):
            raise VaultError("VAULT_GLOBAL_LEASE_DENIED") from None
        try:
            return dfd, os.open(name, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC,
                                0o600, dir_fd=dfd)
        except OSError as error:
            os.close(dfd)
            if error.errno == errno.ENOENT:
                continue
            raise VaultError("VAULT_GLOBAL_LEASE_DENIED") from None
    raise VaultError("VAULT_SESSION_BUSY")


@contextmanager
def _exclusive_lock(root, name):
    import fcntl
    dfd, fd = _open_lock(root, name)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_uid != os.geteuid() or info.st_nlink != 1):
            raise VaultError("VAULT_GLOBAL_LEASE_DENIED")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise VaultError("VAULT_SESSION_BUSY") from None
        try:
            # The locked inode must still be the published name (no unlink or
            # replacement raced the open); otherwise two holders could exist.
            named = os.stat(name, dir_fd=dfd, follow_symlinks=False)
            if (named.st_dev, named.st_ino) != (info.st_dev, info.st_ino):
                raise VaultError("VAULT_GLOBAL_LEASE_DENIED")
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        if fd is not None:
            os.close(fd)
        os.close(dfd)


class KeychainAnchor:
    """Only a public generation/digest is stored; never a key or passphrase.

    A supplied keychain is used only by acceptance tests. Normal GUI uses the
    user's default macOS Keychain without changing its search list/settings.
    """
    def __init__(self, wallet_id, keychain=None):
        if sys.platform != "darwin" or type(wallet_id) is not str or not re.fullmatch(r"[0-9a-f]{32}", wallet_id):
            raise VaultError("VAULT_MACOS_SCOPE_DENIED")
        self.wallet_id = wallet_id
        self.keychain = keychain
        self._lease_local = threading.local()
        if keychain is not None and (type(keychain) is not type(Path())
                or not keychain.is_absolute() or keychain.is_symlink()):
            raise VaultError("VAULT_KEYCHAIN_SCOPE_DENIED")

    @contextmanager
    def lease(self):
        # All copies of one wallet share this OS lease even when their vault
        # directories differ. Roots contain empty locks, never secrets.
        #
        # CDX-AUD-001: the authoritative lock lives in a stable per-user
        # private directory derived from the password database (never from
        # TMPDIR/HOME). During the transition the legacy locks used by earlier
        # builds are ALSO held: the Darwin per-user default temp root (what an
        # earlier process launched normally used) and the caller's current
        # temp root. Order is fixed (stable, default-legacy, env-legacy); every
        # acquisition is non-blocking and any busy/invalid lock fails closed.
        # Lock files are never unlinked or recreated.
        from contextlib import ExitStack
        # Only this exact anchor object and thread may nest a held lease.
        # Another object/process for the same wallet must still contend.
        if getattr(self._lease_local,"held_pid",None)==os.getpid():
            yield
            return
        with ExitStack() as stack:
            for root in _lease_roots():
                stack.enter_context(_exclusive_lock(root,self.wallet_id+".lock"))
            self._lease_local.held_pid=os.getpid()
            try:
                yield
            finally:
                self._lease_local.held_pid=None

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
        with self.lease():
            self._advance_unlocked(previous,current)

    def _advance_unlocked(self, previous, current):
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
        self._storage = custody.storage()
        self._storage.validate_directory(directory)
        if sys.platform == "win32":
            from .windows_checkpoint_anchor import WindowsCredentialAnchor
            if type(anchor) is not WindowsCredentialAnchor:
                raise VaultError("VAULT_NATIVE_ANCHOR_REQUIRED")
        elif sys.platform == 'linux':
            from .linux_anchor_witness import LinuxRootWitnessAnchor
            from .linux_runtime import policy
            if type(anchor) is not LinuxRootWitnessAnchor or anchor.endpoint!=policy().witness:
                raise VaultError('VAULT_NATIVE_ROOT_WITNESS_REQUIRED')
        elif type(anchor) is not KeychainAnchor:
            raise VaultError("VAULT_NATIVE_ANCHOR_REQUIRED")
        self._expected = anchor.read()

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
        with self.anchor.lease(), exclusive_file_lock(self.directory / ".vault.lock"):
            previous = self.anchor.read()
            if previous != self._expected:
                raise VaultError("VAULT_STALE_WRITER_DENIED")
            if previous is not None:
                self._load_payload(password, previous)
            serial = 1 if previous is None else previous[0] + 1
            payload = {
                **custody.envelope_profile(), "disposable_regtest": True, "network": GENESIS,
                "wallet_id": self.anchor.wallet_id, "generation": serial,
                "keys": base64.b64encode(ring.backup(password)).decode("ascii"),
                "checkpoint": base64.b64encode(scanner.checkpoint(password)).decode("ascii"),
            }
            raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            ciphertext = seal(raw, password, b"recovery")
            self._storage.publish(self.directory, self._filename(serial), ciphertext)
            current = serial, sha256(ciphertext).hexdigest()
            # A crash before/while anchoring leaves an orphan, never a silently
            # accepted old generation. Ambiguous writes fail closed.
            self.anchor._advance_unlocked(previous, current)
            self._expected = current
            return current

    def _load_payload(self, password, record):
        from wam_sp.keystore import unseal
        from wam_sp.watcher import GENESIS
        ciphertext = self._storage.read(self.directory, self._filename(record[0]))
        if sha256(ciphertext).hexdigest() != record[1]:
            raise VaultError("VAULT_ROLLBACK_OR_TAMPER_DENIED")
        try:
            payload = json.loads(unseal(ciphertext, password, b"recovery"))
            profile = custody.envelope_profile()
            if (type(payload) is not dict or set(payload) != set(profile) | {"disposable_regtest", "network",
                    "wallet_id", "generation", "keys", "checkpoint"}
                    or any(type(payload[k]) is not type(v) or payload[k] != v for k,v in profile.items())
                    or payload["disposable_regtest"] is not True
                    or payload["network"] != GENESIS
                    or payload["wallet_id"] != self.anchor.wallet_id
                    or type(payload["generation"]) is not int
                    or payload["generation"] != record[0]):
                raise ValueError
            return payload
        except (ValueError, TypeError, KeyError):
            raise VaultError("VAULT_AUTHENTICATION_DENIED") from None

    def restore(self, runtime_path, password, *, private_windows_runtime=False):
        """Return NOT-current scanner. Caller must sync to real attested Core.

        No balance or signing may rely solely on restored checkpoint state.
        """
        if (type(private_windows_runtime) is not bool
                or private_windows_runtime and sys.platform!='win32'):
            raise VaultError('VAULT_PRIVATE_WINDOWS_RUNTIME_SCOPE_DENIED')
        from wam_sp.keystore import Keyring
        from wam_sp.scanner import Scanner
        from wam_sp.file_lock import exclusive_file_lock
        runtime_files=tuple(runtime_path.with_name(runtime_path.name+x)
                            for x in ("","-journal","-wal","-shm"))
        if any(p.exists() or p.is_symlink() for p in runtime_files):
            raise VaultError("VAULT_FRESH_RUNTIME_REQUIRED")
        ring = scanner = None
        runtime_created = False
        try:
            self._storage.validate_directory(runtime_path.parent)
            with self.anchor.lease(), exclusive_file_lock(self.directory / ".vault.lock"):
                record = self.anchor.read()
                if record is None:
                    raise VaultError("VAULT_ANCHOR_MISSING_DENIED")
                payload = self._load_payload(password, record)
                ring = Keyring.restore(base64.b64decode(payload["keys"], validate=True), password)
                if private_windows_runtime:
                    from .windows_private_storage import create_managed_runtime
                    # Only after authentication and under the existing lease.
                    # CREATE_NEW failure never authorizes deleting an old file.
                    create_managed_runtime(runtime_path)
                runtime_created = True
                scanner = Scanner(runtime_path, ring.accounts())
                scanner.restore(base64.b64decode(payload["checkpoint"], validate=True), password)
                if scanner.ready or self.anchor.read() != record:
                    raise VaultError("VAULT_RESTORE_STATE_DENIED")
                self._expected = record
                return ring, scanner
        except Exception:
            try:
                if scanner is not None:
                    scanner.close()
            finally:
                if ring is not None:
                    ring.close()
                if runtime_created:
                    # Only our fresh private disposable SQLite path, never a
                    # supplied existing DB. Failed restore must be retryable.
                    for path in reversed(runtime_files):
                        path.unlink(missing_ok=True)
            raise VaultError("VAULT_RESTORE_DENIED") from None

    def backup(self, destination, name):
        from wam_sp.file_lock import exclusive_file_lock
        with self.anchor.lease(), exclusive_file_lock(self.directory / ".vault.lock"):
            record = self.anchor.read()
            if record is None:
                raise VaultError("VAULT_ANCHOR_MISSING_DENIED")
            ciphertext = self._storage.read(self.directory, self._filename(record[0]))
            if sha256(ciphertext).hexdigest() != record[1]:
                raise VaultError("VAULT_ROLLBACK_OR_TAMPER_DENIED")
            self._storage.publish(destination, name, ciphertext)
            if self.anchor.read() != record:
                raise VaultError("VAULT_ANCHOR_CHANGED")
            return record
