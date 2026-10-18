"""T-06 explicit read-only connection to an ALREADY-RUNNING isolated REGTEST Core.

This module NEVER starts, stops, restarts, mines, loads a wallet, signs, or
broadcasts. PID is only an observed OS identity, never adopted as a child or
used for a signal. The external process must use our exact independently
qualified Core pair and a pre-existing, owner-private strict REGTEST config.
No arbitrary RPC endpoint, cookie fallback, or owner-mainnet miner is accepted.
"""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import time

from .core import verified_core_paths
from .core_process import (
    CoreBindingError, _image, _metadata, _linux_socket, _mac_socket,
    _windows_socket,
)


class AttachedCoreError(ValueError):
    pass


def _birth(pid):
    """OS observed PID creation identity; never infer from a user-supplied PID."""
    if type(pid) is not int or not 2 <= pid <= 2**31-1:
        raise AttachedCoreError("ATTACH_PID_DENIED")
    try:
        if sys.platform=="linux":
            proc=Path(f"/proc/{pid}")
            if proc.stat().st_uid!=os.geteuid():
                raise AttachedCoreError("ATTACH_PROCESS_OWNER_DENIED")
            raw=(proc/"stat").read_text()
            # Linux comm may contain spaces or ')' characters.
            fields=raw.rsplit(")",1)[1].split()
            if len(fields)<20 or not fields[19].isdigit() or int(fields[19])<=0:
                raise AttachedCoreError("ATTACH_PROCESS_BIRTH_DENIED")
            cmd=(proc/"cmdline").read_bytes().split(b"\0")
            if cmd[-1:]==[b""]:cmd.pop()
            # Arbitrary runner processes legitimately have different argv.
            # Exact wamd/-datadir/-daemon=0 argv is enforced ONLY by the
            # actual AttachedCoreBinding before contacting RPC.
            return ("linux",int(fields[19]),tuple(cmd))
        if sys.platform=="darwin":
            # /bin/ps reads kernel process metadata; never executes the Core
            # CLI or reads its wallet. Require the native user's UID.
            tool=Path("/bin/ps")
            info=tool.lstat()
            if (not stat.S_ISREG(info.st_mode) or info.st_uid!=0
                    or info.st_mode&0o022):
                raise AttachedCoreError("ATTACH_SYSTEM_PROCESS_PROBE_DENIED")
            response=subprocess.run(
                [str(tool),"-p",str(pid),"-o","uid=","-o","lstart="],
                stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,timeout=3,check=False,
                env={"PATH":"/usr/bin:/bin:/usr/sbin:/sbin","LC_ALL":"C"})
            line=response.stdout.decode("ascii").strip()
            match=re.fullmatch(
                r"([0-9]+)\s+([A-Z][a-z]{2}\s+[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+\d{4})",
                line)
            if (response.returncode or len(response.stdout)>160 or
                    match is None or int(match.group(1))!=os.geteuid()):
                raise AttachedCoreError("ATTACH_PROCESS_BIRTH_DENIED")
            return ("macos",pid,match.group(2))
        if sys.platform=="win32":
            from ctypes import wintypes as w
            api=ctypes.WinDLL("kernel32",use_last_error=True)
            api.OpenProcess.argtypes=(w.DWORD,w.BOOL,w.DWORD)
            api.OpenProcess.restype=w.HANDLE
            api.GetProcessTimes.argtypes=(w.HANDLE,
                ctypes.POINTER(w.FILETIME),ctypes.POINTER(w.FILETIME),
                ctypes.POINTER(w.FILETIME),ctypes.POINTER(w.FILETIME))
            api.GetProcessTimes.restype=w.BOOL
            api.CloseHandle.argtypes=(w.HANDLE,)
            api.CloseHandle.restype=w.BOOL
            handle=api.OpenProcess(0x1000,False,pid)
            if not handle:
                raise AttachedCoreError("ATTACH_PROCESS_BIRTH_DENIED")
            try:
                created=w.FILETIME();exited=w.FILETIME()
                kernel=w.FILETIME();user=w.FILETIME()
                if not api.GetProcessTimes(handle,ctypes.byref(created),
                       ctypes.byref(exited),ctypes.byref(kernel),
                       ctypes.byref(user)):
                    raise AttachedCoreError("ATTACH_PROCESS_BIRTH_DENIED")
                value=(created.dwHighDateTime<<32)|created.dwLowDateTime
                if value<=0:raise AttachedCoreError("ATTACH_PROCESS_BIRTH_DENIED")
                return ("windows",pid,value)
            finally:api.CloseHandle(handle)
        raise AttachedCoreError("ATTACH_NATIVE_PROCESS_REQUIRED")
    except AttachedCoreError:raise
    except (OSError,ValueError,UnicodeError,IndexError,AttributeError):
        raise AttachedCoreError("ATTACH_PROCESS_BIRTH_DENIED") from None


class AttachedCoreBinding:
    """Non-owning, read-only binding to a pre-existing specific native process."""

    def __init__(self,core,directory,pid,*,authorized_readonly=False):
        if (authorized_readonly is not True or type(core) is not type(Path())
                or type(directory) is not type(Path())
                or not core.is_absolute() or not directory.is_absolute()
                or core.is_symlink() or directory.is_symlink()
                or type(pid) is not int or not 2<=pid<=2**31-1):
            raise AttachedCoreError("ATTACH_EXPLICIT_DISPOSABLE_REGTEST_CONSENT_REQUIRED")
        self.core,self.directory,self.pid=core,directory,pid
        # Refuse a foreign or replaced image BEFORE any credential-bearing RPC.
        self._birth_id=_birth(pid)
        expected_node=core/("wamd.exe" if sys.platform=="win32" else "wamd")
        expected_cli=core/("wam-cli.exe" if sys.platform=="win32" else "wam-cli")
        before=(_metadata(expected_node),_metadata(expected_cli))
        self.node,self.cli,self.receipt=verified_core_paths(core)
        if self.node!=expected_node or self.cli!=expected_cli:
            raise AttachedCoreError("ATTACH_CORE_PAIR_DENIED")
        after=(_metadata(self.node),_metadata(self.cli))
        if before!=after:
            raise AttachedCoreError("ATTACH_CORE_REPLACED_DURING_VERIFY")
        self._files=after
        self._image_path=str(self.node.resolve(strict=True))
        if sys.platform=="linux":
            expected=(str(self.node).encode(),f"-datadir={directory}".encode(),b"-daemon=0")
            if self._birth_id[2]!=expected:
                raise AttachedCoreError("ATTACH_PROCESS_ARGS_DENIED")
        self._assert_image()

    def __repr__(self):
        return "<AttachedCoreBinding external REGTEST read-only>"

    def _assert_image(self):
        try:
            if _birth(self.pid)!=self._birth_id:
                raise AttachedCoreError("ATTACH_PID_REUSED_OR_EXITED")
            observed=_image(self.pid,self.directory)
            same=(os.path.samefile(observed,self.node) if sys.platform=="win32"
                  else os.path.normcase(observed)==os.path.normcase(self._image_path))
            if not same:
                raise AttachedCoreError("ATTACH_FOREIGN_PROCESS_DENIED")
            if self._files!=(_metadata(self.node),_metadata(self.cli)):
                raise AttachedCoreError("ATTACH_EXECUTABLE_CHANGED")
        except AttachedCoreError:raise
        except (OSError,CoreBindingError,ValueError):
            raise AttachedCoreError("ATTACH_PROCESS_IDENTITY_DENIED") from None

    def assert_socket(self,sock):
        self._assert_image()
        local,remote=sock.getsockname(),sock.getpeername()
        if local[0]!="127.0.0.1" or remote[0]!="127.0.0.1":
            raise AttachedCoreError("ATTACH_LOOPBACK_REQUIRED")
        deadline=time.monotonic()+1
        while True:
            self._assert_image()
            try:
                if sys.platform=="darwin":
                    found=_mac_socket(self.pid,remote[1],local[1])
                elif sys.platform=="linux":
                    found=_linux_socket(self.pid,remote[1],local[1])
                elif sys.platform=="win32":
                    found=_windows_socket(self.pid,remote[1],local[1],self.directory)
                else:
                    raise AttachedCoreError("ATTACH_NATIVE_ENDPOINT_REQUIRED")
            except (OSError,CoreBindingError,ValueError):
                raise AttachedCoreError("ATTACH_ENDPOINT_IDENTITY_DENIED") from None
            if found:
                self._assert_image()
                return
            if time.monotonic()>=deadline:
                raise AttachedCoreError("ATTACH_FOREIGN_ENDPOINT_DENIED")
            time.sleep(.02)


class AttachedReadOnlyCore:
    """Only block/network reads; no Popen handle, mutation or wallet RPC API."""

    def __init__(self,core,directory,pid,*,authorized_readonly=False):
        if authorized_readonly is not True:
            raise AttachedCoreError("ATTACH_READONLY_CONSENT_REQUIRED")
        self._binding=AttachedCoreBinding(
            core,directory,pid,authorized_readonly=True)
        from .json_rpc import ManagedReadRpc
        try:
            self._reader=ManagedReadRpc(
                core,directory,binding=self._binding,authorized_readonly=True)
        except Exception:
            raise AttachedCoreError("ATTACH_CORE_READ_DENIED") from None

    def attest(self):
        return self._reader.attest()

    def call(self,method,params=None):
        # Do not forward any unvalidated, write or wallet-selecting operation.
        from .json_rpc import _params
        _params(method,[] if params is None else params)
        return self._reader.call(method,params)

    def close(self):
        self._reader.close()

    def __enter__(self):
        return self

    def __exit__(self,*_):
        self.close()

    def __repr__(self):
        return "<AttachedReadOnlyCore verified REGTEST no-spend>"


def attach_existing_core(core,directory,pid,*,authorized_readonly=False):
    """Never spawns or adopts a process, wallet or datadir."""
    return AttachedReadOnlyCore(core,directory,pid,
                                authorized_readonly=authorized_readonly)
