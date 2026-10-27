"""Q04 genuine Core E2E: solo-miner coexistence and read-only attachment.

Run inside CI with a qualified Core directory. Produces q04-evidence.json with
runtime proofs (no secrets). Never uses synthetic RPC responses.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))

from wam_regtest.q04_runner import run_q04_scenario, Q04RunnerError


def _linux_setup_trust(core_dir: Path):
    """Configure the Linux explicit trust policy required by verified_core_paths."""
    if sys.platform != 'linux':
        return
    manifest_sha256 = None
    for path in [
        core_dir.parent / 'LINUX_DEVELOPER_CORE_MANIFEST_SHA256.txt',
        core_dir / 'LINUX_DEVELOPER_CORE_MANIFEST_SHA256.txt',
        core_dir / 'manifest.sha256',
    ]:
        if path.is_file():
            manifest_sha256 = path.read_text().strip()
            break
    if manifest_sha256 is None:
        raise Q04RunnerError('Q04_RUNNER_MANIFEST_SHA256_FILE_NOT_FOUND')
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'tests'))
    os.environ['WAM_ROOT_WITNESS_NATIVE_TESTS'] = '1'
    from test_linux_anchor_witness import NativeRootWitness
    NativeRootWitness.setUpClass()
    try:
        from wam_regtest.linux_runtime import configure
        configure(core_dir, manifest_sha256, NativeRootWitness.root / 'anchor.sock',
                  authorized=True)
    except Exception:
        NativeRootWitness.tearDownClass()
        raise
    return NativeRootWitness


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--core-dir', required=True, type=Path)
    parser.add_argument('--max-duration', type=int, default=120)
    parser.add_argument('--report', type=Path, default=Path('q04-evidence.json'))
    args = parser.parse_args()

    core_dir = args.core_dir.resolve()
    if not core_dir.is_absolute():
        raise Q04RunnerError('Q04_RUNNER_CORE_DIR_ABSOLUTE_REQUIRED')

    witness = None
    try:
        witness = _linux_setup_trust(core_dir)
        evidence = run_q04_scenario(core_dir, report_path=args.report,
                                    max_duration=args.max_duration)
        print('Q04_PASS ' + evidence['status'], flush=True)
    finally:
        if witness is not None:
            witness.tearDownClass()


if __name__ == '__main__':
    main()
