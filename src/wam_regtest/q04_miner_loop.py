"""Sustained solo-miner loop for Q04 isolated REGTEST fixture.

This is a separate long-lived process that mines blocks periodically to an
address from its own fixture wallet. It is intentionally independent from the
Fusion wallet and only operates inside the disposable REGTEST datadir created by
SoloMinerFixture.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path


def _run(cli: Path, datadir: Path, wallet: str, method: str, params: list) -> dict:
    args = [str(cli), f'-datadir={datadir}', '-regtest=1', f'-rpcwallet={wallet}']
    if params:
        args += [method] + [str(p) for p in params]
    else:
        args.append(method)
    result = subprocess.run(args, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f'MINER_RPC_FAILED {method}')
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cli', required=True, type=Path)
    parser.add_argument('--datadir', required=True, type=Path)
    parser.add_argument('--wallet', required=True)
    parser.add_argument('--interval', type=float, default=5.0)
    parser.add_argument('--max-blocks', type=int, default=1000)
    args = parser.parse_args()

    # Create a new address once and mine to it repeatedly.
    address = _run(args.cli, args.datadir, args.wallet, 'getnewaddress', [])
    mined = 0
    while mined < args.max_blocks:
        try:
            _run(args.cli, args.datadir, args.wallet, 'generatetoaddress', [1, address])
            mined += 1
        except RuntimeError:
            # Core may be temporarily busy; keep trying until killed.
            pass
        time.sleep(args.interval)


if __name__ == '__main__':
    main()
