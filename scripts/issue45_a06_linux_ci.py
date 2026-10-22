"""Existing ephemeral Linux witness fixture for the isolated A06 CI job only."""
import argparse
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--core-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != 'linux':
        raise SystemExit('A06_LINUX_CI_REQUIRED')
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root/'tests'))
    from test_linux_anchor_witness import NativeRootWitness
    NativeRootWitness.setUpClass()
    try:
        result = subprocess.run([sys.executable,
            str(root/'scripts'/'issue45_a06_fresh_crash.py'),
            '--core-dir', str(args.core_dir.resolve()),
            '--wsp-source', str((root/'wsp-upstream').resolve()),
            '--linux-developer-manifest',
            'e77a5745263b8fdbcffdb282af22800b6f7805f033c09f00738e997150a0f806',
            '--linux-root-witness', str(NativeRootWitness.root/'anchor.sock'),
            '--confirm-disposable-regtest', '--output', str(args.output)],
            stdin=subprocess.DEVNULL)
        return result.returncode
    finally:
        NativeRootWitness.tearDownClass()


if __name__ == '__main__':
    raise SystemExit(main())
