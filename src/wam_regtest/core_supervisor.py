"""Q05 Stage A: independent owned REGTEST Core, control-only IPC.

Selectively adapted from PR #66/#122, not its wallet/recovery stack. Only the
creator's Popen grants authority. No PID adoption, external attachment, generic
RPC, wallet keys, automatic recovery, config repair or chain deletion.
"""
from contextlib import ExitStack, contextmanager
from hashlib import sha256
import json
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import time

from .core import verified_core_paths, _write_private_config, _read_cli, CoreSmokeError
from .core_process import OwnedCoreBinding, CoreBindingError
from .custody import create_directory, storage
from .json_rpc import ManagedReadRpc, RpcError
from .network_policy import local_rpc_port
from .rpc_credentials import private_bytes
from .rpc_scope import register, unregister, reauthenticate_owned
from .supervisor_protocol import (
    PROTOCOL, MAX_FRAME, ReplayGuard, decode_frame, public_status,
    SupervisorProtocolError, _distinct,
)
from .supervisor_store import create_once, read_exact, exclusive_lease
from .wsp_live import REGTEST_GENESIS

PROFILE_SCHEMA = 'wam-fusion-owned-supervisor-profile/v1'
BUSY_COOLDOWN = 12
# Fixed private diagnostics, never arbitrary exception text or credentials.
DIAGNOSTIC_CODES = frozenset((
    'RPC_HTTP_DENIED','RPC_MANAGED_OPEN_DENIED','RPC_CORE_WARMUP',
    'RPC_CONNECTION_UNCERTAIN_READ_FAILED','RPC_AUTHENTICATION_DENIED',
    'RPC_CONFIG_CHANGED','RPC_CONFIG_CUSTODY_DENIED','RPC_GENESIS_DENIED',
    'RPC_EXTERNAL_PEERS_DENIED','RPC_MANAGED_PROCESS_REQUIRED',
    'RPC_EXECUTABLE_CHANGED','RPC_PROCESS_IMAGE_DENIED','RPC_ENDPOINT_OWNER_DENIED',
    'RPC_OWNED_PROCESS_EXITED','MANAGED_START_TIMEOUT','MANAGED_IDENTITY_CHANGED',
    'CORE_RPC_WARMUP','CORE_RPC_UNAVAILABLE','CORE_RPC_SCOPE_FAULTED',
    'MANAGED_SHUTDOWN_UNCERTAIN',
))


class ManagedCoreError(ValueError):
    """Fixed public codes only; never include paths, logs or credentials."""


def _profile_read(root):
    try:
        value = json.loads(read_exact(root, 'supervisor.profile').decode('ascii'),
                           object_pairs_hook=_distinct)
        if (type(value) is not dict or set(value) != {
                'schema', 'version', 'network', 'genesis', 'core_sha256',
                'cli_sha256', 'config_sha256', 'control_port', 'profile_id',
                'mainnet_allowed'} or value['schema'] != PROFILE_SCHEMA
                or value['version'] != 'v0.1.11' or value['network'] != 'regtest'
                or value['genesis'] != REGTEST_GENESIS
                or value['mainnet_allowed'] is not False
                or type(value['control_port']) is not int
                or not 1024 <= value['control_port'] <= 65535):
            raise ValueError
        for key, length in (('profile_id', 32), ('core_sha256', 64),
                            ('cli_sha256', 64), ('config_sha256', 64)):
            if type(value[key]) is not str or not re.fullmatch(
                    '[0-9a-f]{' + str(length) + '}', value[key]):
                raise ValueError
        return value
    except (OSError, ValueError, UnicodeError):
        raise ManagedCoreError('MANAGED_PROFILE_DENIED') from None


def _listener(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if sys.platform == 'win32':
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('127.0.0.1', port))
        sock.listen(8)
        sock.settimeout(1)
        return sock
    except BaseException:
        sock.close()
        raise


@contextmanager
def _ports():
    # Hold both reservations through config publication. The release-to-Core
    # race is denied by OwnedCoreBinding before any credential bytes are sent.
    with socket.socket() as rpc, socket.socket() as peer:
        for sock in (rpc, peer):
            if sys.platform == 'win32':
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            sock.bind(('127.0.0.1', 0))
        yield rpc.getsockname()[1], peer.getsockname()[1]


class CoreSupervisor:
    """Run in a separate process; GUI disconnect never calls shutdown."""

    def __init__(self, root, core, *, authorized=False):
        if authorized is not True:
            raise ManagedCoreError('MANAGED_EXPLICIT_CONSENT_REQUIRED')
        self.root, self.core = root, core
        self.node, self.cli, self.receipt = verified_core_paths(core)
        self.directory = root / 'chain'
        self.stack = ExitStack()
        self.listener = self.process = self.binding = self.read = None
        self.state = 'stopped'
        self._busy_until = 0
        self._faulted = False
        self._registered = False
        try:
            self.stack.enter_context(exclusive_lease(root))
            # Only a completely empty namespace may be initialized. Partial,
            # legacy or corrupt state stays untouched for explicit review.
            entries = {p.name for p in root.iterdir()} - {'supervisor.lock'}
            if not entries:
                self.listener = _listener(0)
                create_directory(self.directory)
                with _ports() as (rpc, peer):
                    _write_private_config(self.directory, rpc, peer)
                config, _ = private_bytes(self.directory, 'wam.conf', 4096)
                create_once(root, 'supervisor.token', secrets.token_bytes(32))
                profile = dict(schema=PROFILE_SCHEMA, version='v0.1.11',
                    network='regtest', genesis=REGTEST_GENESIS,
                    core_sha256=self.receipt['wamd_sha256'],
                    cli_sha256=self.receipt['wam_cli_sha256'],
                    config_sha256=sha256(config).hexdigest(),
                    control_port=self.listener.getsockname()[1],
                    profile_id=secrets.token_hex(16), mainnet_allowed=False)
                create_once(root, 'supervisor.profile',
                    json.dumps(profile, sort_keys=True).encode('ascii'))
            self.profile = _profile_read(root)
            storage().validate_directory(self.directory)
            self._check_profile()
            self.guard = ReplayGuard(read_exact(root, 'supervisor.token', length=32))
            if self.listener is None:
                self.listener = _listener(self.profile['control_port'])
        except BaseException:
            self.close()
            raise

    def _check_profile(self):
        config, _ = private_bytes(self.directory, 'wam.conf', 4096)
        if (self.profile != _profile_read(self.root)
                or self.profile['core_sha256'] != self.receipt['wamd_sha256']
                or self.profile['cli_sha256'] != self.receipt['wam_cli_sha256']
                or self.profile['config_sha256'] != sha256(config).hexdigest()):
            raise ManagedCoreError('MANAGED_IDENTITY_CHANGED')
        return local_rpc_port(self.directory)

    def _record_failure(self, stage, error):
        code = (error.args[0] if type(error) in
                (RpcError, CoreBindingError, CoreSmokeError, ManagedCoreError)
                and len(error.args)==1 and type(error.args[0]) is str
                and error.args[0] in DIAGNOSTIC_CODES
                else 'MANAGED_UNCLASSIFIED_FAILURE')
        record = json.dumps({'stage':stage,'code':code},sort_keys=True).encode('ascii')
        try:
            # Preserve the first failure; create-only native custody, bounded
            # data and no repair/overwrite even while already faulted.
            create_once(self.root,'supervisor.failure',record)
        except (ValueError,OSError):
            pass  # No successful operation follows diagnostic publication failure.

    def start(self, *, timeout=90):
        if (type(timeout) is not int or not 1 <= timeout <= 90
                or self.process is not None or self._faulted):
            raise ManagedCoreError('MANAGED_START_NOT_ALLOWED')
        port = self._check_profile()
        # Never adopt a listener or rewrite durable config to evade a conflict.
        with _listener(port):
            pass
        if sys.platform == 'win32':
            from .windows_core_regtest_smoke import _host_env
            env = _host_env(self.directory)
        else:
            env = {'PATH': '/usr/bin:/bin:/usr/sbin:/sbin',
                   'HOME': str(self.directory), 'LC_ALL': 'C'}
        self.state = 'starting'
        try:
            self.process = subprocess.Popen(
                [str(self.node), f'-datadir={self.directory}', '-daemon=0'],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, env=env,
                cwd=self.node.parent if sys.platform == 'win32' else self.directory,
                creationflags=0x08000000 if sys.platform == 'win32' else 0)
            self.binding = OwnedCoreBinding(self.process, self.core, self.directory)
            # Writes stay behind Q02/Q03 signed CLI. No HTTP write API or IPC
            # wallet authority is added. This grant is local to this owner.
            register(self.process, self.core, self.directory,
                     authorized_disposable_mutation=True)
            self._registered = True
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                self.binding._assert_image()
                try:
                    probe = socket.create_connection(('127.0.0.1', port), timeout=.25)
                except (ConnectionRefusedError, socket.timeout):
                    time.sleep(.1)
                    continue
                with probe:
                    self.binding.assert_socket(probe)
                try:
                    self.read = ManagedReadRpc(self.core, self.directory,
                        authorized_readonly=True, binding=self.binding)
                    self.state = 'ready'
                    return
                except RpcError as error:
                    if error.args != ('RPC_CORE_WARMUP',):
                        raise
                    time.sleep(.1)
            raise ManagedCoreError('MANAGED_START_TIMEOUT')
        except BaseException as error:
            # Keep the Popen, lease and datadir. Never kill an unverified child
            # or automatically launch a replacement after uncertain startup.
            self._faulted = True
            self.state = 'recovery-needed'
            self._record_failure('start',error)
            raise

    def status(self):
        if self.process is None:
            return public_status(state=self.state)
        if self.process.poll() is not None:
            self._faulted = True
            self.state = 'recovery-needed'
            if self.read is not None:
                self.read.close()
                self.read = None
            return public_status(state=self.state)
        if self._faulted:
            return public_status(state='recovery-needed')
        try:
            self._check_profile()
            self.binding._assert_image()
            if time.monotonic() < self._busy_until:
                return public_status(state='busy', owned=True)
            info = self.read.call('getblockchaininfo')
            self.state = 'syncing' if info.get('initialblockdownload') is True else 'ready'
            return public_status(state=self.state, chain_height=info['blocks'], owned=True)
        except RpcError as error:
            if error.args == ('RPC_NODE_BUSY',):
                self._busy_until = time.monotonic() + BUSY_COOLDOWN
                return public_status(state='busy', owned=True)
            self._faulted = True
        except (OSError, ValueError, RuntimeError):
            self._faulted = True
        self.state = 'recovery-needed'
        return public_status(state=self.state)

    def shutdown(self):
        if self.process is None or self._faulted:
            raise ManagedCoreError('MANAGED_STOP_NOT_ALLOWED')
        self._check_profile()
        self.binding._assert_image()
        try:
            _read_cli([str(self.cli), f'-datadir={self.directory}', 'stop'])
            self.process.wait(timeout=20)
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
            self._faulted = True
            self.state = 'recovery-needed'
            raise ManagedCoreError('MANAGED_SHUTDOWN_UNCERTAIN') from None
        if self.read is not None:
            self.read.close()
        unregister(self.directory)
        self._registered = False
        self.read = self.binding = self.process = None
        self.state = 'stopped'

    def recover_stop(self):
        """Explicit authenticated stop, inside the ORIGINAL Popen owner only.

        This never adopts a PID, replays a payment, modifies config or grants
        wallet access. Any lost identity/credential/chain proof refuses. No
        termination fallback: uncertain exit retains ownership and the lease.
        """
        if (self.process is None or type(self.process) is not subprocess.Popen
                or not self._registered or self.process.poll() is not None):
            raise ManagedCoreError('MANAGED_RECOVERY_ORIGINAL_OWNER_REQUIRED')
        self._check_profile()
        verified_core_paths(self.core)
        binding=OwnedCoreBinding(self.process,self.core,self.directory)
        binding._assert_image()
        # Reuse the owned-context explicit reattestation, never external attach
        # or a foreign PID-based mutation capability. It checks endpoint before
        # auth and attests REGTEST genesis/version/peers before stop.
        reauthenticate_owned(self.directory,authorized=True)
        try:
            _read_cli([str(self.cli),f'-datadir={self.directory}','stop'])
            self.process.wait(timeout=20)
        except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired) as error:
            self._faulted=True;self.state='recovery-needed'
            self._record_failure('recover-stop',error)
            raise ManagedCoreError('MANAGED_SHUTDOWN_UNCERTAIN') from None
        if self.read is not None:self.read.close()
        unregister(self.directory)
        self._registered=False
        self.read=self.binding=self.process=None
        # A stopped child does not resolve the original fault or authorize a
        # replacement. Keep restart denied pending explicit journal recovery.
        self._faulted=True;self.state='recovery-needed'

    def handle(self, raw, challenge):
        message = decode_frame(raw)
        op = self.guard.verify(raw, challenge)
        if op == 'start':
            self.start()
        elif op == 'shutdown':
            self.shutdown()
        elif op == 'recover-stop':
            self.recover_stop()
        status = self.status()
        return {**status, 'nonce': message['nonce'],
                'proof': self.guard.sign_status(message['nonce'], status)}

    def serve(self):
        while True:
            try:
                conn, _ = self.listener.accept()
            except socket.timeout:
                continue
            with conn:
                challenge = None
                try:
                    conn.settimeout(3)
                    hello = self.guard.hello()
                    challenge = hello['challenge']
                    conn.sendall(json.dumps(hello).encode('ascii') + b'\n')
                    deadline = time.monotonic() + 3
                    raw = bytearray()
                    while len(raw) <= MAX_FRAME and not raw.endswith(b'\n'):
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise SupervisorProtocolError('SUPERVISOR_FRAME_TIMEOUT')
                        conn.settimeout(remaining)
                        part = conn.recv(min(256, MAX_FRAME + 1 - len(raw)))
                        if not part:
                            break
                        raw.extend(part)
                    reply = self.handle(bytes(raw), challenge)
                    conn.settimeout(3)
                    conn.sendall(json.dumps(reply, sort_keys=True).encode('ascii') + b'\n')
                except (OSError, ValueError, RuntimeError):
                    # Do not echo arbitrary errors or unauthenticated state.
                    continue
                finally:
                    if challenge is not None:
                        self.guard.discard(challenge)

    def close(self):
        # Explicit supervisor exit cannot quietly relinquish a live owner.
        # SIGKILL/crash recovery is a later Q05 stage, never PID adoption here.
        if self.process is not None and self.process.poll() is None:
            raise ManagedCoreError('MANAGED_LIVE_OWNER_CLOSE_DENIED')
        if self.read is not None:
            self.read.close()
        if self._registered:
            unregister(self.directory)
            self._registered = False
        if self.listener is not None:
            self.listener.close()
            self.listener = None
        self.stack.close()
