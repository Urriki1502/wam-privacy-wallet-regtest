"""T05 owned-Core supervisor process (REGTEST only).

Independent of GUI lifetime. Only this process owns subprocess.Popen; another
process must never adopt a PID, datadir lock or foreign Core. IPC exposes authenticated control/status and a separate strict WSP read-only
block subset. No generic RPC, credentials, wallet keys, signing or mining.
"""
from __future__ import annotations
from contextlib import ExitStack,contextmanager
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
# T-07: protect a busy RPC worker queue from repeated GUI/status polling.
# This is only set after Core positively rejects idempotent reads with 503.
BUSY_STATUS_COOLDOWN_SECONDS=12


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



def _scoped_ipc_tokens(root, *, allow_upgrade=False):
    """Independent scanner/spend capability tokens, never a generic RPC key.

    Explicit supervisor startup may upgrade a complete legacy REGTEST profile
    once. Partial/uncertain token publication fails closed with no repair.
    These owner-private files do not resist compromise of the same OS user.
    """
    names=("supervisor.scan.token","supervisor.spend.token")
    present=tuple((root/name).exists() or (root/name).is_symlink()
                  for name in names)
    if present==(False,False) and allow_upgrade is True:
        for name in names:
            create_once(root,name,secrets.token_bytes(32))
    elif present!=(True,True):
        raise ManagedCoreError("MANAGED_IPC_SCOPE_UPGRADE_REQUIRED")
    try:
        scan=read_exact(root,names[0],length=32)
        spend=read_exact(root,names[1],length=32)
    except SupervisorStorageError:
        raise ManagedCoreError("MANAGED_IPC_SCOPE_CUSTODY_DENIED") from None
    if secrets.compare_digest(scan,spend):
        raise ManagedCoreError("MANAGED_IPC_SCOPE_DUPLICATE_DENIED")
    return scan,spend


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


@contextmanager
def _reserve_existing_rpc_port(port):
    """Preflight *existing* managed REGTEST RPC port without changing config.

    This guard holds an exclusive native IPv4 loopback bind until immediately
    before launching our own daemon. Kernel ownership is independently proven
    after launch and BEFORE any HTTP/authentication bytes. A competing service
    never receives credentials; no Core process, wallet or chain is adopted.
    """
    if type(port) is not int or not 1<=port<=65535:
        raise ManagedCoreError("MANAGED_RPC_PORT_INVALID")
    candidate=None
    acquired=False
    try:
        candidate=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        if sys.platform=="win32":
            candidate.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        else:
            # Clean Core shutdown leaves accepted TCP connections in
            # TIME_WAIT. Do NOT mistake those as a competing listener.
            # SO_REUSEADDR + listen() permits normal restart but still
            # refuses an active server on the exact same loopback port.
            # Never enable SO_REUSEPORT or change the Core RPC exposure.
            candidate.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        candidate.bind(("127.0.0.1",port))
        candidate.listen(1)
        acquired=True
    except OSError:
        raise ManagedCoreError("MANAGED_RPC_PORT_OCCUPIED") from None
    finally:
        if not acquired and candidate is not None:
            candidate.close()
    try:
        yield
    finally:
        candidate.close()


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
        self._busy_until=0.0
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
                # Authenticate the complete original chain/profile first.
                # Separate IPC tokens do not touch wallet keys or Core files.
                scan_token,spend_token=_scoped_ipc_tokens(self.root,allow_upgrade=True)
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
                scan_token=secrets.token_bytes(32)
                spend_token=secrets.token_bytes(32)
                create_once(self.root,"supervisor.scan.token",scan_token)
                create_once(self.root,"supervisor.spend.token",spend_token)
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
            if (secrets.compare_digest(token,scan_token)
                    or secrets.compare_digest(token,spend_token)
                    or secrets.compare_digest(scan_token,spend_token)):
                raise ManagedCoreError("MANAGED_IPC_SCOPE_DUPLICATE_DENIED")
            self._guard=ReplayGuard(token)
            self._scan_secret=scan_token
            self._scan_seen=set()
            self._spend_secret=spend_token
            self._spend_seen=set()
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

    def _ready(self,deadline,rpcport):
        # The protected config was strictly validated BEFORE spawning Core.
        # Don't re-open it during the process/config handoff: ManagedReadRpc
        # independently verifies that exact local config and the OS-bound Core
        # endpoint before any authenticated read. A changed port is denied.
        if type(rpcport) is not int or not 1<=rpcport<=65535:
            raise ManagedCoreError("MANAGED_CONFIG_PORT_DENIED")
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
                    # This socket has already been attested to our Popen-owned
                    # binary. Reject any config port drift, never adopt it.
                    if read._connection.port!=rpcport:
                        raise ManagedCoreError("MANAGED_CONFIG_PORT_CHANGED")
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
            self._busy_until=0.0
            try:
                # Chain stays in a durable owner-only directory. Config is
                # create-once, never changed to evade conflicts.
                rpcport=local_rpc_port(self.directory)
                if type(rpcport) is not int or not 1<=rpcport<=65535:
                    raise ManagedCoreError("MANAGED_CONFIG_DENIED")
                env=self._child_environment()
                # Existing durable profiles have create-once credentials and
                # chain state. NEVER rewrite their RPC/P2P port on collision.
                # Hold an exclusive loopback reservation for the configured
                # port until just before Popen (Core cannot bind while held).
                # A losing handoff is still caught by native server socket
                # ownership proof BEFORE any HTTP or credentials are sent.
                with _reserve_existing_rpc_port(rpcport):
                    pass
                # Never open an untrusted reusable log path. Core writes its
                # own protected chain logs; application stdout is discarded.
                self.process=subprocess.Popen(
                    [str(self.node),f"-datadir={self.directory}","-daemon=0"],
                    stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                    cwd=self.node.parent if sys.platform=="win32" else self.directory,
                    env=env,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0) if sys.platform=="win32" else 0,
                )
                self.binding=OwnedCoreBinding(self.process,self.core,self.directory)
                self.read=self._ready(time.monotonic()+timeout,rpcport)
                self._consecutive_failures=0
                self._busy_until=0.0
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
                self._busy_until=0.0
                self._state="recovery-needed"
                if self.read is not None:self.read.close();self.read=None
                self.binding=None;self.process=None
                return public_status(state=self._state)
            try:
                # Always recheck native ownership even while Core is busy;
                # an exited/swapped Core can NEVER be reported as busy/owned.
                self.binding._assert_image()
                if (self._state=="busy"
                        and time.monotonic()<getattr(self,"_busy_until",0.0)):
                    # Coalesce repeated status/refresh/scanner requests into
                    # one bounded cooling-off interval. NO stale tip/balance.
                    return public_status(state="busy",owned=True)
                info=self.read.attest()
                height=info["blocks"]
                self._busy_until=0.0
                self._state="syncing" if info.get("initialblockdownload") is True else "ready"
                return public_status(state=self._state,owned=True,chain_height=height)
            except RpcError as error:
                if error.args==("RPC_NODE_BUSY",):
                    self._busy_until=time.monotonic()+BUSY_STATUS_COOLDOWN_SECONDS
                    self._state="busy"
                    return public_status(state="busy",owned=True)
                self._busy_until=0.0
                self._state="recovery-needed"
                return public_status(state=self._state)
            except Exception:
                self._busy_until=0.0
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
            # A dead owned child can still have an assigned Popen until a
            # status request reaps it. The first authorized Start must observe
            # that exit BEFORE deciding whether there is already a live Core.
            # Never discard/replace a child whose exit is not established.
            if self.process is not None and self.process.poll() is not None:
                self.status()
            if self.process is None:self.start()
        elif op=="shutdown":
            self.shutdown()
        status=self.status()
        return {**status,"nonce":message["nonce"],
                "proof":self._guard.sign_status(message["nonce"],status)}

    def _scan_handle(self,raw):
        """Only pinned WSP read methods through the owned process's RPC."""
        from .managed_scan_protocol import decode_request,encode_reply
        method,params,nonce=decode_request(raw,self._scan_secret,self._scan_seen)
        # A non-owned or busy Core never provides chain data to a GUI.
        if self.status()["state"]!="ready" or self.read is None:
            raise ManagedCoreError("MANAGED_SCAN_CORE_NOT_READY")
        result=self.read.call(method,params)
        return encode_reply(self._scan_secret,method,nonce,result)

    def _spend_handle(self,raw):
        """One non-retried payment method via the SAME native-owned HTTP Core.

        The GUI owns the WSP keyring, PSBT and anchored reservation. This
        supervisor never receives a secret key or signs a transaction.
        """
        from .managed_spend_protocol import decode_request,encode_reply
        method,params,nonce=decode_request(raw,self._spend_secret,self._spend_seen)
        if self.status()["state"]!="ready" or self.read is None:
            raise ManagedCoreError("MANAGED_SPEND_CORE_NOT_READY")
        result=self.read.write_owned_regtest(method,params,authorized=True)
        return encode_reply(self._spend_secret,method,nonce,result)

    def _serve_client(self,conn):
        """Bound control/scan/spend frames; no failed GUI can stop Core."""
        deadline=time.monotonic()+3.0
        from .managed_spend_protocol import MAX_SPEND_REQUEST,SPEND_PROTOCOL
        try:
            payload=bytearray()
            while len(payload)<MAX_SPEND_REQUEST:
                remaining=deadline-time.monotonic()
                if remaining<=0:
                    raise SupervisorProtocolError("SUPERVISOR_FRAME_TIMEOUT")
                conn.settimeout(remaining)
                block=conn.recv(min(256,MAX_SPEND_REQUEST-len(payload)))
                if not block:break
                payload.extend(block)
                if b"\n" in block:break
            raw=bytes(payload)
            # Dispatch ONLY on a fully parsed, unique protocol field. Neither
            # request body nor arbitrary RPC method is used for routing.
            from .supervisor_protocol import _distinct
            from .managed_scan_protocol import SCAN_PROTOCOL
            try:
                frame=json.loads(raw.decode("ascii"),object_pairs_hook=_distinct)
            except (ValueError,UnicodeError):
                frame=None
            if type(frame) is dict and frame.get("protocol")==SCAN_PROTOCOL:
                scan_reply=self._scan_handle(raw)
                conn.settimeout(15.0)
                conn.sendall(scan_reply)
                return
            if type(frame) is dict and frame.get("protocol")==SPEND_PROTOCOL:
                spend_reply=self._spend_handle(raw)
                conn.settimeout(15.0)
                conn.sendall(spend_reply)
                return
            reply=self.handle(raw)
        except (SupervisorProtocolError,ManagedCoreError,RpcError,
                SupervisorStorageError,CoreBindingError,OSError,ValueError):
            # Never echo exceptions or secret values to an untrusted peer.
            reply=public_status(state="error",owned=False)
        try:
            conn.settimeout(3.0)
            conn.sendall((json.dumps(reply,sort_keys=True,separators=(",",":"))+"\n").encode("ascii"))
        except OSError:
            # Broken pipe/peer abort is normal on GUI restart. Keep the owner
            # process and held native Core binding alive.
            return

    def serve(self):
        if self.listener is None:raise ManagedCoreError("MANAGED_NO_LISTENER")
        # GUI may come and go; this process and Core remain alive.
        while True:
            try:conn,_=self.listener.accept()
            except socket.timeout:continue
            with conn:self._serve_client(conn)
