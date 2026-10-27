"""Reusable Q04 genuine Core E2E scenario.

Used by scripts/q04_miner_coexistence.py and by frozen wallet entry points.
Produces a redacted public evidence JSON; never emits credentials or paths.
"""
from __future__ import annotations

import json
import time
import sys
import os
from pathlib import Path

from .q04_fixture import SoloMinerFixture
from .rpc_contention import ContentionAwareRpc, RpcContentionError
from .external_recovery import ExternalCoreSession, ExternalRecoveryError, ReconnectPolicy
from .external_core import ExternalAttachmentError
from .telemetry import increment


class Q04RunnerError(RuntimeError):
    """Fixed redacted runner status."""


def run_q04_scenario(core_dir: Path, report_path: Path | None = None,
                     max_duration: int = 180, extra_config: dict | None = None) -> dict:
    """Run the canonical Q04 miner-coexistence scenario on a genuine Core.

    Returns the evidence dict and optionally writes it to report_path.
    """
    if type(core_dir) is not type(Path()) or not core_dir.is_absolute():
        raise Q04RunnerError('Q04_RUNNER_CORE_DIR_REQUIRED')

    config={'rpcworkqueue':'2','rpcthreads':'1', **(extra_config or {})}
    with SoloMinerFixture(core_dir, timeout=max_duration, extra_config=config) as fixture:
        spec = fixture.start()
        pid = spec['pid']
        rpc_port = spec['rpc_port']
        datadir = Path(spec['datadir'])

        # Scenario 1: Fusion read-only attachment and same-PID socket attestation.
        height_before = fixture.fusion_read('getblockcount', [])

        # Scenario 2: Continuous Fusion polling while miner operates independently.
        miner_heights = []
        for _ in range(5):
            time.sleep(3.0)
            h = fixture.fusion_read('getblockcount', [])
            miner_heights.append(h)
        if miner_heights[-1] <= miner_heights[0]:
            raise Q04RunnerError('Q04_RUNNER_MINER_DID_NOT_ADVANCE')

        # Scenario 3: Contention-aware read returns actual data (no busy coercion).
        aware = ContentionAwareRpc(
            fixture.fusion_read,
            ownership_attest_callable=lambda: True)
        try:
            current = aware.read('getblockcount', [])
        except RpcContentionError:
            current = None
        if current is None:
            raise Q04RunnerError('Q04_RUNNER_CONTENTION_READ_FAILED')

        # Scenario 4: Negative test — write method is refused at attachment boundary.
        try:
            fixture.fusion_read('sendrawtransaction', ['deadbeef'])
            raise Q04RunnerError('Q04_RUNNER_WRITE_SCOPE_NOT_DENIED')
        except ExternalAttachmentError as exc:
            if exc.args[0] != 'EXTERNAL_ATTACHMENT_READ_SCOPE_DENIED':
                raise Q04RunnerError('Q04_RUNNER_WRITE_SCOPE_WRONG_ERROR') from exc

        # Scenario 5: Reconnection after transient disconnect still re-attests identity.
        with ExternalCoreSession(
            authorize=lambda: {
                'pid': pid, 'rpc_port': rpc_port, 'datadir': str(datadir),
                'core_dir': str(core_dir), 'operator_consent': True,
            },
            policy=ReconnectPolicy(max_attempts=3, base_delay_seconds=0.5, max_delay_seconds=2.0),
        ) as session:
            try:
                reconn_height = session.read('getblockcount', [])
            except ExternalRecoveryError as exc:
                raise Q04RunnerError('Q04_RUNNER_RECONNECT_FAILED') from exc
            # Reset ONE real client TCP socket after connecting to the genuine
            # Core. No HTTP reply or RPC result is synthesized; recovery must
            # create and fully attest a fresh attachment to the same node.
            from . import external_core
            original_socket=external_core.socket.socket
            reset={'count':0}
            class ResetOnce(original_socket):
                def connect(self,address):
                    super().connect(address)
                    if address==('127.0.0.1',rpc_port) and reset['count']==0:
                        reset['count']+=1
                        import struct
                        linger=struct.pack('hh' if sys.platform=='win32' else 'ii',1,0)
                        self.setsockopt(external_core.socket.SOL_SOCKET,external_core.socket.SO_LINGER,linger)
                        self.close()
                        raise ConnectionResetError('fixture transport reset')
            previous=session._attachment
            try:
                external_core.socket.socket=ResetOnce
                reconn_height=session.read('getblockcount',[])
            finally:external_core.socket.socket=original_socket
            if reset['count']!=1 or session._attachment is previous:
                raise Q04RunnerError('Q04_RUNNER_RECONNECT_NOT_EXERCISED')
            if reconn_height < height_before:
                raise Q04RunnerError('Q04_RUNNER_RECONNECT_HEIGHT_REGRESSED')
            # Authorized fixture-operator fault, never a product attach action:
            # replace this disposable node's on-disk cookie while its genuine
            # server remains running. A reconnect must refuse before using it.
            cookie=datadir/'regtest'/'.cookie';original=cookie.read_bytes()
            replacement=b'__cookie__:'+b'0'*(len(original)-11)
            if replacement==original:replacement=b'__cookie__:'+b'1'*(len(original)-11)
            def fixture_cookie(data):
                with cookie.open('r+b') as out:
                    out.write(data);out.truncate();out.flush();os.fsync(out.fileno())
            try:
                fixture_cookie(replacement)
                session._attachment.close();session._attachment=None
                try:
                    session._reconnect()
                    raise Q04RunnerError('Q04_RUNNER_COOKIE_CHANGE_ADOPTED')
                except ExternalRecoveryError as error:
                    if error.args!=('EXTERNAL_RECOVERY_CREDENTIAL_CHANGED',):raise
            finally:fixture_cookie(original)
            try:
                session.read('getblockcount',[])
                raise Q04RunnerError('Q04_RUNNER_RESTORED_COOKIE_RESUMED')
            except ExternalRecoveryError as error:
                if error.args!=('EXTERNAL_RECOVERY_NEEDED',):raise

        # Scenario 6: Credential/port change detection — altered port must require new auth.
        bad_session = ExternalCoreSession(
            authorize=lambda: {
                'pid': pid, 'rpc_port': rpc_port + 1, 'datadir': str(datadir),
                'core_dir': str(core_dir), 'operator_consent': True,
            })
        bad_session._last_spec = {
            'pid': pid, 'rpc_port': rpc_port, 'datadir': str(datadir),
            'core_dir': str(core_dir), 'operator_consent': True,
        }
        try:
            bad_session.read('getblockcount', [])
            raise Q04RunnerError('Q04_RUNNER_PORT_CHANGE_NOT_DETECTED')
        except ExternalRecoveryError as exc:
            if exc.args[0] != 'EXTERNAL_RECOVERY_IDENTITY_CHANGED':
                raise Q04RunnerError('Q04_RUNNER_PORT_CHANGE_WRONG_ERROR') from exc

        from .q04_busy_probe import probe_busy
        import importlib.util
        genuine_busy=probe_busy(fixture,gui=importlib.util.find_spec('PySide6') is not None)
        receipt=fixture._attachment._receipt
        evidence = {
            'status': 'Q04_MINER_COEXISTENCE_PASS',
            'timestamp_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'platform': receipt['platform'],
            'core_sha256': {'wamd':receipt['wamd_sha256'],'wam-cli':receipt['wam_cli_sha256']},
            'wsp_source_commit':'ac55f13423620252bdbf848c7e8a280c3b84721e',
            'execution':'FROZEN' if getattr(sys,'frozen',False) else 'SOURCE_NATIVE',
            'genuine_busy':genuine_busy,
            'miner_driver':'sustained-thread-with-separate-Core-CLI-processes',
            'height_before': height_before,
            'miner_heights': miner_heights,
            'contention_read_height': current,
            'reconnect_height': reconn_height,
            'reconnect_real_tcp_reset_count':reset['count'],
            'reconnect_fresh_attachment':True,
            'changed_cookie_reconnect_denied_before_auth':True,
            'restored_cookie_still_requires_new_authorization':True,
            'credential_fault_actor':'disposable_fixture_operator',
            'write_denied': True,
            'port_change_detected': True,
            'synthetic_rpc': False,
        }

        if report_path is not None:
            report_path = Path(report_path)
            if report_path.exists() or not report_path.parent.is_dir():
                raise Q04RunnerError('Q04_RUNNER_REPORT_PATH_DENIED')
            report_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + '\n')

        increment('q04_runner_scenario_pass')
        return evidence
