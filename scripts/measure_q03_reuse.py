"""Genuine Core macOS measurement for Q03 persistent JSON-RPC reuse.

Launches the real signed v0.1.11 regtest Core, mines 101 public-fixture blocks,
creates a disposable WalletSession, then repeatedly refreshes the wallet read
snapshot while recording telemetry counters.

No mainnet, no real funds, no GUI. The temporary chain is stopped and deleted
before the script exits.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Ensure repository src/ is on path when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from wam_regtest.core import (
    _port,
    _read_cli,
    _write_private_config,
    CoreSmokeError,
    verified_core_paths,
)
from wam_regtest.rpc_scope import register, unregister
from wam_regtest.telemetry import reset as reset_telemetry, snapshot as telemetry_snapshot
from wam_regtest.wallet_session import WalletSession
from wam_regtest.wsp_live import public_regtest_mining_address, scan_actual_core_blocks


def wait_for_chain(prefix: list[str], proc: subprocess.Popen, timeout: float = 90.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise CoreSmokeError("CORE_MEASURE_EARLY_EXIT")
        try:
            info = _read_cli(prefix + ["getblockchaininfo"], timeout=3)
            if isinstance(info, dict) and info.get("chain") == "regtest":
                return
        except CoreSmokeError:
            pass
        time.sleep(0.2)
    raise CoreSmokeError("CORE_MEASURE_START_TIMEOUT")


def measure_reuse(core_dir: Path, source_root: Path, cycles: int = 5) -> dict:
    node, cli, receipt = verified_core_paths(core_dir)
    node_sha256 = receipt["wamd_sha256"]
    with tempfile.TemporaryDirectory(prefix="wam-q03-measure-") as temp:
        datadir = Path(temp).resolve(strict=True)
        datadir.chmod(0o700)
        rpc_port, peer_port = _port(), _port()
        if rpc_port == peer_port:
            raise CoreSmokeError("CORE_MEASURE_PORT_COLLISION")
        _write_private_config(datadir, rpc_port, peer_port)
        env = {
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "HOME": str(datadir),
            "LC_ALL": "C",
        }
        prefix = [str(cli), f"-datadir={datadir}"]
        proc = None
        keychain = datadir / "q03-measure.keychain-db"
        created_keychain = False
        try:
            with (datadir / "core-output.log").open("xb") as log:
                proc = subprocess.Popen(
                    [str(node), f"-datadir={datadir}", "-daemon=0"],
                    cwd=datadir,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
            register(proc, core_dir, datadir, authorized_disposable_mutation=True)
            wait_for_chain(prefix, proc)
            if _read_cli(prefix + ["getconnectioncount"]) != 0:
                raise CoreSmokeError("CORE_MEASURE_EXTERNAL_PEERS")
            mining = public_regtest_mining_address(source_root)
            mined = _read_cli(prefix + ["generatetoaddress", "101", mining], timeout=90)
            if not isinstance(mined, list) or len(mined) != 101:
                raise CoreSmokeError("CORE_MEASURE_GENERATE_DENIED")

            # Bring the chain to height 102 with a real BIP352 fixture payment.
            scan_actual_core_blocks(
                cli, datadir, source_root, expected_height=101,
                payment_e2e=True, mining_address=mining,
            )

            if sys.platform == "darwin":
                status = subprocess.run(
                    ["/usr/bin/security", "create-keychain", "-p", "public-test-only", str(keychain)],
                    capture_output=True, timeout=15, check=False,
                ).returncode
                if status:
                    raise CoreSmokeError("CORE_MEASURE_KEYCHAIN_DENIED")
                created_keychain = True
            else:
                keychain = None

            password = b"public-disposable-q03-measure"
            # WalletSession.create brings the chain to height 103 and funds the wallet.
            session = WalletSession.create(
                core_dir, datadir, source_root, password, mining,
                authorized=True, keychain=keychain,
            )
            initial = session.snapshot()

            # Record counters right after session creation, then reset so the
            # measurement covers only repeated read reuse.
            telemetry_before_repeated_reads = telemetry_snapshot()
            reset_telemetry()
            baseline = telemetry_snapshot()
            measurements = []
            for i in range(cycles):
                snap = session.snapshot()
                measurements.append({
                    "cycle": i + 1,
                    "height": snap.height,
                    "confirmed_utxos": snap.confirmed_utxos,
                    "confirmed_atoms": snap.confirmed_atoms,
                    "telemetry": telemetry_snapshot(),
                })
            final = telemetry_snapshot()
            delta = {k: final[k] - baseline.get(k, 0) for k in final}
            return {
                "status": "Q03_REUSE_MEASURED",
                "platform": receipt.get("platform"),
                "node_sha256": node_sha256,
                "initial_height": initial.height,
                "initial_confirmed_utxos": initial.confirmed_utxos,
                "initial_confirmed_atoms": initial.confirmed_atoms,
                "cycles": cycles,
                "per_cycle": measurements,
                "telemetry_before_repeated_reads": telemetry_before_repeated_reads,
                "delta": delta,
                "averages": {
                    "http_requests_per_cycle": delta["http_request"] / cycles if cycles else None,
                    "cli_spawns_per_cycle": delta["cli_spawn"] / cycles if cycles else None,
                },
            }
        finally:
            if proc is not None:
                if proc.poll() is None:
                    try:
                        _read_cli(prefix + ["stop"], timeout=8)
                    except CoreSmokeError:
                        pass
                    try:
                        proc.wait(timeout=12)
                    except subprocess.TimeoutExpired:
                        proc.terminate()
                        try:
                            proc.wait(timeout=6)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                            proc.wait(timeout=6)
            unregister(datadir)
            if created_keychain and keychain.exists():
                subprocess.run(
                    ["/usr/bin/security", "delete-keychain", str(keychain)],
                    capture_output=True, timeout=15, check=False,
                )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure Q03 persistent RPC reuse on genuine Core")
    parser.add_argument("--core-dir", type=Path, default=Path("core-macos-arm64").resolve())
    parser.add_argument("--wsp-source", type=Path, default=Path("wsp-upstream").resolve())
    parser.add_argument("--cycles", type=int, default=5)
    args = parser.parse_args(argv)
    result = measure_reuse(args.core_dir.resolve(), args.wsp_source.resolve(), args.cycles)
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
