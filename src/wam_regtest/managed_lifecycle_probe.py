"""Independent Q05 GUI acceptance. Never repair crash residue to obtain PASS.

Only a newly provisioned, private, explicitly marked disposable fixture is
accepted by the child driver. Real widgets, native vault, pinned WSP and Core
IPC execute unchanged. Dialog input is supplied through Qt, never mocked.
"""
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import time

PASSWORD = b'public-disposable-q05-lifecycle-only'
MARKER = 'q05-acceptance-fixture.enc'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True,
        separators=(',', ':')).encode('ascii')).hexdigest()


def _fixture_store():
    from . import encrypted_storage as store
    if sys.platform == 'win32':
        from . import windows_private_storage as store
    elif sys.platform == 'linux':
        from . import linux_private_storage as store
    return store


def fixture_write(root, name, value):
    from wam_sp.keystore import seal
    _fixture_store().publish(root, name, seal(value, PASSWORD, b'recovery'))


def fixture_read(root, name):
    from wam_sp.keystore import unseal
    return unseal(_fixture_store().read(root, name), PASSWORD, b'recovery')


def close_gui(window, app, *, timeout=20):
    """Request normal close; a live worker is allowed to refuse it safely.

    Native event dispatch can start a timer worker after an idle observation.
    Never stop timers, clear worker pointers, force-delete a window or treat a
    refusal as success. Retry the normal guarded close while draining events.
    A permanently refusing/busy GUI still fails the bounded acceptance.
    """
    deadline=time.monotonic()+timeout
    while True:
        if window.close():
            return
        if time.monotonic()>=deadline:
            raise ValueError('Q05_NORMAL_GUI_CLOSE_NOT_COMPLETED')
        app.processEvents()
        time.sleep(.01)


def child(core, source, argv):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', type=Path, required=True)
    ap.add_argument('--mode', choices=('read', 'spend', 'wrong-password',
        'decline', 'wait-locked', 'wait-unlocked', 'wait-spend-core', 'blocked-spend', 'attached', 'wrong-version', 'not-ready',
        'recover', 'recover-wrong-password', 'recover-decline'), required=True)
    ap.add_argument('--report', required=True)
    ap.add_argument('--confirm-disposable-regtest-gui-probe', action='store_true')
    args = ap.parse_args(argv)
    from .supervisor_store import _root
    read_exact, create_once = fixture_read, fixture_write
    from . import custody
    root = args.root
    if (not args.confirm_disposable_regtest_gui_probe or not root.is_absolute()
            or not root.parent.name.startswith('wam-q05-gui-')):
        raise ValueError('Q05_DISPOSABLE_FIXTURE_REQUIRED')
    _root(root)
    from .wsp_live import _pinned_source
    _pinned_source(source)
    fixture = json.loads(read_exact(root, MARKER))
    if (fixture.get('schema') != 'wam-q05-disposable-gui/v1'
            or fixture.get('network') != 'regtest'
            or fixture.get('mainnet_allowed') is not False
            or re.fullmatch(r'q05-report-[0-9a-f]{24}\.enc', args.report) is None):
        raise ValueError('Q05_FIXTURE_SCOPE_DENIED')
    from .core import verified_core_paths
    from .wsp_live import REGTEST_GENESIS, _pinned_source
    if sys.platform == 'linux':
        from .linux_runtime import configure
        configure(core, fixture['linux_manifest'], Path(fixture['linux_witness']), authorized=True)
    _, _, receipt = verified_core_paths(core)
    _pinned_source(source)
    if (fixture['core_sha256'] != receipt['wamd_sha256']
            or fixture['cli_sha256'] != receipt['wam_cli_sha256']
            or fixture['genesis'] != REGTEST_GENESIS):
        raise ValueError('Q05_FIXTURE_PROVENANCE_DENIED')
    native_anchor = custody.anchor
    if sys.platform == 'darwin':
        keychain = root.parent / 'disposable-q05.keychain-db'
        custody.anchor = lambda wallet_id, requested=None: native_anchor(wallet_id, keychain)
    from .desktop import qt_application, shutdown_qt
    from .managed_gui import ManagedCoreWindow
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox
    from shiboken6 import delete, isValid
    app = qt_application()
    if args.mode == 'attached':
        from .attached_core_gui import ExistingCoreReadOnlyWindow
        # Windows freezes stage the original signed pair privately PER process.
        # An identical fresh child copy is not the daemon's native file image.
        # Select the actual parent fixture image, then keep BOTH immutable-byte
        # pinning and AttachedCoreBinding's native same-file/PID checks intact.
        owner_core = Path(fixture['owner_core_dir'])
        if not owner_core.is_absolute() or '..' in owner_core.parts:
            raise ValueError('Q05_OWNER_CORE_PATH_DENIED')
        _, _, owner_receipt = verified_core_paths(owner_core)
        if owner_receipt != receipt:
            raise ValueError('Q05_OWNER_CORE_PAIR_CHANGED')
        window = ExistingCoreReadOnlyWindow(owner_core, root/'chain', fixture['core_pid'])
        window.show(); window.request_refresh()
        deadline = time.monotonic()+30
        while window._worker is not None and time.monotonic()<deadline:
            app.processEvents(); time.sleep(.01)
        assert window._worker is None and window._proof is not None
        assert (window._proof['height'], window._proof['tip']) == (fixture['height'], fixture['tip'])
        assert not hasattr(window, 'start_core') and not hasattr(window, 'stop_core')
        assert not hasattr(window, '_managed_root') and not hasattr(window, 'recover_index')
        proof = {'status': 'PASS', 'attached_gui_has_no_managed_lifecycle': True, 'actual_parent_image_verified': True,
            'native_gui': True, 'frozen': bool(getattr(sys, 'frozen', False)),
            'binary_sha256': hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
            'synthetic_rpc': False, 'mainnet_allowed': False, 'qt_platform': app.platformName()}
        assert window.grab().save(str(root/(args.report+'.png')))
        create_once(root, args.report, (json.dumps(proof,sort_keys=True)+'\n').encode('ascii'))
        close_gui(window,app); delete(window); app.processEvents(); shutdown_qt()
        custody.anchor = native_anchor
        return 0
    window = ManagedCoreWindow(root, core_dir=core, wsp_source=source)
    window.show()
    mode = args.mode
    def settle():
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            app.processEvents()
            spend = window._spend_window
            if window._worker is None and (spend is None or spend._worker is None):
                app.processEvents()
                return
            time.sleep(.01)
        raise ValueError('Q05_GUI_WORKER_TIMEOUT')
    def answer():
        dialog = QApplication.activeModalWidget()
        if isinstance(dialog, QMessageBox):
            button = (QMessageBox.StandardButton.No if mode in ('decline','recover-decline')
                      else QMessageBox.StandardButton.Yes)
            dialog.button(button).click()
        elif isinstance(dialog, QInputDialog):
            secret = b'public-intentionally-wrong-q05' if mode in ('wrong-password','recover-wrong-password') else PASSWORD
            dialog.setTextValue(secret.decode('ascii'))
            dialog.accept()
    responder = QTimer()
    responder.setInterval(10)
    responder.timeout.connect(answer)
    try:
        window.request_sync()
        settle()
        if mode in ('wrong-version', 'not-ready'):
            if mode == 'wrong-version':
                assert not window._managed_authenticated and window._managed_state == 'error'
                assert not window.start_core.isEnabled() and not window.stop_core.isEnabled()
            else:
                assert window._managed_authenticated and window._managed_state in ('syncing','recovery-needed','stopped')
            assert window._snapshot is None and window._spend_window is None
            assert not window.view_wallet_button.isEnabled() and not window.spend_wallet_button.isEnabled()
            assert not window.create_wallet_button.isEnabled() and not window.create_bip39_wallet_button.isEnabled()
            proof = {'status': 'PASS', 'unsupported_selected_profile_version_denied_before_rpc': mode == 'wrong-version',
                'visible_core_state': window._managed_state, 'no_wallet_adopted': True,
                'native_gui': True, 'frozen': bool(getattr(sys, 'frozen', False)),
                'binary_sha256': hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
                'synthetic_rpc': False, 'mainnet_allowed': False, 'qt_platform': app.platformName()}
            assert window.grab().save(str(root/(args.report+'.png')))
            create_once(root,args.report,(json.dumps(proof,sort_keys=True)+'\n').encode('ascii'))
            close_gui(window,app); delete(window); app.processEvents(); shutdown_qt()
            return 0
        assert window._managed_authenticated and window._managed_state == 'ready'
        assert window.session is None and window._snapshot is None
        assert not window.dashboard.go_send.isEnabled()
        responder.start()
        if mode.startswith('recover'):
            window.welcome_page.scroll.ensureWidgetVisible(window.recover_runtime_button)
            app.processEvents()
            assert window.recover_runtime_button.isVisible() and window.recover_runtime_button.isEnabled()
            window.recover_runtime_button.click()
            settle(); responder.stop()
            recovered=window._runtime_recovery_receipt
            assert (recovered is not None) is (mode=='recover')
            assert window._spend_window is None and window._snapshot is None
            assert window.session is None and not window.dashboard.go_send.isEnabled()
            proof={'status':'PASS' if recovered else 'DENIED',
                'recovery_receipt':recovered,'remains_locked':True,
                'native_gui':True,'frozen':bool(getattr(sys,'frozen',False)),
                'binary_sha256':hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
                'synthetic_rpc':False,'mainnet_allowed':False,'qt_platform':app.platformName()}
            assert window.grab().save(str(root/(args.report+'.png')))
            create_once(root,args.report,(json.dumps(proof,sort_keys=True)+'\n').encode('ascii'))
            close_gui(window,app); delete(window); app.processEvents(); shutdown_qt()
            return 0
        if mode in ('read', 'wait-locked'):
            target=window.welcome_page.view
        else:
            target=window.welcome_page.send
        window.welcome_page.scroll.ensureWidgetVisible(target)
        app.processEvents()
        assert target.isVisible() and target.isEnabled()
        target.click()
        settle()
        responder.stop()
        spend = window._spend_window
        denied = mode in ('wrong-password', 'decline', 'blocked-spend')
        if denied:
            assert spend is None and window._snapshot is None
            assert not window.dashboard.go_send.isEnabled()
            proof = {'status': 'DENIED', 'no_wallet_adopted': True}
        else:
            snap = window._snapshot if spend is None else spend._snapshot
            assert snap is not None and not snap.synthetic_rpc and not snap.demo_account_only
            assert snap.mainnet_allowed is False
            assert snap.height == fixture['height'] and snap.tip == fixture['tip']
            assert digest(snap.receive_code) == fixture['receive_digest']
            assert digest([row.__dict__ for row in snap.history]) == fixture['history_digest']
            assert snap.confirmed_atoms == fixture['confirmed_atoms']
            if spend is not None:
                from .index_recovery_probe import _reservations
                assert digest(_reservations(spend.session)) == fixture['reservations_digest']
                assert spend.session.vault.anchor.wallet_id == fixture['wallet_id']
                assert spend.review is None and not spend.signed
            proof = {'status': 'PASS', 'original_receive_history_balance': True,
                'original_wallet_id': fixture['wallet_id'], 'height': snap.height,
                'tip': snap.tip, 'receive_digest': fixture['receive_digest'],
                'reservations_digest': fixture['reservations_digest'],
                'unlocked_only_after_explicit_consent': spend is not None}
        proof.update(binary_sha256=hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
                     qt_platform=app.platformName(), frozen=bool(getattr(sys, 'frozen', False)),
                     native_gui=True, synthetic_rpc=False, mainnet_allowed=False)
        assert (spend or window).grab().save(str(root/(args.report+'.png')))
        create_once(root, args.report, (json.dumps(proof, sort_keys=True)+'\n').encode('ascii'))
        if mode.startswith('wait-'):
            # Parent kills this exact Popen only after observing real Qt/WSP
            # readiness. While locked, background status must reject Core loss.
            deadline = time.monotonic() + 60
            observed = False
            last = None
            while time.monotonic() < deadline:
                app.processEvents()
                state = (window._managed_state, window._worker is not None, window._managed_dialog_open, window._sync_timer.isActive())
                if state != last:
                    print('Q05_GUI_WAIT_STATE='+repr(state), flush=True)
                    last = state
                if mode == 'wait-locked' and window._managed_state != 'ready' and not observed:
                    assert window._snapshot is None and window._spend_window is None
                    assert not window.spend_wallet_button.isEnabled()
                    create_once(root, args.report.replace('.enc', '-unavailable.enc'), b'FAIL_CLOSED\n')
                    observed = True
                if mode == 'wait-spend-core' and spend.session.faulted and spend._worker is None and not observed:
                    assert spend._snapshot is None
                    assert not spend.sign_button.isEnabled() and not spend.broadcast_button.isEnabled()
                    create_once(root, args.report.replace('.enc', '-unavailable.enc'), b'FAIL_CLOSED\n')
                    observed = True
                if mode == 'wait-spend-core' and observed and (root/args.report.replace('.enc', '-close.enc')).exists():
                    assert fixture_read(root,args.report.replace('.enc', '-close.enc')) == b'EXPLICIT_NORMAL_GUI_CLOSE\n'
                    break
                time.sleep(.01)
            else:
                raise ValueError('Q05_EXPECTED_GUI_TERMINATION_NOT_INJECTED')
        if spend is not None:
            close_gui(spend,app)
            settle()
            delete(spend)
        close_gui(window,app)
        delete(window)
        app.processEvents()
        shutdown_qt()
        return 0
    finally:
        if isValid(responder): responder.stop()
        # No destructive cleanup or automatic recovery of unexplained runtime.
        custody.anchor = native_anchor


def _environment():
    env = {k: v for k, v in os.environ.items() if not k.startswith('_PYI_')}
    if getattr(sys, 'frozen', False):
        env.pop('PYTHONPATH', None)
        env.pop('PYTHONHOME', None)
        env['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
    return env


def run_child(root, core, source, mode, *, wait=False):
    import secrets
    read_exact = fixture_read
    report = 'q05-report-'+secrets.token_hex(12)+'.enc'
    args = ['--root', str(root), '--mode', mode, '--report', report,
            '--confirm-disposable-regtest-gui-probe']
    if getattr(sys, 'frozen', False):
        command = [sys.executable, '--ci-managed-gui-child', *args]
    else:
        command = [sys.executable, '-m', 'wam_regtest.managed_lifecycle_probe',
                   '--core-dir', str(core), '--wsp-source', str(source), *args]
    with (root/(report+'.log')).open('xb') as log:
        child_process = subprocess.Popen(command, stdin=subprocess.DEVNULL,
            stdout=log, stderr=log, env=_environment())
    deadline = time.monotonic() + 100
    try:
        while time.monotonic() < deadline:
            if (root/report).exists():
                proof = json.loads(read_exact(root, report))
                assert proof['frozen'] is bool(getattr(sys, 'frozen', False))
                assert proof['binary_sha256'] == hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest()
                if mode in ('read', 'spend'):
                    import shutil
                    review = Path('fusion-ui-review')
                    review.mkdir(exist_ok=True)
                    label = 'frozen' if getattr(sys, 'frozen', False) else 'native'
                    shutil.copyfile(root/(report+'.png'), review/('q05-managed-'+label+'-'+mode+'.png'))
                if wait:
                    assert child_process.poll() is None
                    return child_process, report, proof
                assert child_process.wait(timeout=30) == 0, 'Q05_GUI_CHILD_BAD_EXIT'
                return proof
            if child_process.poll() is not None:
                raise ValueError('Q05_GUI_CHILD_NO_VERIFIED_REPORT')
            time.sleep(.05)
        raise ValueError('Q05_GUI_CHILD_REPORT_TIMEOUT')
    except BaseException:
        if child_process.poll() is None:
            child_process.kill()
            child_process.wait(timeout=15)
        raise


def prove_managed_gui_lifecycle(core, source):
    """All failures remain nonpassing; retain failed private fixture and anchor."""
    import socket
    import tempfile
    import threading
    from unittest.mock import patch
    from . import custody
    from .core import verified_core_paths, _read_cli
    from .core_supervisor import CoreSupervisor
    from .managed_wallet_create import create_managed_wallet
    from .managed_spend_session import ManagedWalletSession
    from .managed_spend_client import ManagedSpendRpc
    from .index_recovery_probe import _blocks, _vault_files, _reservations
    from .bip39_wallet import generate_phrase
    from .supervisor_store import read_exact
    create_once = fixture_write
    from .wsp_live import REGTEST_GENESIS, public_regtest_mining_address, _public_fixture_payment
    from .owned_recovery import recover_index
    from .wallet_session import WalletCoreCli, WalletSessionError
    node, cli, receipt = verified_core_paths(core)
    temporary = Path(tempfile.mkdtemp(prefix='wam-q05-gui-')).resolve()
    root = temporary/'wam-fusion-core-0123456789abcdef'
    owner = session = worker = None
    children = []
    stop = threading.Event()
    errors = []
    cases = {}
    native_anchor = custody.anchor
    keychain = temporary/'disposable-q05.keychain-db'
    def start_owner():
        nonlocal owner, worker
        stop.clear()
        owner = CoreSupervisor(root, core, authorized=True, existing_only=(root/'supervisor.profile').exists())
        owner.start()
        children.append(owner.process)
        def serve():
            try:
                while not stop.is_set():
                    try: connection, _ = owner.listener.accept()
                    except socket.timeout: continue
                    with connection: owner._serve_client(connection)
            except Exception as error:
                errors.append(type(error).__name__)
        worker = threading.Thread(target=serve, daemon=True)
        worker.start()
    def close_owner():
        nonlocal owner, worker
        if worker is not None:
            stop.set(); worker.join(timeout=20)
            assert not worker.is_alive()
            worker = None
        if owner is not None:
            owner.status()
            if owner.process is not None: owner.shutdown()
            owner.close_listener(); owner.stack.close(); owner = None
    try:
        if sys.platform == 'darwin':
            assert subprocess.run(['/usr/bin/security', 'create-keychain', '-p',
                'public-disposable-only', str(keychain)], capture_output=True, timeout=20).returncode == 0
            custody.anchor = lambda wallet_id, requested=None: native_anchor(wallet_id, keychain)
        custody.create_directory(root)
        start_owner()
        directory = owner.directory
        prefix = [str(cli), f'-datadir={directory}']
        _read_cli(prefix+['createwallet', 'test'])
        mine = public_regtest_mining_address(source)
        _read_cli(prefix+['generatetoaddress', '102', mine], timeout=90)
        create_managed_wallet(root, core, source, PASSWORD, authorized=True,
            keychain=keychain if sys.platform == 'darwin' else None,
            bip39_phrase=generate_phrase(12, authorized_disposable=True), bip39_passphrase='')
        session = ManagedWalletSession.reopen_spending(root, core, source, PASSWORD, authorized=True)
        funding = WalletCoreCli(cli, directory); funding.attest()
        _public_fixture_payment(funding, session.ring.accounts()[0], mine,
            funding_height=2, expected_before_height=102)
        session.snapshot()
        code = session.snapshot().receive_code
        first = session.prepare(code, 50000, 10000); session.sign(first.commitment)
        _public_fixture_payment(funding, session.ring.accounts()[0], mine,
            funding_height=3, expected_before_height=103)
        session.snapshot(); session.close()
        session = ManagedWalletSession.reopen_spending(root, core, source, PASSWORD, authorized=True)
        second = session.prepare(code, 50000, 10000); session.sign(second.commitment)
        actual_call = ManagedSpendRpc.call
        accepted = []
        def lose_reply(client, method, params=None):
            value = actual_call(client, method, params)
            if method == 'sendrawtransaction':
                accepted.append(value)
                raise WalletSessionError('WALLET_BROADCAST_UNCERTAIN')
            return value
        snap = session.snapshot()
        with patch.object(ManagedSpendRpc, 'call', lose_reply):
            try: session.broadcast(second.commitment)
            except WalletSessionError: pass
            else: raise AssertionError('Q05_GENUINE_UNCERTAIN_WRITE_REQUIRED')
        assert len(accepted) == 1
        rows = _reservations(session)
        assert {r[3] for r in rows} == {'signed', 'uncertain'}
        anchor = session.vault.anchor; anchored = anchor.read()
        fixture = {'schema': 'wam-q05-disposable-gui/v1', 'network': 'regtest',
            'genesis': REGTEST_GENESIS, 'mainnet_allowed': False,
            'core_sha256': receipt['wamd_sha256'], 'cli_sha256': receipt['wam_cli_sha256'],
            'wallet_id': anchor.wallet_id, 'height': snap.height, 'tip': snap.tip, 'core_pid': owner.process.pid, 'owner_core_dir': str(core),
            'receive_digest': digest(code), 'reservations_digest': digest(rows),
            'history_digest': digest([row.__dict__ for row in snap.history]),
            'confirmed_atoms': snap.confirmed_atoms}
        if sys.platform == 'linux':
            from .linux_runtime import policy
            p = policy(); fixture.update(linux_manifest=p.manifest_sha256, linux_witness=str(p.witness))
        session.close(); session = None
        create_once(root, MARKER, json.dumps(fixture, sort_keys=True).encode('ascii'))
        profile = read_exact(root, 'supervisor.profile')
        sealed = _vault_files(directory)
        chain = _blocks(directory)
        mempool = set(_read_cli(prefix+['getrawmempool']))
        assert set(mempool) == set(accepted)
        directory_identity = directory.stat().st_dev, directory.stat().st_ino
        # A second real owner must fail at the native repository-independent
        # Core lease; never stop or adopt the active process to resolve it.
        try:
            contender = CoreSupervisor(root, core, authorized=True, existing_only=True)
        except ValueError as error:
            assert error.args == ('SUPERVISOR_STORAGE_LEASE_BUSY',)
        else:
            contender.close_listener(); contender.stack.close()
            raise AssertionError('Q05_SECOND_SUPERVISOR_ADMITTED')
        cases['supervisor-lock-contention'] = {'status': 'PASS', 'original_core_alive': owner.process.poll() is None}
        from .attached_core import attach_existing_core
        with attach_existing_core(core, directory, owner.process.pid, authorized_readonly=True) as attached:
            assert attached.attest()['bestblockhash'] == fixture['tip']
            assert not hasattr(attached, 'shutdown') and not hasattr(attached, 'recover_index')
            try: attached.call('stop')
            except ValueError: pass
            else: raise AssertionError('Q05_EXTERNAL_ATTACH_STOP_ALLOWED')
        assert owner.process.poll() is None
        cases['external-attach-has-no-lifecycle-authority'] = {'status': 'PASS', 'attached_stop_refused': True}
        attached_proof = run_child(root, core, source, 'attached')
        assert attached_proof['status'] == 'PASS'
        cases['external-attach-has-no-lifecycle-authority']['gui_receipt'] = attached_proof
        # A private COPY of public supervisor metadata selects an unsupported
        # version. Never mutate the original profile, live Core or wallet.
        invalid_parent = temporary/'wam-q05-gui-version'
        custody.create_directory(invalid_parent)
        invalid_root = invalid_parent/root.name
        custody.create_directory(invalid_root)
        bad_profile = json.loads(profile); bad_profile['version'] = 'v0.1.12'
        from .supervisor_store import create_once as publish_profile
        publish_profile(invalid_root,'supervisor.profile',json.dumps(bad_profile).encode('ascii'))
        fixture_write(invalid_root,MARKER,json.dumps(fixture).encode('ascii'))
        cases['wrong-version-gui'] = run_child(invalid_root,core,source,'wrong-version')
        assert owner.process.poll() is None and read_exact(root,'supervisor.profile') == profile
        for mode in ('wrong-password', 'decline', 'read', 'spend', 'read'):
            proof = run_child(root, core, source, mode)
            assert proof['status'] == ('DENIED' if mode in ('wrong-password', 'decline') else 'PASS')
            cases['normal-'+mode] = proof
            assert anchor.read() == anchored and _vault_files(directory) == sealed
            assert not (directory/'wallet-runtime.sqlite').exists()
            assert set(_read_cli(prefix+['getrawmempool'])) == mempool
        gui, report, proof = run_child(root, core, source, 'wait-locked', wait=True)
        children.append(gui)
        gui.kill(); assert gui.wait(timeout=15) != 0
        assert run_child(root, core, source, 'read')['status'] == 'PASS'
        cases['locked-gui-kill-reopen'] = {'status': 'PASS', 'genuine_process_kill': True, 'ready_receipt': proof}
        gui, report, proof = run_child(root, core, source, 'wait-locked', wait=True)
        children.append(gui)
        owner.binding._assert_image()
        owner.process.kill(); assert owner.process.wait(timeout=15) != 0
        # Verified read-only GUI deliberately expires its display on a 30s
        # authenticated status cycle. Wait for that existing product interval.
        deadline = time.monotonic()+40
        while not (root/report.replace('.enc', '-unavailable.enc')).exists() and time.monotonic()<deadline:
            assert gui.poll() is None
            time.sleep(.1)
        assert fixture_read(root, report.replace('.enc', '-unavailable.enc')) == b'FAIL_CLOSED\n'
        gui.kill(); assert gui.wait(timeout=15) != 0
        owner.status()
        cases['unavailable-core-fresh-gui-locked'] = run_child(root,core,source,'not-ready')
        owner.start(); children.append(owner.process)
        observed = owner.read.attest()['blocks']
        assert observed < fixture['height'], 'Q05_CORE_INDEX_LOSS_NOT_OBSERVED'
        cases['index-loss-gui-wallet-locked-before-reindex'] = run_child(root,core,source,'not-ready')
        assert anchor.read() == anchored and _vault_files(directory) == sealed
        close_owner()
        try:
            recover_index(root, core, expected_height=fixture['height'], expected_tip=fixture['tip'])
        except ValueError: pass
        else: raise AssertionError('Q05_MISSING_REINDEX_CONSENT_ACCEPTED')
        if getattr(sys, 'frozen', False):
            command = [sys.executable, '--recover-owned-regtest-index', '--root', str(root),
                '--expected-height', str(fixture['height']), '--expected-tip', fixture['tip'],
                '--confirm-regtest-managed-core']
            if sys.platform == 'linux':
                command += ['--linux-developer-manifest', fixture['linux_manifest'],
                            '--linux-root-witness', fixture['linux_witness']]
            denied = subprocess.run(command, env=_environment(), stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
            assert denied.returncode == 2 and not list(root.glob('supervisor.recovery.*'))
            approved = subprocess.run(command+['--confirm-reindex-existing-regtest'], env=_environment(),
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
            assert approved.returncode == 0, 'Q05_FINAL_BINARY_EXPLICIT_REINDEX_DENIED'
        else:
            recovered = recover_index(root, core, expected_height=fixture['height'],
                                      expected_tip=fixture['tip'], authorized_reindex=True)
            assert recovered['status'] == 'OWNED_REGTEST_EXPLICIT_REINDEX_VERIFIED_STOPPED'
        assert anchor.read() == anchored and _vault_files(directory) == sealed
        assert _blocks(directory) == chain and read_exact(root, 'supervisor.profile') == profile
        start_owner()
        assert run_child(root, core, source, 'spend')['status'] == 'PASS'
        cases['core-kill-explicit-recovery-original-gui'] = {'status': 'PASS',
            'observed_index_height': observed, 'exact_original_tip': fixture['tip'],
            'explicit_consent_required': True, 'original_chain_vault_anchor': True, 'ready_receipt': proof}
        assert (owner.read.attest()['blocks'], owner.read.attest()['bestblockhash']) == (fixture['height'], fixture['tip'])
        # Reindex may drop mempool. It must NEVER rebroadcast to repair it.
        after_mempool = set(_read_cli(prefix+['getrawmempool']))
        assert after_mempool <= mempool
        # The live spending GUI must also fail closed on Core loss; normal
        # close of THIS still-live session owns its runtime cleanup authority.
        gui, report, proof = run_child(root, core, source, 'wait-spend-core', wait=True)
        children.append(gui)
        owner.binding._assert_image(); owner.process.kill()
        assert owner.process.wait(timeout=15) != 0
        deadline = time.monotonic()+40
        while not (root/report.replace('.enc','-unavailable.enc')).exists() and time.monotonic()<deadline:
            assert gui.poll() is None; time.sleep(.1)
        assert fixture_read(root,report.replace('.enc','-unavailable.enc')) == b'FAIL_CLOSED\n'
        fixture_write(root,report.replace('.enc','-close.enc'),b'EXPLICIT_NORMAL_GUI_CLOSE\n')
        assert gui.wait(timeout=30) == 0
        assert not (directory/'wallet-runtime.sqlite').exists()
        assert anchor.read() == anchored and _vault_files(directory) == sealed
        owner.status(); owner.start(); children.append(owner.process)
        # Previous explicit reindex finished with a verified graceful stop;
        # no new blocks were mined. Require exact original persisted chain.
        assert (owner.read.attest()['blocks'], owner.read.attest()['bestblockhash']) == (fixture['height'],fixture['tip'])
        assert run_child(root,core,source,'spend')['status'] == 'PASS'
        cases['core-kill-while-spend-unlocked'] = {'status':'PASS',
            'background_sync_failed_closed':True,'normal_close_by_live_session':True,
            'original_wallet_reopened_after_explicit_owned_start':True,'ready_receipt':proof}
        after_mempool = set(_read_cli(prefix+['getrawmempool']))
        gui, report, proof = run_child(root, core, source, 'wait-unlocked', wait=True)
        children.append(gui)
        contended = run_child(root,core,source,'blocked-spend')
        assert contended['status'] == 'DENIED' and gui.poll() is None
        from .runtime_recovery import recover_managed_runtime, RuntimeRecoveryError, RuntimeLease
        try: recover_managed_runtime(root,core,source,PASSWORD,authorized=True)
        except RuntimeRecoveryError as error: assert str(error)=='RUNTIME_SESSION_BUSY'
        else: raise AssertionError('Q05_LIVE_WRITER_RECOVERY_ALLOWED')
        # Identity-scoped descriptor also excludes a separate-directory copy.
        try: RuntimeLease(fixture['wallet_id'])
        except RuntimeRecoveryError: pass
        else: raise AssertionError('Q05_SECOND_WALLET_ID_LEASE_ALLOWED')
        cases['concurrent-wallet-gui-denied'] = {'status':'PASS','second_writer_refused':True,
            'recovery_while_original_gui_alive_denied':True,'wallet_identity_lease_contends':True}
        gui.kill(); assert gui.wait(timeout=15) != 0
        runtime = directory/'wallet-runtime.sqlite'
        assert runtime.is_file()
        residue_hash = hashlib.sha256(runtime.read_bytes()).hexdigest()
        denied = run_child(root, core, source, 'blocked-spend')
        assert denied['status'] == 'DENIED'
        assert hashlib.sha256(runtime.read_bytes()).hexdigest() == residue_hash
        assert anchor.read() == anchored and _vault_files(directory) == sealed
        assert set(_read_cli(prefix+['getrawmempool'])) == after_mempool
        try: recover_managed_runtime(root,core,source,PASSWORD)
        except RuntimeRecoveryError as error: assert str(error)=='RUNTIME_RECOVERY_EXPLICIT_CONSENT_REQUIRED'
        else: raise AssertionError('Q05_RUNTIME_IMPLICIT_RECOVERY_ALLOWED')
        for mode in ('recover-decline','recover-wrong-password'):
            assert run_child(root,core,source,mode)['status']=='DENIED'
            assert hashlib.sha256(runtime.read_bytes()).hexdigest()==residue_hash
            assert anchor.read()==anchored and _vault_files(directory)==sealed
        recovered=run_child(root,core,source,'recover')
        assert recovered['status']=='PASS' and recovered['remains_locked']
        assert not runtime.exists()
        from wam_sp.keystore import unseal
        archive=directory/('runtime-residue-'+residue_hash[:32]+'.enc')
        assert hashlib.sha256(unseal(custody.storage().read(directory,archive.name),PASSWORD,b'checkpoint')).hexdigest()==residue_hash
        assert anchor.read()==anchored and _vault_files(directory)==sealed
        reopened=run_child(root,core,source,'spend')
        assert reopened['status']=='PASS'
        assert anchor.read()==anchored and _vault_files(directory)==sealed
        assert set(_read_cli(prefix+['getrawmempool']))==after_mempool
        cases['unlocked-gui-kill-authenticated-reopen'] = {'status':'PASS',
            'explicit_recovery_and_separate_unlock':True,'original_residue_retained_encrypted':True,
            'missing_consent_wrong_password_declined_recovery_denied':True,
            'original_anchor_vault_unchanged':True,'ready_receipt':proof,
            'recovery_gui_receipt':recovered,'reopened_gui_receipt':reopened,
            'signed_uncertain_reservations_digest':fixture['reservations_digest']}
        return {'schema': 'wam-q05-managed-gui-lifecycle/v1', 'status': 'PASS',
            'platform': receipt['platform'], 'execution': 'FROZEN' if getattr(sys, 'frozen', False) else 'SOURCE_NATIVE',
            'core_version': 'v0.1.11', 'wamd_sha256': receipt['wamd_sha256'],
            'wam_cli_sha256': receipt['wam_cli_sha256'], 'genesis': REGTEST_GENESIS,
            'source_head_sha': os.environ.get('WAM_SOURCE_HEAD'),
            'frozen_binary_sha256': hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest() if getattr(sys, 'frozen', False) else None,
            'wallet_id': fixture['wallet_id'], 'receive_digest': fixture['receive_digest'],
            'original_height': fixture['height'], 'original_tip': fixture['tip'],
            'datadir_and_profile_unchanged': read_exact(root, 'supervisor.profile') == profile and (directory.stat().st_dev, directory.stat().st_ino) == directory_identity,
            'cases': cases, 'failed_private_fixture_retained': True, 'retained_fixture_id': temporary.name,
            'owner_data_accessed': False, 'automatic_rebroadcast': False,
            'synthetic_rpc': False, 'mainnet_allowed': False,
            'full_q05_qualified': False, 'full_v1_qualified': False,
            'physical_accepted': False, 'dev_reviewed': False,
            'pending_scenarios': ['genuine unqualified running Core version GUI scenario (unsupported selected profile refused without contacting it)',
                'divergent or sidecar runtime requires independent review; exact anchored checkpoint recovery only']}
    finally:
        if session is not None: session.close()
        for process in children:
            if process.poll() is None and process is not (owner.process if owner else None):
                process.kill(); process.wait(timeout=15)
        close_owner()
        custody.anchor = native_anchor
        # Intentionally retain FAILED fixture, crash residue and native anchor.
        # No anchor deletion, plaintext removal, alternate runtime or recreation.
        assert all(p.poll() is not None for p in children) and not errors


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument('--core-dir', type=Path, required=True)
    ap.add_argument('--wsp-source', type=Path, required=True)
    known, remaining = ap.parse_known_args()
    try:
        raise SystemExit(child(known.core_dir, known.wsp_source, remaining))
    except Exception as error:
        import traceback
        print('Q05_GUI_CHILD_DENIED:'+type(error).__name__, file=sys.stderr)
        print([frame.lineno for frame in traceback.extract_tb(error.__traceback__)], file=sys.stderr)
        raise SystemExit(2)
