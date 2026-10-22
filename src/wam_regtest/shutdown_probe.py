"""Genuine pinned Core graceful-stop acceptance in disposable owned profiles.

Separate from A06's unchanged abrupt-crash diagnostic. No reindex, chain
replacement, post-restart mining, external Core, wallet restore or mocked RPC.
"""
from pathlib import Path
import hashlib
import shutil
import signal
import socket
import subprocess
import json
import sys
import tempfile


def _wallet_witness(owner, method, *params):
    # Test-only independent exact-CLI wallet witness. Do not broaden the
    # application's read/spend transport allowlists for acceptance tooling.
    assert method in ('getbalances', 'getaddressesbylabel', 'getaddressinfo',
                      'listwallets', 'loadwallet')
    from .network_policy import local_rpc_port
    port = local_rpc_port(owner.directory)
    owner.binding._assert_image()
    with socket.create_connection(('127.0.0.1', port), timeout=1) as sock:
        owner.binding.assert_socket(sock)
    command = [str(owner.cli), f'-datadir={owner.directory}',
        '-rpcconnect=127.0.0.1', f'-rpcport={port}']
    if method not in ('listwallets', 'loadwallet'):
        command.append('-rpcwallet=test')
    command.extend((method, *params))
    result = subprocess.run(command, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=20,
        env=owner._child_environment(),
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0) if sys.platform == 'win32' else 0)
    assert result.returncode == 0, 'GRACEFUL_CORE_WALLET_WITNESS_DENIED'
    return json.loads(result.stdout)


def prove_graceful_shutdown(core):
    from .core import _read_cli, verified_core_paths
    from .core_supervisor import CoreSupervisor
    from .custody import create_directory
    from .supervisor_store import read_exact
    _, cli, receipt = verified_core_paths(core)
    cases = []
    for method in (('rpc-stop', 'sigterm') if sys.platform != 'win32' else ('rpc-stop',)):
        temporary = Path(tempfile.mkdtemp(prefix='wam-graceful-owned-')).resolve()
        root = temporary/'wam-fusion-core-0123456789abcdef'
        owner = None
        processes = []
        cleaned = False
        try:
            create_directory(root)
            owner = CoreSupervisor(root, core, authorized=True)
            owner.start()
            processes.append(owner.process)
            prefix = [str(cli), f'-datadir={owner.directory}']
            _read_cli(prefix+['createwallet', 'test'])
            wallet = prefix+['-rpcwallet=test']
            address = _read_cli(wallet+['getnewaddress', 'graceful-persisted-test'])
            assert len(_read_cli(prefix+['generatetoaddress', '101', address], timeout=90)) == 101
            before = owner.read.attest()
            assert before['blocks'] == 101
            balances = _wallet_witness(owner, 'getbalances')
            assert balances['mine']['trusted'] > 0
            labels = _wallet_witness(owner, 'getaddressesbylabel', 'graceful-persisted-test')
            assert address in labels
            identity = (owner.directory.stat().st_dev, owner.directory.stat().st_ino)
            profile = hashlib.sha256(read_exact(root, 'supervisor.profile')).hexdigest()
            owner.binding._assert_image()
            original = owner.process
            if method == 'rpc-stop':
                # Independently send genuine stop; never let shutdown's
                # fallback terminate/kill masquerade as a successful RPC stop.
                from .network_policy import local_rpc_port
                with socket.create_connection(('127.0.0.1', local_rpc_port(owner.directory)), timeout=1) as sock:
                    owner.binding.assert_socket(sock)
                _read_cli(prefix+['stop'])
            else:
                original.send_signal(signal.SIGTERM)
            assert original.wait(timeout=30) == 0, 'GRACEFUL_CORE_EXIT_NOT_CLEAN'
            assert owner.status()['state'] == 'recovery-needed'
            owner.start()
            processes.append(owner.process)
            after = owner.read.attest()
            assert (after['blocks'], after['bestblockhash']) == (101, before['bestblockhash'])
            if 'test' not in _wallet_witness(owner, 'listwallets'):
                _wallet_witness(owner, 'loadwallet', 'test')
            assert _wallet_witness(owner, 'getbalances') == balances
            assert _wallet_witness(owner, 'getaddressesbylabel', 'graceful-persisted-test') == labels
            assert _wallet_witness(owner, 'getaddressinfo', address)['ismine'] is True
            assert identity == (owner.directory.stat().st_dev, owner.directory.stat().st_ino)
            assert profile == hashlib.sha256(read_exact(root, 'supervisor.profile')).hexdigest()
            cases.append({'method': method, 'status': 'PASS', 'height_before': 101,
                'height_after': 101, 'exact_original_tip': before['bestblockhash'],
                'exact_tip_preserved': True, 'same_datadir_identity': True,
                'protected_profile_unchanged': True, 'core_wallet_address_and_balance_preserved': True,
                'clean_exit_code': 0, 'reindex_performed': False,
                'post_restart_mining': False, 'replacement_wallet_created': False})
        finally:
            if owner is not None:
                if owner.process is not None and owner.process not in processes:
                    processes.append(owner.process)
                owner.status()
                if owner.process is not None:
                    owner.shutdown()
                if any(p.poll() is None for p in processes):
                    raise AssertionError('GRACEFUL_OWNED_PROCESS_CLEANUP_UNVERIFIED')
                owner.close_listener()
                owner.stack.close()
                cleaned = True
            # Preserve uncertain child's chain. Cleanup is only a disposable
            # fixture lifecycle AFTER verification, never a recovery strategy.
            if cleaned:
                shutil.rmtree(temporary)
        assert cleaned and not temporary.exists()
    assert verified_core_paths(core)[2] == receipt
    return {'status': 'REAL_CORE_GRACEFUL_SHUTDOWN_CONTINUITY_PASS',
        'platform': receipt['platform'], 'core_version': 'v0.1.11',
        'wamd_sha256': receipt['wamd_sha256'], 'wam_cli_sha256': receipt['wam_cli_sha256'],
        'cases': cases, 'owned_processes_reaped': True, 'cleanup_verified': True,
        'synthetic_rpc': False, 'mainnet_allowed': False, 'a06_abrupt_crash_resolved': False,
        'physical_accepted': False}
