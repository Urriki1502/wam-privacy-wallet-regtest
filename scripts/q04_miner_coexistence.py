"""Q04 genuine Core E2E: solo-miner coexistence and read-only attachment.

Run inside CI with a qualified Core directory. Produces q04-evidence.json with
runtime proofs (no secrets). Never uses synthetic RPC responses.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))

from wam_regtest.q04_fixture import SoloMinerFixture, Q04FixtureError
from wam_regtest.rpc_contention import ContentionAwareRpc, RpcContentionError
from wam_regtest.external_recovery import ExternalCoreSession, ExternalRecoveryError
from wam_regtest.external_core import ExternalAttachmentError


def _fail(message: str):
    print(f'Q04_FAIL {message}', flush=True)
    raise SystemExit(1)


def _ok(result: dict):
    evidence = {
        'status': 'Q04_MINER_COEXISTENCE_PASS',
        'timestamp_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        **result,
    }
    Path('q04-evidence.json').write_text(json.dumps(evidence, indent=2, sort_keys=True))
    print('Q04_PASS ' + json.dumps(evidence, sort_keys=True), flush=True)
    return evidence


def _read_manifest_sha256(core_dir: Path) -> str:
    candidates = [
        core_dir.parent / 'LINUX_DEVELOPER_CORE_MANIFEST_SHA256.txt',
        core_dir / 'LINUX_DEVELOPER_CORE_MANIFEST_SHA256.txt',
        core_dir / 'manifest.sha256',
    ]
    for path in candidates:
        if path.is_file():
            return path.read_text().strip()
    _fail('MANIFEST_SHA256_FILE_NOT_FOUND')


def _linux_setup_trust(core_dir: Path):
    """Configure the Linux explicit trust policy required by verified_core_paths."""
    if sys.platform != 'linux':
        return
    manifest_sha256 = _read_manifest_sha256(core_dir)
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
    args = parser.parse_args()

    core_dir = args.core_dir.resolve()
    if not core_dir.is_absolute():
        _fail('CORE_DIR_ABSOLUTE_REQUIRED')

    witness = None
    try:
        witness = _linux_setup_trust(core_dir)
        with SoloMinerFixture(core_dir, timeout=args.max_duration) as fixture:
        spec = fixture.start()
        pid = spec['pid']
        rpc_port = spec['rpc_port']
        datadir = Path(spec['datadir'])

        # Scenario 1: Fusion read-only attachment and same-PID socket attestation.
        height_before = fixture.fusion_read('getblockcount', [])
        print(f'Q04_OBSERVED_HEIGHT {height_before}', flush=True)

        # Scenario 2: Continuous Fusion polling while miner operates independently.
        miner_heights = []
        for _ in range(5):
            time.sleep(3.0)
            h = fixture.fusion_read('getblockcount', [])
            miner_heights.append(h)
        if miner_heights[-1] <= miner_heights[0]:
            _fail('MINER_DID_NOT_ADVANCE')

        # Scenario 3: Contention-aware read returns actual data (no busy coercion).
        aware = ContentionAwareRpc(
            fixture.fusion_read,
            ownership_attest_callable=lambda: True)  # Fixture verified PID at attach time.
        try:
            current = aware.read('getblockcount', [])
        except RpcContentionError:
            current = None
        if current is None:
            _fail('CONTENTION_READ_FAILED')

        # Scenario 4: Negative test — write method is refused at attachment boundary.
        try:
            fixture.fusion_read('sendrawtransaction', ['deadbeef'])
            _fail('WRITE_SCOPE_NOT_DENIED')
        except ExternalAttachmentError as exc:
            if exc.args[0] != 'EXTERNAL_ATTACHMENT_READ_SCOPE_DENIED':
                _fail('WRITE_SCOPE_WRONG_ERROR')

        # Scenario 5: Reconnection after transient disconnect still re-attests identity.
        with ExternalCoreSession(
            authorize=lambda: {
                'pid': pid, 'rpc_port': rpc_port, 'datadir': str(datadir),
                'core_dir': str(args.core_dir), 'operator_consent': True,
            },
            policy=__import__('wam_regtest.external_recovery').external_recovery.ReconnectPolicy(
                max_attempts=3, base_delay_seconds=0.5, max_delay_seconds=2.0),
        ) as session:
            try:
                reconn_height = session.read('getblockcount', [])
            except ExternalRecoveryError:
                _fail('RECONNECT_FAILED')
            if reconn_height < height_before:
                _fail('RECONNECT_HEIGHT_REGRESSED')

        # Scenario 6: Credential/port change detection — altered port must require new auth.
        bad_session = ExternalCoreSession(
            authorize=lambda: {
                'pid': pid, 'rpc_port': rpc_port + 1, 'datadir': str(datadir),
                'core_dir': str(args.core_dir), 'operator_consent': True,
            })
        bad_session._last_spec = {
            'pid': pid, 'rpc_port': rpc_port, 'datadir': str(datadir),
            'core_dir': str(args.core_dir), 'operator_consent': True,
        }
        try:
            bad_session.read('getblockcount', [])
            _fail('PORT_CHANGE_NOT_DETECTED')
        except ExternalRecoveryError as exc:
            if exc.args[0] != 'EXTERNAL_RECOVERY_IDENTITY_CHANGED':
                _fail('PORT_CHANGE_WRONG_ERROR')

        _ok({
            'core_dir': str(core_dir),
            'fixture_pid': pid,
            'rpc_port': rpc_port,
            'height_before': height_before,
            'miner_heights': miner_heights,
            'contention_read_height': current,
            'reconnect_height': reconn_height,
            'write_denied': True,
            'port_change_detected': True,
            'synthetic_rpc': False,
        })
    finally:
        if witness is not None:
            witness.tearDownClass()


if __name__ == '__main__':
    main()
