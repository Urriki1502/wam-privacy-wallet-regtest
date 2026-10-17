"""Bounded startup of disposable v0.1.11 REGTEST only; no attach/persistent API.

Never accepts an existing datadir, endpoint or config. Retry only a positively
observed bind failure BEFORE any wallet exists. Every attempt has fresh private
storage/credentials. OS socket ownership is checked before HTTP auth or CLI use.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from .core import verified_core_paths, _write_private_config, _early_exit_category, CoreSmokeError
from .core_process import OwnedCoreBinding, CoreBindingError
from .json_rpc import ManagedReadRpc, RpcError

MAX_START_ATTEMPTS = 3


class _BindCollision(Exception):
    pass


@contextmanager
def _reserved_ports():
    sockets = []
    try:
        for _ in range(2):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM);sockets.append(s)
            if sys.platform == 'win32':s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            s.bind(('127.0.0.1', 0))
        # Both sockets remain bound until config publication is complete.
        # There is still a handoff race; _ready never authenticates a stranger.
        yield tuple(s.getsockname()[1] for s in sockets)
    finally:
        for s in sockets:s.close()


def _exited(process, directory):
    if process.poll() is None:return
    category = _early_exit_category(directory)
    if category == 'CORE_DAEMON_PORT_BIND_DENIED':raise _BindCollision()
    raise CoreSmokeError(category)


def _ready(binding, port, deadline):
    warmups=0
    while time.monotonic() < deadline:
        _exited(binding.process, binding.directory)
        try:
            probe=socket.create_connection(('127.0.0.1',port),timeout=.25)
        except (ConnectionRefusedError,socket.timeout):
            # Windows may time out before returning a loopback TCP refusal.
            # No RPC/auth bytes exist yet; this is not a request replay.
            time.sleep(min(.05,max(0,deadline-time.monotonic())));continue
        except OSError as error:
            code=getattr(error,'winerror',None) or error.errno
            suffix=str(code) if type(code) is int and 0<=code<=65535 else 'UNKNOWN'
            raise CoreSmokeError('CORE_START_TCP_PROBE_DENIED_'+suffix) from None
        try:
            with probe:
                # Raw TCP only; this sends ZERO HTTP/authentication bytes.
                binding.assert_socket(probe)
            read = ManagedReadRpc(binding.core, binding.directory,
                authorized_readonly=True, binding=binding)
            try:
                if read.attest()['blocks'] != 0:raise CoreSmokeError('CORE_START_FRESH_CHAIN_REQUIRED')
                return read
            except BaseException:
                read.close();raise
        except RpcError as error:
            if error.args!=('RPC_CORE_WARMUP',):raise
            warmups+=1
            if warmups>=30:raise CoreSmokeError('CORE_START_WARMUP_LIMIT') from None
            time.sleep(min(.05*(2**(warmups-1)),1,max(0,deadline-time.monotonic())))
        except CoreBindingError:
            # A competing listener may precede Core's own bind-failure exit.
            # Only the actual owned process's private log + EXIT permits retry.
            try:binding.process.wait(timeout=1)
            except subprocess.TimeoutExpired:pass
            _exited(binding.process, binding.directory)
            raise CoreSmokeError('CORE_START_ENDPOINT_OWNERSHIP_DENIED') from None
    raise CoreSmokeError('CORE_START_TIMEOUT')


def _reap(process):
    # This API owns a fresh disposable process only. Never signal an attached
    # node, invoke RPC stop on a competing listener or kill by guessed PID.
    if process is None:return
    if process.poll() is None:
        process.terminate()
        try:process.wait(timeout=12)
        except subprocess.TimeoutExpired:
            process.kill();process.wait(timeout=6)
    else:process.wait(timeout=1)


@dataclass(frozen=True,repr=False)
class DisposableCore:
    node: Path
    cli: Path
    directory: Path
    process: subprocess.Popen
    read: ManagedReadRpc
    receipt: dict
    environment: dict
    attempts: int

    def __repr__(self):return '<DisposableCore owned REGTEST>'


@contextmanager
def disposable_core(core, *, authorized=False, timeout=90):
    if authorized is not True:raise CoreSmokeError('CORE_START_EXPLICIT_DISPOSABLE_CONSENT_REQUIRED')
    if type(timeout) not in (int,float) or not 1 <= timeout <= 240:
        raise CoreSmokeError('CORE_START_TIMEOUT_DENIED')
    if type(core) is not type(Path()) or not core.is_absolute():
        raise CoreSmokeError('CORE_START_PATH_DENIED')
    node, cli, receipt = verified_core_paths(core)
    with tempfile.TemporaryDirectory(prefix='wam-owned-start-') as temp:
        root = Path(temp).resolve(strict=True)
        if sys.platform != 'win32':root.chmod(0o700)
        deadline = time.monotonic()+timeout
        for attempt in range(1, MAX_START_ATTEMPTS+1):
            from .custody import create_directory
            directory = root/f'chain-{attempt}';create_directory(directory)
            if sys.platform == 'win32':
                from .windows_core_regtest_smoke import _host_env
                env = _host_env(directory)
            else:env = {'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','HOME':str(directory),'LC_ALL':'C'}
            process = read = None
            try:
                with _reserved_ports() as (rpc, peer):_write_private_config(directory, rpc, peer)
                with (directory/'core-output.log').open('xb') as log:
                    process = subprocess.Popen([str(node),f'-datadir={directory}','-daemon=0'],
                        stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                        cwd=node.parent if sys.platform=='win32' else directory, env=env,
                        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0) if sys.platform=='win32' else 0)
                try:
                    try:binding = OwnedCoreBinding(process, core, directory)
                    except CoreBindingError:
                        _exited(process, directory)
                        raise CoreSmokeError('CORE_START_PROCESS_IDENTITY_DENIED') from None
                    read = _ready(binding, rpc, deadline)
                except _BindCollision:
                    if attempt == MAX_START_ATTEMPTS or time.monotonic() >= deadline:
                        raise CoreSmokeError('CORE_START_PORT_RETRIES_EXHAUSTED') from None
                    continue
                # Once yielded, any error propagates without restart/retry.
                yield DisposableCore(node,cli,directory,process,read,dict(receipt),env,attempt)
                return
            finally:
                if read is not None:read.close()
                _reap(process)
