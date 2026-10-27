"""Q04 RPC contention qualification on a genuine Core attachment.

Produces q04-contention-evidence.json proving the ContentionAwareRpc layer
behaves correctly when the external Core reports busy (HTTP 503 / RPC_NODE_BUSY).

The script first attempts to trigger genuine Core queue saturation by flooding
the RPC port with concurrent requests while a small rpcworkqueue is configured.
If the real Core does not return 503 under this load, the same attachment path
is exercised with a controlled busy-signal shim so that backoff, coalescing and
non-retry properties are still verified against real attachment code. The
ledger evidence always records whether a genuine 503 was observed.
"""
from __future__ import annotations

import argparse
import base64
import concurrent.futures
import http.client
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))

from wam_regtest.q04_fixture import SoloMinerFixture, Q04FixtureError
from wam_regtest.rpc_contention import ContentionAwareRpc, BackoffPolicy, RpcContentionError
from wam_regtest.external_core import ExternalAttachmentError


def _fail(message: str):
    print(f'Q04_CONTENTION_FAIL {message}', flush=True)
    raise SystemExit(1)


def _ok(result: dict):
    evidence = {
        'status': 'Q04_CONTENTION_PASS',
        'timestamp_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'synthetic_rpc': False,
        **result,
    }
    Path('q04-contention-evidence.json').write_text(json.dumps(evidence, indent=2, sort_keys=True))
    print('Q04_CONTENTION_PASS ' + json.dumps(evidence, sort_keys=True), flush=True)
    return evidence


def _linux_setup_trust(core_dir: Path):
    if sys.platform != 'linux':
        return None
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'tests'))
    os.environ['WAM_ROOT_WITNESS_NATIVE_TESTS'] = '1'
    from test_linux_anchor_witness import NativeRootWitness
    NativeRootWitness.setUpClass()
    manifest_candidates = [
        core_dir.parent / 'LINUX_DEVELOPER_CORE_MANIFEST_SHA256.txt',
        core_dir / 'LINUX_DEVELOPER_CORE_MANIFEST_SHA256.txt',
        core_dir / 'manifest.sha256',
    ]
    manifest_sha256 = None
    for path in manifest_candidates:
        if path.is_file():
            manifest_sha256 = path.read_text().strip()
            break
    if manifest_sha256 is None:
        raise Q04FixtureError('MANIFEST_SHA256_FILE_NOT_FOUND')
    try:
        from wam_regtest.linux_runtime import configure
        configure(core_dir, manifest_sha256, NativeRootWitness.root / 'anchor.sock', authorized=True)
    except Exception:
        NativeRootWitness.tearDownClass()
        raise
    return NativeRootWitness


def _read_cookie(datadir: Path) -> str:
    raw = (datadir / 'regtest' / '.cookie').read_bytes()
    return base64.b64encode(raw).decode('ascii')


def _raw_rpc(rpc_port: int, auth: str, method: str, params: list, timeout: float = 10.0) -> tuple:
    """Return (http_status, body_bytes). Caller handles parsing."""
    body = json.dumps({'jsonrpc': '1.0', 'id': 1, 'method': method, 'params': params}, ensure_ascii=True).encode('utf8')
    headers = {'Authorization': f'Basic {auth}', 'Content-Type': 'application/json'}
    conn = http.client.HTTPConnection('127.0.0.1', rpc_port, timeout=timeout)
    try:
        conn.request('POST', '/', body, headers)
        response = conn.getresponse()
        status = response.status
        data = response.read(2 * 1024 * 1024)
    finally:
        conn.close()
    return status, data


def _attempt_genuine_503(rpc_port: int, auth: str, duration_seconds: float = 8.0) -> tuple[bool, int]:
    """Flood Core with concurrent RPC calls; return (observed_503, total_requests)."""
    observed_503 = False
    total = 0
    deadline = time.monotonic() + duration_seconds

    def flood_once(_):
        nonlocal observed_503, total
        try:
            status, _ = _raw_rpc(rpc_port, auth, 'getblockchaininfo', [], timeout=2.0)
            if status == 503:
                observed_503 = True
            total += 1
        except Exception:
            pass

    with concurrent.futures.ThreadPoolExecutor(max_workers=64) as pool:
        while time.monotonic() < deadline and not observed_503:
            futures = [pool.submit(flood_once, i) for i in range(128)]
            concurrent.futures.wait(futures, timeout=1.0)
    return observed_503, total


def _measure_backoff_on_injected_busy(read_callable, policy: BackoffPolicy):
    """Return (delays, calls_made) for a ContentionAwareRpc retrying on busy."""
    # The shim lets the first N attempts fail with busy, then succeeds.
    state = {'busy_remaining': policy.max_retries, 'calls': 0}

    def shim(method, params):
        state['calls'] += 1
        if state['busy_remaining'] > 0:
            state['busy_remaining'] -= 1
            raise ExternalAttachmentError('EXTERNAL_ATTACHMENT_RPC_NODE_BUSY')
        return read_callable(method, params)

    rpc = ContentionAwareRpc(shim, policy=policy)
    start = time.monotonic()
    delays = []
    last = start
    try:
        rpc.read('getblockcount', [])
    except RpcContentionError:
        pass
    # Measure intervals between attempts via shim is hard; instead measure
    # elapsed time for the whole call and assert it is >= sum of min delays.
    elapsed = time.monotonic() - start
    return elapsed, state['calls']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--core-dir', required=True, type=Path)
    parser.add_argument('--max-duration', type=int, default=120)
    parser.add_argument('--force-injected-busy', action='store_true',
                        help='Skip genuine saturation attempt and use controlled busy injection only')
    args = parser.parse_args()

    core_dir = args.core_dir.resolve()
    if not core_dir.is_absolute():
        _fail('CORE_DIR_ABSOLUTE_REQUIRED')

    witness = None
    try:
        witness = _linux_setup_trust(core_dir)
        # Small work queue makes 503 more reproducible; single thread serializes.
        fixture = SoloMinerFixture(core_dir, timeout=args.max_duration,
                                   extra_config={'rpcworkqueue': '2', 'rpcthreads': '1'})
        with fixture:
            spec = fixture.start()
            pid = spec['pid']
            rpc_port = spec['rpc_port']
            datadir = Path(spec['datadir'])
            auth = _read_cookie(datadir)

            # Baseline height through the contention-aware wrapper.
            base_policy = BackoffPolicy(base_seconds=0.25, max_seconds=2.0, max_retries=2, jitter=0.1)
            aware = ContentionAwareRpc(fixture.fusion_read, policy=base_policy)
            baseline = aware.read('getblockcount', [])

            # 1) Genuine Core queue saturation attempt.
            observed_503 = False
            flood_total = 0
            if not args.force_injected_busy:
                observed_503, flood_total = _attempt_genuine_503(rpc_port, auth)

            # 2) Controlled busy injection on the real attachment path.
            #    This verifies backoff, retry, coalescing and no-write-retry
            #    deterministically regardless of whether Core produced 503.
            test_policy = BackoffPolicy(base_seconds=0.1, max_seconds=1.0, max_retries=3, jitter=0.1)

            # Backoff: busy remaining == max_retries; call should succeed after retries.
            shim_state = {'busy_remaining': test_policy.max_retries, 'calls': 0}

            def backoff_shim(method, params):
                shim_state['calls'] += 1
                if shim_state['busy_remaining'] > 0:
                    shim_state['busy_remaining'] -= 1
                    raise ExternalAttachmentError('EXTERNAL_ATTACHMENT_RPC_NODE_BUSY')
                return fixture.fusion_read(method, params)

            backoff_rpc = ContentionAwareRpc(backoff_shim, policy=test_policy)
            backoff_start = time.monotonic()
            backoff_result = backoff_rpc.read('getblockcount', [])
            backoff_elapsed = time.monotonic() - backoff_start
            min_expected = sum(test_policy.delay(i) * 0.75 for i in range(test_policy.max_retries))
            if backoff_elapsed < min_expected:
                _fail('BACKOFF_DELAYS_TOO_SHORT')
            if backoff_result < baseline:
                _fail('BACKOFF_HEIGHT_REGRESSED')

            # Coalescing: mark busy, then status/read must return busy without hitting Core.
            coalesce_rpc = ContentionAwareRpc(fixture.fusion_read, policy=test_policy)
            coalesce_state = {'calls': 0}

            def coalesce_shim(method, params):
                coalesce_state['calls'] += 1
                raise ExternalAttachmentError('EXTERNAL_ATTACHMENT_RPC_NODE_BUSY')

            coalesce_rpc._read = coalesce_shim
            try:
                coalesce_rpc.read('getblockcount', [])
                _fail('COALESCE_DID_NOT_BUSY')
            except RpcContentionError as exc:
                if exc.args[0] != 'RPC_NODE_BUSY':
                    _fail('COALESCE_WRONG_ERROR')
            if coalesce_state['calls'] != test_policy.max_retries + 1:
                _fail('COALESCE_RETRY_COUNT_MISMATCH')
            # Second call while coalescer is hot must not invoke the shim.
            coalesce_state['calls'] = 0
            try:
                coalesce_rpc.read('getblockcount', [])
                _fail('COALESCE_DID_NOT_STAY_BUSY')
            except RpcContentionError:
                pass
            if coalesce_state['calls'] != 0:
                _fail('COALESCE_DID_NOT_SUPPRESS_CALL')
            status = coalesce_rpc.status()
            if not status.get('busy'):
                _fail('COALESCE_STATUS_NOT_BUSY')

            # No-write-retry: write method must be refused immediately.
            write_rpc = ContentionAwareRpc(fixture.fusion_read, policy=test_policy)
            write_state = {'calls': 0}

            def write_shim(method, params):
                write_state['calls'] += 1
                return fixture.fusion_read(method, params)

            write_rpc._read = write_shim
            try:
                write_rpc.read('sendrawtransaction', ['deadbeef'])
                _fail('WRITE_NOT_DENIED')
            except ExternalAttachmentError as exc:
                if exc.args[0] != 'EXTERNAL_ATTACHMENT_READ_SCOPE_DENIED':
                    _fail('WRITE_WRONG_ERROR')
            if write_state['calls'] != 1:
                _fail('WRITE_WAS_RETRIED')

            # Recovery after busy: reset coalescer and read real data.
            reset_rpc = ContentionAwareRpc(fixture.fusion_read, policy=test_policy)
            reset_state = {'busy_remaining': 1, 'calls': 0}

            def reset_shim(method, params):
                reset_state['calls'] += 1
                if reset_state['busy_remaining'] > 0:
                    reset_state['busy_remaining'] -= 1
                    raise ExternalAttachmentError('EXTERNAL_ATTACHMENT_RPC_NODE_BUSY')
                return fixture.fusion_read(method, params)

            reset_rpc._read = reset_shim
            try:
                reset_rpc.read('getblockcount', [])
            except RpcContentionError:
                pass
            reset_rpc.reset()
            recovery_height = reset_rpc.read('getblockcount', [])
            if recovery_height < baseline:
                _fail('RECOVERY_HEIGHT_REGRESSED')

            _ok({
                'core_dir': str(core_dir),
                'fixture_pid': pid,
                'rpc_port': rpc_port,
                'baseline_height': baseline,
                'observed_503': observed_503,
                'flood_requests': flood_total,
                'backoff_elapsed_seconds': round(backoff_elapsed, 3),
                'backoff_min_expected_seconds': round(min_expected, 3),
                'backoff_calls': shim_state['calls'],
                'coalesce_suppressed_call': True,
                'write_denied': True,
                'write_retried': False,
                'recovery_height': recovery_height,
            })
    finally:
        if witness is not None:
            witness.tearDownClass()


if __name__ == '__main__':
    main()
