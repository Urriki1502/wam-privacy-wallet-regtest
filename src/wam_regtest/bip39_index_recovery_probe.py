"""Disposable genuine Core/BIP39/native-custody recovery acceptance.

No production startup hook. Exercise the unchanged managed IPC, pinned WSP
signer and explicitly authorized owned reindex in each native/frozen lane.
Existing legacy32 and original no-reindex A06 gates remain separate.
"""
import hashlib
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
from unittest.mock import patch


def _case(core, source, words):
    from . import custody
    from .bip39_wallet import generate_phrase, Bip39RegtestKeys
    from .bip39_durable import Bip39DurableKeyring
    from .core import _read_cli, verified_core_paths
    from .core_supervisor import CoreSupervisor
    from .index_recovery_probe import _blocks, _vault_files, _reservations
    from .managed_wallet_create import create_managed_wallet
    from .managed_spend_session import ManagedWalletSession
    from .managed_spend_client import ManagedSpendRpc
    from .owned_recovery import recover_index
    from .shutdown_probe import _wallet_witness
    from .supervisor_store import read_exact
    from .wallet_session import WalletCoreCli, WalletSessionError
    from .wsp_live import public_regtest_mining_address, _public_fixture_payment

    _, cli, receipt = verified_core_paths(core)
    temporary = Path(tempfile.mkdtemp(prefix='wam-bip39-index-recovery-')).resolve()
    root = temporary/'wam-fusion-core-0123456789abcdef'
    owner = session = worker = keychain = None
    stopped = threading.Event()
    children = []
    server_errors = []
    exchanges = []
    success = False
    native_anchor = custody.anchor

    def private_anchor(wallet_id, requested=None):
        # Only select a NEW disposable Mac Keychain; native anchor operations
        # are unchanged. Windows/Linux use their real native backend directly.
        assert sys.platform == 'darwin' and requested in (None, keychain)
        return native_anchor(wallet_id, keychain)

    def start_server():
        nonlocal worker
        stopped.clear()
        def serve():
            try:
                while not stopped.is_set():
                    try:
                        connection, _ = owner.listener.accept()
                    except socket.timeout:
                        continue
                    with connection:
                        owner._serve_client(connection)
                    exchanges.append(True)
            except Exception as error:
                server_errors.append(type(error).__name__)
        worker = threading.Thread(target=serve, daemon=True)
        worker.start()

    def close_owner():
        nonlocal owner, worker
        if worker is not None:
            stopped.set()
            worker.join(timeout=20)
            assert not worker.is_alive(), 'BIP39_RECOVERY_IPC_WORKER_NOT_STOPPED'
            worker = None
        if owner is not None:
            owner.status()
            if owner.process is not None:
                owner.shutdown()
            owner.close_listener()
            owner.stack.close()
            owner = None

    try:
        if sys.platform == 'darwin':
            keychain = temporary/'disposable-recovery.keychain-db'
            assert subprocess.run(['/usr/bin/security', 'create-keychain', '-p',
                'public-disposable-only', str(keychain)], capture_output=True,
                timeout=20).returncode == 0
            custody.anchor = private_anchor
        custody.create_directory(root)
        owner = CoreSupervisor(root, core, authorized=True)
        owner.start()
        children.append(owner.process)
        directory = owner.directory
        prefix = [str(cli), f'-datadir={directory}']
        _read_cli(prefix+['createwallet', 'test'])
        mine = public_regtest_mining_address(source)
        _read_cli(prefix+['generatetoaddress', '102', mine], timeout=90)
        start_server()
        password = b'public-disposable-bip39-recovery-test'
        phrase = generate_phrase(words, authorized_disposable=True)
        passphrase = '' if words == 12 else 'public-disposable-test-passphrase'
        with Bip39RegtestKeys(phrase, source=source, passphrase=passphrase,
                authorized_disposable=True) as independent:
            expected_code = independent.public_metadata(0)['receive_code']
            seed_digest = hashlib.sha256(independent._seed).digest()
        created = create_managed_wallet(root, core, source, password,
            authorized=True, keychain=keychain, bip39_phrase=phrase,
            bip39_passphrase=passphrase)
        phrase = passphrase = None
        assert created['wallet_locked'] and not created['signer_allowed']
        session = ManagedWalletSession.reopen_spending(root, core, source,
            password, authorized=True)
        assert type(session.ring) is Bip39DurableKeyring
        assert len(session.ring._seed) == 64
        assert hashlib.sha256(session.ring._seed).digest() == seed_digest
        assert session.snapshot().receive_code == expected_code
        funding = WalletCoreCli(cli, directory)
        funding.attest()
        _public_fixture_payment(funding, session.ring.accounts()[0], mine,
            funding_height=2, expected_before_height=102)
        session.snapshot()
        first = session.prepare(expected_code, 50000, 10000)
        session.sign(first.commitment)  # Actual WSP signature, never broadcast.
        _public_fixture_payment(funding, session.ring.accounts()[0], mine,
            funding_height=3, expected_before_height=103)
        session.snapshot()
        session.close()
        session = None
        session = ManagedWalletSession.reopen_spending(root, core, source,
            password, authorized=True)
        second = session.prepare(expected_code, 50000, 10000)
        session.sign(second.commitment)
        actual_call = ManagedSpendRpc.call
        accepted = []
        def lose_accepted_reply(client, method, params=None):
            value = actual_call(client, method, params)
            if method == 'sendrawtransaction':
                accepted.append(value)
                raise WalletSessionError('WALLET_BROADCAST_UNCERTAIN')
            return value
        # Fault injection occurs AFTER genuine Core accepts the transaction.
        # No synthetic RPC result, failed write retry or fabricated blockchain.
        with patch.object(ManagedSpendRpc, 'call', lose_accepted_reply):
            try:
                session.broadcast(second.commitment)
            except WalletSessionError:
                pass
            else:
                raise AssertionError('BIP39_REAL_LOST_REPLY_NOT_EXERCISED')
        assert len(accepted) == 1
        rows = _reservations(session)
        assert {row[3] for row in rows} == {'signed', 'uncertain'}
        history = tuple(tuple(row) for row in session.scanner.store.db.execute(
            'SELECT txid,height,credit,debit FROM history ORDER BY txid'))
        anchor = session.vault.anchor
        anchored = anchor.read()
        identity = anchor.wallet_id
        session.close()
        session = None
        sealed = _vault_files(directory)
        before = owner.read.attest()
        assert before['blocks'] == 104
        tip = before['bestblockhash']
        disk = _blocks(directory)
        profile = read_exact(root, 'supervisor.profile')
        owner.binding._assert_image()
        killed = owner.process
        killed.kill()
        assert killed.wait(timeout=15) != 0
        owner.status()
        owner.start()
        children.append(owner.process)
        observed = owner.read.attest()['blocks']
        assert observed < 104, 'BIP39_EXPECTED_INDEX_LOSS_NOT_OBSERVED'
        assert anchor.read() == anchored and _vault_files(directory) == sealed
        close_owner()
        assert exchanges and not server_errors
        # Immediate reuse follows real authenticated IPC, not an idle listener.
        recovered = recover_index(root, core, expected_height=104,
            expected_tip=tip, authorized_reindex=True)
        assert recovered['status'] == 'OWNED_REGTEST_EXPLICIT_REINDEX_VERIFIED_STOPPED'
        assert _blocks(directory) == disk
        assert read_exact(root, 'supervisor.profile') == profile
        assert anchor.read() == anchored and _vault_files(directory) == sealed
        owner = CoreSupervisor(root, core, authorized=True, existing_only=True)
        owner.start()
        children.append(owner.process)
        final = owner.read.attest()
        assert (final['blocks'], final['bestblockhash']) == (104, tip)
        if 'test' not in _wallet_witness(owner, 'listwallets'):
            _wallet_witness(owner, 'loadwallet', 'test')
        start_server()
        session = ManagedWalletSession.reopen_spending(root, core, source,
            password, authorized=True)
        assert type(session.ring) is Bip39DurableKeyring
        assert len(session.ring._seed) == 64
        assert hashlib.sha256(session.ring._seed).digest() == seed_digest
        assert session.snapshot().receive_code == expected_code
        assert session.vault.anchor.wallet_id == identity
        assert _reservations(session) == rows
        assert tuple(tuple(row) for row in session.scanner.store.db.execute(
            'SELECT txid,height,credit,debit FROM history ORDER BY txid')) == history
        assert session._review is None and session._signed is None and session._prepared is None
        session.close()
        session = None
        close_owner()
        assert not server_errors and all(child.poll() is not None for child in children)
        assert verified_core_paths(core)[2] == receipt
        success = True
        return {'words': words, 'passphrase_used': words == 24, 'status': 'PASS',
            'original_height': 104, 'original_tip': tip,
            'index_loss_observed_height': observed, 'explicit_reindex': recovered,
            'exact_original_64_byte_seed_and_identity': True,
            'real_authenticated_ipc_before_supervisor_restart': True,
            'signed_and_uncertain_reservations_preserved': True,
            'native_anchor_vault_unchanged_by_reindex': True,
            'confirmed_scanner_history_preserved': True,
            'complete_block_file_bytes_unchanged': True,
            'automatic_broadcast': False, 'post_crash_mining': False,
            'cleanup_verified': True}
    finally:
        try:
            if session is not None:
                session.close()
            close_owner()
        finally:
            custody.anchor = native_anchor
        # Failed fixtures and native anchors stay for diagnosis; never erase
        # evidence to qualify recovery. Only successful disposable data clears.
        if success and all(child.poll() is not None for child in children):
            if keychain is not None:
                assert subprocess.run(['/usr/bin/security', 'delete-keychain',
                    str(keychain)], capture_output=True, timeout=20).returncode == 0
            shutil.rmtree(temporary)


def prove_bip39_index_recovery(core, source):
    from .core import verified_core_paths
    _, _, receipt = verified_core_paths(core)
    cases = []
    for words in (12, 24):
        print(f'BIP39_INDEX_RECOVERY_WORDS={words}', flush=True)
        cases.append(_case(core, source, words))
    assert verified_core_paths(core)[2] == receipt
    return {'status': 'REAL_BIP39_MANAGED_INDEX_RECOVERY_PASS',
        'platform': receipt['platform'], 'core_version': 'v0.1.11',
        'wamd_sha256': receipt['wamd_sha256'], 'wam_cli_sha256': receipt['wam_cli_sha256'],
        'execution': 'FROZEN' if getattr(sys, 'frozen', False) else 'SOURCE_NATIVE',
        'cases': cases, 'synthetic_rpc': False, 'mainnet_allowed': False,
        'physical_accepted': False, 'full_managed_gui_qualified': False,
        'historical_a06_failure_unchanged': True}
