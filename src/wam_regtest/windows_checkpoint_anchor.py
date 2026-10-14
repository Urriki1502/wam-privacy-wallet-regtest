"""Windows x64 REGTEST checkpoint anti-rollback anchor (NO wallet activation).

Store only public generation + ciphertext digest in the Windows Credential
Manager under the logged-in account. No seed, spend key, passphrase, scan key
or decrypted backup is ever placed in a credential. A named global Windows
mutex serializes same-wallet mutations across processes/sessions. The anchor
only protects against file-only stale snapshot restoration while a Windows
Credential record remains intact; it is NOT a protection against same-user
malware, profile rollback, or an adversary controlling Credential Manager.
"""
from __future__ import annotations

from contextlib import contextmanager
import re
import sys
import threading

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _BYTE = ctypes.c_ubyte
    class _CredentialW(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD),
            ("Type", wintypes.DWORD),
            ("TargetName", wintypes.LPWSTR),
            ("Comment", wintypes.LPWSTR),
            ("LastWritten", wintypes.FILETIME),
            ("CredentialBlobSize", wintypes.DWORD),
            ("CredentialBlob", ctypes.POINTER(_BYTE)),
            ("Persist", wintypes.DWORD),
            ("AttributeCount", wintypes.DWORD),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", wintypes.LPWSTR),
            ("UserName", wintypes.LPWSTR),
        ]

    _advapi = ctypes.WinDLL("Advapi32", use_last_error=True)
    _cred_read = _advapi.CredReadW
    _cred_read.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                           ctypes.POINTER(ctypes.POINTER(_CredentialW)))
    _cred_read.restype = wintypes.BOOL
    _cred_write = _advapi.CredWriteW
    _cred_write.argtypes = (ctypes.POINTER(_CredentialW), wintypes.DWORD)
    _cred_write.restype = wintypes.BOOL
    _cred_free = _advapi.CredFree
    _cred_free.argtypes = (ctypes.c_void_p,)
    _cred_free.restype = None

    _kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    _mutex = _kernel.CreateMutexW
    _mutex.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
    _mutex.restype = wintypes.HANDLE
    _wait = _kernel.WaitForSingleObject
    _wait.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    _wait.restype = wintypes.DWORD
    _release = _kernel.ReleaseMutex
    _release.argtypes = (wintypes.HANDLE,)
    _release.restype = wintypes.BOOL
    _close = _kernel.CloseHandle
    _close.argtypes = (wintypes.HANDLE,)
    _close.restype = wintypes.BOOL

_CRED_TYPE_GENERIC = 1
_CRED_PERSIST_LOCAL_MACHINE = 2
_NOT_FOUND = 1168
_WAIT_OWNED = 0
_WAIT_ABANDONED = 0x80
_WAIT_TIMEOUT = 0x102
_ANCHOR_PATTERN = re.compile(rb"([1-9][0-9]{0,8}):([0-9a-f]{64})\Z")


class WindowsAnchorError(ValueError):
    """Never include Win32 errors, wallet IDs or external text in UI."""


class WindowsCredentialAnchor:
    """Native persistent Windows checkpoint CAS. Public metadata only.

    Do not connect to a signer or CheckpointVault until Windows private-file
    custody and crash/recovery gates are qualified as separate milestones.
    """
    def __init__(self, wallet_id: str):
        if sys.platform != "win32" or type(wallet_id) is not str or not re.fullmatch(
            r"[0-9a-f]{32}", wallet_id
        ):
            raise WindowsAnchorError("WIN_ANCHOR_NATIVE_SCOPE_DENIED")
        self.wallet_id = wallet_id
        self._target = "org.wamcoin.regtest.windows.checkpoint." + wallet_id
        self._mutex_name = "Global\\WAM-REGTEST-WALLET-" + wallet_id
        self._local = threading.local()

    def read(self) -> tuple[int, str] | None:
        pointer = ctypes.POINTER(_CredentialW)()
        if not _cred_read(self._target, _CRED_TYPE_GENERIC, 0, ctypes.byref(pointer)):
            if ctypes.get_last_error() == _NOT_FOUND:
                return None
            raise WindowsAnchorError("WIN_ANCHOR_CREDENTIAL_READ_DENIED")
        try:
            if not pointer:
                raise WindowsAnchorError("WIN_ANCHOR_CREDENTIAL_READ_DENIED")
            value = pointer.contents
            if (value.Type != _CRED_TYPE_GENERIC
                    or value.Persist != _CRED_PERSIST_LOCAL_MACHINE
                    or value.CredentialBlobSize <= 0
                    or value.CredentialBlobSize > 120
                    or not value.CredentialBlob):
                raise WindowsAnchorError("WIN_ANCHOR_CREDENTIAL_FORMAT_DENIED")
            raw = ctypes.string_at(value.CredentialBlob, value.CredentialBlobSize)
            if not _ANCHOR_PATTERN.fullmatch(raw):
                raise WindowsAnchorError("WIN_ANCHOR_CREDENTIAL_FORMAT_DENIED")
            generation, digest = raw.decode("ascii").split(":")
            return int(generation), digest
        finally:
            _cred_free(pointer)

    @contextmanager
    def lease(self):
        """Mutual exclusion across Windows threads/processes/user sessions."""
        if getattr(self._local, "inside", False):
            yield
            return
        handle = _mutex(None, False, self._mutex_name)
        if not handle:
            raise WindowsAnchorError("WIN_ANCHOR_MUTEX_UNAVAILABLE")
        acquired = False
        try:
            code = _wait(handle, 0)
            if code == _WAIT_OWNED:
                acquired = True
                self._local.inside = True
                try:
                    yield
                finally:
                    self._local.inside = False
            elif code == _WAIT_ABANDONED:
                # Windows reports ownership acquired despite abandonment.
                # Release but DENY: an abandoned wallet writer is ambiguous.
                acquired = True
                raise WindowsAnchorError("WIN_ANCHOR_ABANDONED_WRITER_DENIED")
            elif code == _WAIT_TIMEOUT:
                raise WindowsAnchorError("WIN_ANCHOR_SESSION_BUSY")
            else:
                raise WindowsAnchorError("WIN_ANCHOR_MUTEX_WAIT_DENIED")
        finally:
            if acquired and not _release(handle):
                _close(handle)
                raise WindowsAnchorError("WIN_ANCHOR_MUTEX_RELEASE_DENIED")
            _close(handle)

    def advance(self, previous: tuple[int, str] | None, current: tuple[int, str]) -> None:
        with self.lease():
            self._advance_unlocked(previous, current)

    def _advance_unlocked(self, previous: tuple[int, str] | None,
                          current: tuple[int, str]) -> None:
        if (type(current) is not tuple or len(current) != 2
                or type(current[0]) is not int
                or not 1 <= current[0] < 10**9
                or type(current[1]) is not str
                or not re.fullmatch(r"[0-9a-f]{64}", current[1])
                or (previous is not None
                    and (type(previous) is not tuple or len(previous) != 2
                         or type(previous[0]) is not int
                         or type(previous[1]) is not str))):
            raise WindowsAnchorError("WIN_ANCHOR_GENERATION_DENIED")
        if current[0] != (1 if previous is None else previous[0] + 1):
            raise WindowsAnchorError("WIN_ANCHOR_GENERATION_DENIED")
        if self.read() != previous:
            raise WindowsAnchorError("WIN_ANCHOR_STALE_WRITER_DENIED")
        data = f"{current[0]}:{current[1]}".encode("ascii")
        storage = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
        credential = _CredentialW()
        credential.Type = _CRED_TYPE_GENERIC
        credential.TargetName = self._target
        credential.UserName = "WAM-REGTEST-PUBLIC-CHECKPOINT"
        credential.Persist = _CRED_PERSIST_LOCAL_MACHINE
        credential.CredentialBlobSize = len(data)
        credential.CredentialBlob = ctypes.cast(storage, ctypes.POINTER(_BYTE))
        if not _cred_write(ctypes.byref(credential), 0):
            raise WindowsAnchorError("WIN_ANCHOR_CREDENTIAL_WRITE_DENIED")
        if self.read() != current:
            raise WindowsAnchorError("WIN_ANCHOR_CREDENTIAL_VERIFY_DENIED")
