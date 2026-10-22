"""A06 native Core continuity gate; no wallet, recovery mutation or mock RPC.

Mine only in a newly created disposable REGTEST datadir. Kill only our own
Popen after native image/RPC ownership verification. Publish sanitized facts
after verified cleanup, then FAIL if the original fresh tip is unavailable.
This is source/native evidence, never frozen, physical or independent review.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time

from wam_regtest.build_provenance import capture, verify, public_receipt
from wam_regtest.core import _read_cli, verified_core_paths
from wam_regtest.core_supervisor import CoreSupervisor
from wam_regtest.json_rpc import _private_config
from wam_regtest.supervisor_protocol import PROTOCOL, request_proof
from wam_regtest.supervisor_store import read_exact
from wam_regtest.wsp_live import public_regtest_mining_address


def _digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def _blocks(directory):
    result = {}
    for path in sorted((directory/'regtest'/'blocks').glob('blk*.dat')):
        info = path.lstat()
        if path.is_symlink() or not path.is_file() or info.st_size > 128*1024*1024:
            raise AssertionError('A06_BLOCK_FILE_SHAPE_DENIED')
        result[path.name] = {'bytes': info.st_size, 'sha256': _digest(path)}
    if not result:
        raise AssertionError('A06_BLOCK_FILE_MISSING_BEFORE_CRASH')
    return result


def _header(cli, directory, tip):
    # Independent exact-pinned CLI is an audit witness, not a wallet fallback.
    reply = subprocess.run([str(cli), f'-datadir={directory}',
        'getblockheader', tip, 'false'], stdin=subprocess.DEVNULL,
        capture_output=True, timeout=15,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
    if reply.returncode == 0:
        raw = reply.stdout.decode('ascii').strip()
        if not re.fullmatch('[0-9a-f]{160}', raw):
            raise AssertionError('A06_HEADER_RESPONSE_SHAPE_DENIED')
        return {'rpc_success': True,
                'header_sha256': hashlib.sha256(bytes.fromhex(raw)).hexdigest()}
    # Never publish arbitrary stderr, Core logs, credentials or private paths.
    return {'rpc_success': False, 'exit_code': reply.returncode,
            'block_not_found': b'Block not found' in reply.stderr,
            'rpc_error_code_minus5': b'error code: -5' in reply.stderr}


def prove(core, wsp, *, authorized=False, linux_manifest=None,
          linux_witness=None):
    if authorized is not True or not core.is_absolute() or not wsp.is_absolute():
        raise ValueError('A06_DISPOSABLE_REGTEST_CONSENT_REQUIRED')
    source_root = Path(__file__).resolve().parents[1]
    source = capture(source_root)
    evidence = {
        'schema': 'wam-a06-native-fresh-core-crash/v1',
        'started_at_utc': datetime.now(timezone.utc).isoformat(),
        'test_source_provenance': public_receipt(source,
            source_head=os.environ.get('WAM_SOURCE_HEAD'),
            dispatch=os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch'),
        'network': 'regtest', 'core_version': 'v0.1.11',
        'wsp_source_commit': 'ac55f13423620252bdbf848c7e8a280c3b84721e',
        'synthetic_rpc': False, 'mainnet_allowed': False,
        'wallet_keys_used': False, 'wallet_anchor_used': False,
        'frozen': False, 'physical_accepted': False, 'dev_reviewed': False,
        'clean_stop_before_crash': False, 'reindex_performed': False,
        'recovery_mutation_performed': False, 'automatic_payment_retry': False,
        'cleanup_verified': False, 'status': 'RUNNING',
    }
    owner = None
    processes = []
    temporary = None
    try:
        if sys.platform == 'linux':
            if linux_manifest is None or linux_witness is None:
                raise ValueError('A06_LINUX_EXISTING_WITNESS_REQUIRED')
            # Existing native CI witness only; no service provisioning here.
            from wam_regtest.linux_runtime import configure
            configure(core, linux_manifest, linux_witness, authorized=True)
        node, cli, receipt = verified_core_paths(core)
        evidence.update(platform=receipt['platform'],
            official_signed_release=receipt['platform'] != 'linux-x86_64',
            wamd_sha256=receipt['wamd_sha256'],
            wam_cli_sha256=receipt['wam_cli_sha256'])
        if sys.platform == 'linux':
            evidence['linux_developer_manifest_sha256'] = linux_manifest
            evidence['existing_root_witness_verified'] = True
        mine = public_regtest_mining_address(wsp)
        temporary = Path(tempfile.mkdtemp(prefix='wam-a06-core-crash-')).resolve()
        root = temporary/'wam-fusion-core-0123456789abcdef'
        if sys.platform == 'win32':
            from wam_regtest.custody import create_directory
            create_directory(root)
        else:
            root.mkdir(mode=0o700)
        owner = CoreSupervisor(root, core, authorized=True)
        owner.start()
        processes.append(owner.process)
        mined = _read_cli([str(cli), f'-datadir={owner.directory}',
                          'generatetoaddress', '101', mine], timeout=90)
        if len(mined) != 101 or owner.read.call('getblockcount', []) != 101:
            raise AssertionError('A06_MINED_HEIGHT_UNVERIFIED')
        tip = owner.read.call('getbestblockhash', [])
        before_header = _header(cli, owner.directory, tip)
        if not before_header['rpc_success']:
            raise AssertionError('A06_ORIGINAL_HEADER_UNVERIFIED')
        directory_identity = (owner.directory.stat().st_dev,
                              owner.directory.stat().st_ino)
        profile = hashlib.sha256(read_exact(root, 'supervisor.profile')).hexdigest()
        config = hashlib.sha256(_private_config(owner.directory)).hexdigest()
        evidence['before_crash'] = {'height': 101, 'tip': tip,
            'block_files': _blocks(owner.directory), 'known_tip_header': before_header}
        state = owner.status()
        if state['core_process_owned'] is not True or state['height'] != 101:
            raise AssertionError('A06_PRE_KILL_NATIVE_OWNER_UNVERIFIED')
        owner.binding._assert_image()
        previous = owner.process
        previous.kill()
        code = previous.wait(timeout=15)
        if code == 0:
            raise AssertionError('A06_ABRUPT_CHILD_EXIT_UNVERIFIED')
        evidence['prior_owned_child_exit_code'] = code
        evidence['after_exit_block_files'] = _blocks(owner.directory)
        # No intervening status refresh; genuinely authenticate first Start.
        nonce = secrets.token_hex(16)
        token = read_exact(root, 'supervisor.token', length=32)
        frame = (json.dumps({'protocol': PROTOCOL, 'op': 'start', 'nonce': nonce,
            'proof': request_proof(token, 'start', nonce)})+'\n').encode('ascii')
        reply = owner.handle(frame)
        if owner.process is None or owner.process is previous:
            raise AssertionError('A06_NEW_OWNED_CORE_NOT_STARTED')
        processes.append(owner.process)
        evidence['first_authenticated_start'] = {k: v for k, v in reply.items()
                                                if k not in ('nonce', 'proof')}
        start = time.monotonic()
        observations = []
        for sample in range(11):
            if sample:
                time.sleep(1)
            observed = owner.read.attest()
            observations.append({'elapsed_seconds': round(time.monotonic()-start, 3),
                'height': observed['blocks'],
                'tip_matches': observed['bestblockhash'] == tip})
            if observed['blocks'] == 101 and observed['bestblockhash'] == tip:
                break
        evidence['restart_observations'] = observations
        evidence['after_restart_block_files'] = _blocks(owner.directory)
        evidence['original_header_after_restart'] = _header(cli, owner.directory, tip)
        evidence['same_directory_identity'] = directory_identity == (
            owner.directory.stat().st_dev, owner.directory.stat().st_ino)
        evidence['protected_profile_unchanged'] = profile == hashlib.sha256(
            read_exact(root, 'supervisor.profile')).hexdigest()
        evidence['protected_config_unchanged'] = config == hashlib.sha256(
            _private_config(owner.directory)).hexdigest()
        evidence['complete_block_file_bytes_unchanged'] = (
            evidence['before_crash']['block_files'] == evidence['after_exit_block_files']
            == evidence['after_restart_block_files'])
        evidence['fresh_tip_preserved'] = observations[-1]['tip_matches'] and (
            observations[-1]['height'] == 101)
        evidence['status'] = 'PASS' if evidence['fresh_tip_preserved'] else 'FAIL'
        for name in ('same_directory_identity', 'protected_profile_unchanged',
                     'protected_config_unchanged'):
            if evidence[name] is not True:
                raise AssertionError('A06_FIXTURE_IDENTITY_CHANGED')
    except Exception as error:
        evidence.update(status='ERROR', failure_type=type(error).__name__)
        if type(error) is AssertionError and len(error.args) == 1 and (
                type(error.args[0]) is str and re.fullmatch('A06_[A-Z_]+', error.args[0])):
            evidence['harness_error_code'] = error.args[0]
    finally:
        try:
            if owner is not None:
                if owner.process is not None and owner.process not in processes:
                    processes.append(owner.process)
                owner.status()
                if owner.process is not None:
                    owner.shutdown()
                if any(process.poll() is None for process in processes):
                    raise AssertionError('A06_OWNED_CHILD_CLEANUP_UNVERIFIED')
                owner.close_listener()
                owner.stack.close()
            if temporary is not None:
                shutil.rmtree(temporary)
            evidence['cleanup_verified'] = temporary is not None and not temporary.exists()
        except Exception as error:
            # Preserve an uncertain live child's PRIVATE datadir; never delete
            # it to manufacture cleanup. Hosted runner teardown is separate.
            evidence.update(status='ERROR', cleanup_error_type=type(error).__name__)
        try:
            verify(source_root, source)
            if owner is not None and verified_core_paths(core)[2] != owner.receipt:
                raise AssertionError('A06_CORE_RECEIPT_CHANGED')
        except Exception as error:
            evidence.update(status='ERROR', provenance_error_type=type(error).__name__)
        evidence['completed_at_utc'] = datetime.now(timezone.utc).isoformat()
    return evidence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--core-dir', type=Path, required=True)
    parser.add_argument('--wsp-source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--confirm-disposable-regtest', action='store_true', required=True)
    parser.add_argument('--linux-developer-manifest')
    parser.add_argument('--linux-root-witness', type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise SystemExit('A06_RECEIPT_PATH_OCCUPIED')
    evidence = prove(args.core_dir.resolve(), args.wsp_source.resolve(),
        authorized=args.confirm_disposable_regtest,
        linux_manifest=args.linux_developer_manifest,
        linux_witness=args.linux_root_witness)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(evidence, stream, sort_keys=True, indent=2)
        stream.write('\n')
    print('A06_NATIVE_CORE_CRASH_EVIDENCE='+json.dumps(evidence, sort_keys=True), flush=True)
    # A workflow success can never conceal a failed continuity receipt.
    return 0 if evidence['status'] == 'PASS' and evidence['cleanup_verified'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
