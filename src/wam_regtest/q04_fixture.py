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

import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

from .core import CoreSmokeError, _port
from .custody import private_temporary_directory
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

    def __init__(self, core_dir: Path, timeout: int = 180):
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
        self._wallet_name: str | None = None

    def _write_cookie_config(self, datadir: Path, rpcport: int, p2pport: int) -> None:
        """Provision regtest config that uses cookie auth (no rpcuser/rpcpassword).

        WAM Core creates regtest/.cookie automatically when neither rpcuser nor
        rpcpassword is set. The config file is created owner-only and fsynced.
        """
        global_values = {"regtest": "1", "server": "1"}
        network_values = {
            "rpcbind": "127.0.0.1",
            "rpcallowip": "127.0.0.1",
            "rpcport": str(rpcport),
            "port": str(p2pport),
            "listen": "0",
            "connect": "0",
            "dnsseed": "0",
            "discover": "0",
            "upnp": "0",
            "txindex": "1",
            "blockfilterindex": "1",
            "coinstatsindex": "1",
            "fallbackfee": "0.0001",
        }
        config = datadir / "wam.conf"
        fd = os.open(config, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "w") as out:
                for k, v in global_values.items():
                    out.write(f"{k}={v}\n")
                out.write("[regtest]\n")
                for k, v in network_values.items():
                    out.write(f"{k}={v}\n")
                out.flush()
                os.fsync(out.fileno())
        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass
            raise

    def start(self) -> dict:
        """Start isolated Core and miner. Returns attachment spec."""
        self._datadir = private_temporary_directory(prefix='q04_miner_')
        self._rpc_port = _port()
        self._p2p_port = _port()
        self._write_cookie_config(self._datadir, self._rpc_port, self._p2p_port)

        node, cli, receipt = self._verified_core_paths(self._core_dir)

        # Start Core in non-daemon mode so we own the Popen.
        argv = [str(node), f'-datadir={self._datadir}', '-daemon=0']
        self._core_process = subprocess.Popen(
            argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)

        # Wait for RPC cookie to appear (cookie auth mode).
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

        # Create and load a disposable wallet before generating addresses.
        self._wallet_name = 'q04_fixture_' + secrets.token_hex(6)
        result = subprocess.run(
            [str(cli), f'-datadir={self._datadir}', '-regtest=1', 'createwallet', self._wallet_name],
            capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise Q04FixtureError('Q04_FIXTURE_WALLET_CREATE_FAILED')

        # Start a sustained solo-miner loop as a separate Python process.
        # It mines to the fixture wallet address periodically while Fusion observes.
        self._miner_process = subprocess.Popen(
            [sys.executable, '-m', 'wam_regtest.q04_miner_loop',
             '--cli', str(cli), '--datadir', str(self._datadir),
             '--wallet', self._wallet_name, '--interval', '5.0'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

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
            [str(cli), f'-datadir={self._datadir}', '-regtest=1',
             '-rpcwallet=' + self._wallet_name, 'getnewaddress'],
            capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise Q04FixtureError('Q04_FIXTURE_ADDRESS_FAILED')
        return result.stdout.strip()

    def mine_blocks(self, count: int = 1) -> dict:
        """Mine blocks without Fusion intervention; measure miner continuity."""
        if self._attachment is None:
            raise Q04FixtureError('Q04_FIXTURE_NOT_STARTED')
        before = self._attachment.read('getblockcount', [])
        node, cli, _ = self._verified_core_paths(self._core_dir)
        for _ in range(count):
            result = subprocess.run(
                [str(cli), f'-datadir={self._datadir}', '-regtest=1',
                 '-rpcwallet=' + self._wallet_name, 'generatetoaddress',
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
