"""One bounded genuine-Core Stage A lifecycle, never wallet/frozen acceptance."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
import time

from wam_regtest.core import verified_core_paths
from wam_regtest.probe_source import verify_source
from wam_regtest.custody import create_directory
from wam_regtest.supervisor_client import control
from wam_regtest.supervisor_store import read_exact
from wam_regtest.wsp_live import PINNED_WSP_COMMIT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--core-dir', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--confirm-disposable-regtest', action='store_true')
    args = parser.parse_args()
    if (not args.confirm_disposable_regtest or sys.platform != 'darwin'
            or platform.machine() != 'arm64' or args.root.exists()
            or args.root.is_symlink() or args.receipt.exists()):
        raise SystemExit('Q05_NATIVE_PROBE_SCOPE_DENIED')
    source = Path(__file__).resolve().parents[1]
    # Use the existing exact literal-source attestation shared by Q05 probes.
    # CI may create untracked receipts; modified or added Python code still denies.
    proof = verify_source(source)
    head = proof['candidate_source_sha']
    node, cli, intake = verified_core_paths(args.core_dir)
    receipt = dict(schema='q05-stage-a-native-lifecycle/v1', source_sha=head,
        checkout_sha=proof['checkout_sha'], platform='macos-arm64', core_version='v0.1.11',
        python_version=platform.python_version(),
        command=['python3.12','scripts/probe_q05_macos_lifecycle.py',
                 '--core-dir','<verified signed Core>','--root','<new isolated profile>',
                 '--receipt','<new receipt>','--confirm-disposable-regtest'],
        core_trust='official-signed-v0.1.11', wsp_source_commit=PINNED_WSP_COMMIT,
        wsp_execution=False, synthetic_rpc=False, frozen=False,
        mainnet_allowed=False, core_intake=intake,
        core_sha256={p.name: sha256(p.read_bytes()).hexdigest() for p in (node, cli)},
        source_files={p: sha256((source/p).read_bytes()).hexdigest() for p in (
            'src/wam_regtest/core_supervisor.py', 'src/wam_regtest/supervisor_protocol.py',
            'src/wam_regtest/supervisor_journal.py',
            'src/wam_regtest/supervisor_identity.py',
            'src/wam_regtest/supervisor_client.py', 'scripts/probe_q05_macos_lifecycle.py')},
        observations=[], status='FAIL')
    owner = None
    running = False
    root = args.root
    env = {'PATH': '/usr/bin:/bin:/usr/sbin:/sbin', 'LC_ALL': 'C',
           'HOME': str(root), 'PYTHONPATH': str(source/'src'), 'PYTHONDONTWRITEBYTECODE': '1'}

    def spawn_owner():
        return subprocess.Popen([sys.executable, '-m', 'wam_regtest.supervisor_cli',
            'serve', '--root', str(root), '--core-dir', str(args.core_dir),
            '--confirm-regtest-managed-core'], cwd=source, env=env,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True)

    def end_stopped_owner():
        # Only our exact Python child after authenticated owned Core shutdown.
        control(root,'release',authorized=True,timeout=3)
        owner.wait(timeout=5)
        if owner.returncode != 0:
            raise ValueError('Q05_OWNER_EXIT_DENIED')

    try:
        create_directory(root)
        owner = spawn_owner()
        deadline = time.monotonic()+10
        while not (root/'supervisor.profile').exists():
            if owner.poll() is not None or time.monotonic() >= deadline:
                raise ValueError('Q05_OWNER_START_DENIED')
            time.sleep(.05)
        profile = read_exact(root, 'supervisor.profile')
        config = (root/'chain'/'wam.conf').read_bytes()
        chain_stat = (root/'chain').stat()
        receipt['profile_id'] = json.loads(profile)['profile_id']
        receipt['profile_sha256'] = sha256(profile).hexdigest()
        receipt['config_sha256'] = sha256(config).hexdigest()
        receipt['datadir_identity'] = [chain_stat.st_dev, chain_stat.st_ino]
        result = control(root, 'start', authorized=True, timeout=120)
        running = True
        if not result['core_process_owned'] or result['state'] not in ('ready', 'syncing'):
            raise ValueError('Q05_CORE_START_DENIED')
        receipt['observations'].append({'authenticated_start': result,
            'ownership_proof': 'OwnedCoreBinding actual Popen, image metadata and kernel socket before HTTP auth'})
        status = control(root)
        if status['height'] != result['height'] or not status['core_process_owned']:
            raise ValueError('Q05_STATUS_CONTINUITY_DENIED')
        # Drop a genuine control connection after its server-authenticated hello.
        with socket.create_connection(('127.0.0.1', json.loads(profile)['control_port']), timeout=3) as conn:
            conn.recv(512)
        after_disconnect = control(root)
        if not after_disconnect['core_process_owned']:
            raise ValueError('Q05_DISCONNECT_STOPPED_CORE')
        receipt['observations'].append({'client_disconnect_core_continues': after_disconnect})
        stopped = control(root, 'shutdown', authorized=True, timeout=40)
        if stopped['state'] != 'stopped' or stopped['core_process_owned']:
            raise ValueError('Q05_SHUTDOWN_DENIED')
        running = False
        receipt['observations'].append({'authenticated_shutdown': stopped})
        end_stopped_owner()
        owner = spawn_owner()
        # Existing profile is immutable: readiness is checked by authenticated
        # status, not profile existence. Bounded pre-request connect readiness.
        deadline = time.monotonic()+5
        port = json.loads(profile)['control_port']
        while True:
            if owner.poll() is not None or time.monotonic() >= deadline:
                raise ValueError('Q05_REOPEN_DENIED')
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=.2): pass
                break
            except ConnectionRefusedError: time.sleep(.05)
        reopened = control(root)
        current = (root/'chain').stat()
        if (reopened['state'] != 'stopped' or reopened['core_process_owned']
                or read_exact(root, 'supervisor.profile') != profile
                or (root/'chain'/'wam.conf').read_bytes() != config
                or [current.st_dev, current.st_ino] != receipt['datadir_identity']
                or not (root/'chain'/'regtest'/'blocks').is_dir()):
            raise ValueError('Q05_REOPEN_IDENTITY_DENIED')
        receipt['observations'].append({'supervisor_reopen_same_profile_datadir': reopened})
        end_stopped_owner()
        receipt['status'] = 'PASS'
    except Exception as error:
        code = error.args[0] if error.args else ''
        receipt['failure'] = code if isinstance(code, str) and code.startswith(('Q05_', 'RPC_', 'CORE_', 'MANAGED_')) else 'Q05_NATIVE_PROBE_FAILED'
        receipt['owner_pid_for_manual_review'] = owner.pid if owner is not None else None
        try:
            # Native private file, fixed allowlisted codes only, no traceback,
            # args, config, cookie or control secrets enter a public receipt.
            diagnostic=json.loads(read_exact(root,'supervisor.failure').decode('ascii'))
            from wam_regtest.core_supervisor import DIAGNOSTIC_CODES
            if (set(diagnostic)=={'stage','code'} and diagnostic['stage'] in ('start','recover-stop')
                    and diagnostic['code'] in DIAGNOSTIC_CODES|{'MANAGED_UNCLASSIFIED_FAILURE'}):
                receipt['private_failure_diagnostic']=diagnostic
        except (ValueError,OSError):pass
        # Never kill unknown/unverified Core, guess a PID or silently retry a
        # failed native lifecycle. Preserve this profile and report the blocker.
    finally:
        receipt['timestamp_utc'] = datetime.now(timezone.utc).isoformat()
        receipt['core_shutdown_confirmed'] = not running and receipt['status']=='PASS'
        with args.receipt.open('x') as stream:
            json.dump(receipt, stream, indent=2);stream.write('\n')
    print(json.dumps({'status':receipt['status'], 'source_sha':head,
                      'observations':len(receipt['observations'])}))
    return 0 if receipt['status']=='PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
