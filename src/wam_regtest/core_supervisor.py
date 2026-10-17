"""T05 owned-Core supervisor process (REGTEST only).

Independent of GUI lifetime. Only this process owns subprocess.Popen; another
process must never adopt a PID, datadir lock or foreign Core. IPC exports
control/status ONLY, never credentials, RPC, signing or mining.
"""
from __future__ import annotations
from contextlib import ExitStack
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import threading
import time

from .core import verified_core_paths,_read_cli,_write_private_config,CoreSmokeError
from .core_process import OwnedCoreBinding,CoreBindingError
from .json_rpc import ManagedReadRpc,RpcError
from .network_policy import local_rpc_port
from .owned_start import _reserved_ports,_early_exit_category
from .supervisor_protocol import (
    PROTOCOL,ReplayGuard,SupervisorProtocolError,public_status,decode_frame,MAX_FRAME,
)
from .supervisor_store import create_once,read_exact,exclusive_lease,SupervisorStorageError

PROFILE_SCHEMA="wam-fusion-owned-supervisor-profile/v1"
SUPPORTED_VERSION="v0.1.11"


class ManagedCoreError(ValueError):
    """A fixed error code, never a private path or Core log."""


def _pairs(items):
    result={}
    for key,value in items:
        if key in result:raise ManagedCoreError("MANAGED_PROFILE_DUPLICATE_DENIED")
        result[key]=value
    return result


def _profile_read(root):
    try:
        raw=read_exact(root,"supervisor.profile")
        value=json.loads(raw.decode("ascii"),object_pairs_hook=_pairs)
    except ManagedCoreError:raise
    except (SupervisorStorageError,UnicodeError,ValueError):
        raise ManagedCoreError("MANAGED_PROFILE_READ_DENIED") from None
    if (type(value) is not dict or set(value)!={"schema","version","network","genesis",
           "core_sha256","cli_sha256","control_port","profile_id","mainnet_allowed"}
            or value.get("schema")!=PROFILE_SCHEMA
            or value.get("version")!=SUPPORTED_VERSION
            or value.get("network")!="regtest"
            or value.get("mainnet_allowed") is not False
            or type(value.get("control_port")) is not int
            or not 1024<=value["control_port"]<=65535
            or type(value.get("profile_id")) is not str
            or not re.fullmatch("[0-9a-f]{32}",value["profile_id"])):
        raise ManagedCoreError("MANAGED_PROFILE_SHAPE_DENIED")
    return value


def _listener(port):
    sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    try:
        if sys.platform=="win32":
            sock.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        sock.bind(("127.0.0.1",port))
        sock.listen(8)
        sock.settimeout(1.0)
        return sock
    except BaseException:
        sock.close();raise


def _fresh_directory(root):
    from .custody import create_directory
    directory=root/"chain"
    # Never adopt or repair an unexplained pre-existing directory.
    if directory.exists() or directory.is_symlink():
        raise ManagedCoreError("MANAGED_PREEXISTING_CHAIN_DENIED")
    create_directory(directory)
    return directory


class CoreSupervisor:
    """One owner's Core process with stable, protected chain across GUI exits."""
    def __init__(self,root,core,*,authorized=False):
        if authorized is not True:
            raise ManagedCoreError("MANAGED_EXPLICIT_CONSENT_REQUIRED")
        self.root=root;self.core=core
        self.node,self.cli,self.receipt=verified_core_paths(core)
        from .wsp_live import REGTEST_GENESIS
        self.genesis=REGTEST_GENESIS
        self.process=None;self.binding=None;self.read=None
        self.directory=root/"chain";self.listener=None;self.stack=ExitStack()
        self._state="stopped";self._consecutive_failures=0
        self._lock=threading.RLock()
        self._guard=None
        self._init()
 
    def _init(self):
        try:
            # Lock first; never inspect or modify a competing Core's chain.
            self.stack.enter_context(exclusive_lease(self.root))
            try:
                profile=_profile_read(self.root)
                token=read_exact(self.root,"supervisor.token",length=32)
                if not self.directory.is_dir() or self.directory.is_symlink():
                    raise ManagedCoreError("MANAGED_CHAIN_MISSING_DENIED")
                from .custody import storage
                storage().validate_directory(self.directory)
                if (profile["genesis"]!=self.genesis
                        or profile["core_sha256"]!=self.receipt["wamd_sha256"]
                        or profile["cli_sha256"]!=self.receipt["wam_cli_sha256"]):
                    raise ManagedCoreError("MANAGED_CORE_VERSION_OR_CHAIN_MISMATCH")
                self.listener=_listener(profile["control_port"])
            except ManagedCoreError as error:
                # A corrupt or partially written profile is NEVER treated as a
                # fresh install. Provision only when both named files are absent.
                if error.args!=("MANAGED_PROFILE_READ_DENIED",):raise
                if (self.directory.exists() or self.directory.is_symlink()
                        or (self.root/"supervisor.profile").exists()
                        or (self.root/"supervisor.profile").is_symlink()
                        or (self.root/"supervisor.token").exists()
                        or (self.root/"supervisor.token").is_symlink()):
                    raise ManagedCoreError("MANAGED_UNOWNED_OR_PARTIAL_PROFILE_DENIED") from None
                self.listener=_listener(0)
                port=self.listener.getsockname()[1]
                if port<1024:raise ManagedCoreError("MANAGED_CONTROL_PORT_DENIED")
                self.directory=_fresh_directory(self.root)
                with _reserved_ports() as (rpc,p2p):
                    _write_private_config(self.directory,rpc,p2p)
                token=secrets.token_bytes(32)
                create_once(self.root,"supervisor.token",token)
                data={"schema":PROFILE_SCHEMA,"version":SUPPORTED_VERSION,
                      "network":"regtest","genesis":self.genesis,
                      "core_sha256":self.receipt["wamd_sha256"],
                      "cli_sha256":self.receipt["wam_cli_sha256"],
                      "control_port":port,"profile_id":secrets.token_hex(16),
                      "mainnet_allowed":False}
                create_once(self.root,"supervisor.profile",
                    (json.dumps(data,sort_keys=True,separators=(",",":"))+"\n").encode("ascii"))
                profile=_profile_read(self.root)
            self.profile=profile
            self._guard=ReplayGuard(token)
            # No token, password, datadir path or RPC port in public evidence.
        except BaseException:
            self.close_listener();self.stack.close();raise

    def close_listener(self):
        if self.listener is not None:
            self.listener.close();self.listener=None

    def _child_environment(self):
        if sys.platform=="win32":
            from .windows_core_regtest_smoke import _host_env
            return _host_env(self.directory)
        return {"PATH":"/usr/bin:/bin:/usr/sbin:/sbin",
                "HOME":str(self.directory),"LC_ALL":"C"}

    def _ready(self,deadline):
        rpcport=local_rpc_port(self.directory)
        while time.monotonic()<deadline:
            if self.process.poll() is not None:
                raise ManagedCoreError("MANAGED_CHILD_EXITED")
            try:
                probe=socket.create_connection(("127.0.0.1",rpcport),timeout=.25)
            except (ConnectionRefusedError,socket.timeout):
                time.sleep(.05);continue
            except OSError:
                raise ManagedCoreError("MANAGED_RPC_TCP_DENIED") from None
            try:
                with probe:self.binding.assert_socket(probe)
                read=ManagedReadRpc(self.core,self.directory,
                    authorized_readonly=True,binding=self.binding)
                try:
                    info=read.attest()
                    if info.get("chain")!="regtest":
                        raise ManagedCoreError("MANAGED_CHAIN_IDENTITY_DENIED")
                    return read
                except BaseException:read.close();raise
            except RpcError as error:
                if error.args not in (("RPC_CORE_WARMUP",),("RPC_NODE_BUSY",)):
                    raise ManagedCoreError("MANAGED_RPC_ATTESTATION_DENIED") from None
                time.sleep(.1)
            except CoreBindingError:
                raise ManagedCoreError("MANAGED_ENDPOINT_OWNERSHIP_DENIED") from None
        raise ManagedCoreError("MANAGED_START_TIMEOUT")

    def start(self,*,timeout=90):
        with self._lock:
            if (type(timeout) is not int or not 10<=timeout<=240
                    or self.process is not None
                    or self._consecutive_failures>=3):
                raise ManagedCoreError("MANAGED_START_NOT_ALLOWED")
            self._state="starting"
            try:
                # Chain stays in a durable owner-only directory. Config is
                # create-once, never changed to evade conflicts.
                if local_rpc_port(self.directory) not in range(1,65536):
                    raise ManagedCoreError("MANAGED_CONFIG_DENIED")
                env=self._child_environment()
                # Never open an untrusted reusable log path. Core writes its
                # own protected chain logs; application stdout is discarded.
                self.process=subprocess.Popen(
                    [str(self.node),f"-datadir={self.directory}","-daemon=0"],
                    stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                    cwd=self.node.parent if sys.platform=="win32" else self.directory,
                    env=env,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0) if sys.platform=="win32" else 0,
                )
                self.binding=OwnedCoreBinding(self.process,self.core,self.directory)
                self.read=self._ready(time.monotonic()+timeout)
                self._consecutive_failures=0
                self._state="ready"
            except BaseException:
                self._consecutive_failures+=1
                self._state="recovery-needed"
                if self.process is not None and self.process.poll() is None:
                    # No unverified PID termination, even when launch fails.
                    try:
                        if self.binding is not None:self.binding._assert_image()
                        else:raise ManagedCoreError("MANAGED_UNVERIFIED_CHILD_LEFT_RUNNING")
                    except BaseException:raise ManagedCoreError("MANAGED_UNVERIFIED_CHILD_LEFT_RUNNING") from None
                    self.process.terminate()
                    try:self.process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        self.process.kill();self.process.wait(timeout=5)
                self.process=None;self.binding=None
                if self.read is not None:self.read.close();self.read=None
                raise

    def status(self):
        with self._lock:
            if self.process is None:return public_status(state=self._state)
            if self.process.poll() is not None:
                self._state="recovery-needed"
                if self.read is not None:self.read.close();self.read=None
                self.binding=None;self.process=None
                return public_status(state=self._state)
            try:
                self.binding._assert_image()
                info=self.read.attest()
                height=info["blocks"]
                self._state="syncing" if info.get("initialblockdownload") is True else "ready"
                return public_status(state=self._state,owned=True,chain_height=height)
            except RpcError as error:
                if error.args==("RPC_NODE_BUSY",):
                    self._state="busy"
                    return public_status(state="busy",owned=True)
                self._state="recovery-needed"
                return public_status(state=self._state)
            except Exception:
                self._state="recovery-needed"
                return public_status(state=self._state)

    def shutdown(self):
        with self._lock:
            if self.process is None:
                raise ManagedCoreError("MANAGED_NO_OWNED_PROCESS")
            self.binding._assert_image()
            process=self.process
            try:
                # Never send stop to an attached/external Core, only the verified
                # subprocess whose connected socket was proven pre-auth.
                port=local_rpc_port(self.directory)
                with socket.create_connection(("127.0.0.1",port),timeout=1) as sock:
                    self.binding.assert_socket(sock)
                _read_cli([str(self.cli),f"-datadir={self.directory}","stop"])
                process.wait(timeout=20)
            except Exception:
                if process.poll() is None:
                    self.binding._assert_image()
                    process.terminate()
                    try:process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill();process.wait(timeout=5)
            finally:
                # Never report STOPPED if termination remains uncertain.
                if process.poll() is None:
                    self._state="recovery-needed"
                else:
                    if self.read is not None:self.read.close()
                    self.process=None;self.read=None;self.binding=None
                    self._state="stopped"

    def handle(self,raw):
        # All request authorization is checked before state, Core or RPC.
        message=decode_frame(raw)
        op=self._guard.verify(raw)
        if op=="start":
            if self.process is None:self.start()
        elif op=="shutdown":
            self.shutdown()
        status=self.status()
        return {**status,"nonce":message["nonce"],
                "proof":self._guard.sign_status(message["nonce"],status)}

    def serve(self):
        if self.listener is None:raise ManagedCoreError("MANAGED_NO_LISTENER")
        # GUI may come and go; this process and Core remain alive.
        while True:
            try:conn,_=self.listener.accept()
            except socket.timeout:continue
            with conn:
                conn.settimeout(3)
                try:
                    payload=bytearray()
                    while len(payload)<MAX_FRAME:
                        block=conn.recv(1)
                        if not block:break
                        payload.extend(block)
                        if block==b"\n":break
                    reply=self.handle(bytes(payload))
                except (SupervisorProtocolError,ManagedCoreError,
                        RpcError,SupervisorStorageError,CoreBindingError):
                    reply={"protocol":PROTOCOL,"state":"error",
                           "height":None,"core_process_owned":False,
                           "chain":"regtest","mainnet_allowed":False}
                conn.sendall((json.dumps(reply,sort_keys=True)+"\n").encode("ascii"))
