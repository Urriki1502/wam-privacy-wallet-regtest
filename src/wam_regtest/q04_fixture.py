"""Disposable isolated REGTEST fixture for Q04 solo-miner coexistence.

Creates an independently controlled WAM Core node and a separate solo-miner
process. Fusion wallet attaches read-only to the Core. The fixture verifies that
Fusion monitoring does not disrupt miner block production or RPC.

This fixture performs explicitly authorized test mining inside its own isolated
REGTEST environment. It NEVER accesses, modifies, restarts or interferes with
the repository owner's real mining equipment, node, configuration, wallet or
private keys.
"""
from __future__ import annotations

import json
import secrets
import socket
import subprocess
import time
from pathlib import Path

from .core import smoke_real_core, CoreSmokeError, _write_private_config, _port
from .external_core import ExternalCoreAttachment, ExternalAttachmentError
from .telemetry import increment


class Q04FixtureError(RuntimeError):
    """Fixed redacted fixture status."""


class SoloMinerFixture:
    """Isolated REGTEST Core + solo miner + Fusion read-only observer.

    The fixture owns and controls the Core and miner processes. Fusion attaches
    read-only to the Core using the same ExternalCoreAttachment boundary used for
    user-declared external nodes.
    """

    def __init__(self, core_dir: Path, timeout: int = 120):
        if type(core_dir) is not type(Path()) or not core_dir.is_absolute():
            raise Q04FixtureError('Q04_FIXTURE_CORE_DIR_REQUIRED')
        self._core_dir = core_dir
        self._timeout = timeout
        self._core_process: subprocess.Popen | None = None
        self._miner_process: subprocess.Popen | None = None
        self._datadir: Path | None = None
        self._rpc_port: int | None = None
        self._p2p_port: int | None = None
        self._attachment: ExternalCoreAttachment | None = None

    def _free_port(self) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(('127.0.0.1', 0))
            return sock.getsockname()[1]

    def start(self) -> dict:
        """Start isolated Core and miner. Returns attachment spec."""
        from .custody import private_temporary_directory
        self._datadir = private_temporary_directory(prefix='q04_miner_')
        self._rpc_port = self._free_port()
        self._p2p_port = self._free_port()
        _write_private_config(self._datadir, self._rpc_port, self._p2p_port)

        node, cli, receipt = self._verified_core_paths(self._core_dir)

        # Start Core daemonized in foreground mode so we own the Popen.
        argv = [str(node), f'-datadir={self._datadir}', '-daemon=0']
        self._core_process = subprocess.Popen(
            argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)

        # Wait for RPC cookie to appear.
        cookie = self._datadir / 'regtest' / '.cookie'
        deadline = time.monotonic() + self._timeout
        while not cookie.exists():
            if self._core_process.poll() is not None:
                raise Q04FixtureError('Q04_FIXTURE_CORE_EXITED')
            if time.monotonic() >= deadline:
                raise Q04FixtureError('Q04_FIXTURE_CORE_START_TIMEOUT')
            time.sleep(0.2)

        # Attach Fusion read-only.
        self._attachment = ExternalCoreAttachment(
            pid=self._core_process.pid,
            rpc_port=self._rpc_port,
            datadir=self._datadir,
            core_dir=self._core_dir,
            operator_consent=True,
            timeout=10.0,
        )

        # Start a simple solo miner loop using the signed CLI generate command.
        # This is an isolated REGTEST fixture; mining is explicitly authorized here.
        miner_argv = [str(cli), f'-datadir={self._datadir}', '-regtest=1', '-rpcwait',
                      'generatetoaddress', '1', self._fixture_address(cli)]
        self._miner_process = subprocess.Popen(
            miner_argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)

        increment('q04_fixture_started')
        return {
            'pid': self._core_process.pid,
            'rpc_port': self._rpc_port,
            'datadir': str(self._datadir),
            'core_dir': str(self._core_dir),
            'operator_consent': True,
        }

    def _verified_core_paths(self, core_dir: Path):
        from .core import verified_core_paths
        return verified_core_paths(core_dir)

    def _fixture_address(self, cli: Path) -> str:
        result = subprocess.run(
            [str(cli), f'-datadir={self._datadir}', '-regtest=1', 'getnewaddress'],
            capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise Q04FixtureError('Q04_FIXTURE_ADDRESS_FAILED')
        return result.stdout.strip()

    def mine_blocks(self, count: int = 1) -> dict:
        """Mine blocks without Fusion intervention; measure miner continuity."""
        if self._attachment is None:
            raise Q04FixtureError('Q04_FIXTURE_NOT_STARTED')
        before = self._attachment.read('getblockcount', [])
        # Use the miner CLI directly, not Fusion, to avoid write scope on attachment.
        node, cli, _ = self._verified_core_paths(self._core_dir)
        for _ in range(count):
            result = subprocess.run(
                [str(cli), f'-datadir={self._datadir}', '-regtest=1', 'generatetoaddress',
                 '1', self._fixture_address(cli)],
                capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                raise Q04FixtureError('Q04_FIXTURE_MINING_FAILED')
        after = self._attachment.read('getblockcount', [])
        return {'before': before, 'after': after, 'mined': after - before}

    def fusion_read(self, method: str, params: list | None = None):
        if self._attachment is None:
            raise Q04FixtureError('Q04_FIXTURE_NOT_STARTED')
        return self._attachment.read(method, params)

    def stop(self):
        if self._miner_process is not None:
            self._miner_process.terminate()
            try:
                self._miner_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._miner_process.kill()
            self._miner_process = None
        if self._attachment is not None:
            self._attachment.close()
            self._attachment = None
        if self._core_process is not None:
            self._core_process.terminate()
            try:
                self._core_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._core_process.kill()
            self._core_process = None
        increment('q04_fixture_stopped')

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stop()
        return False
