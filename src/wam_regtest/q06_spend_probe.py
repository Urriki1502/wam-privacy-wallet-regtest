"""Packaged macOS ARM64 Q06 owned BIP39 real-Core spend/restore qualification.

One disposable signed-Core REGTEST chain; never production, mainnet or user
keys. Human review remains a separate product gate. Nothing in this probe
should be interpreted as independent security acceptance.
"""
from hashlib import sha256
import json
from pathlib import Path
import platform
import secrets
import sys
import time
import tempfile
from contextlib import nullcontext
import subprocess
from datetime import datetime, timezone

from . import custody
from .bip39_owner_backend import Bip39ReadOnlyBackend
from .wallet_executor import WalletExecutor
from .wsp_live import _pinned_source


def qualify(core, source):
    if sys.platform != "darwin" or platform.machine().lower() != "arm64":
        raise ValueError("Q06_SPEND_MACOS_NATIVE_REQUIRED")
    from .core import verified_core_paths
    _, _, core_receipt = verified_core_paths(core)
    _pinned_source(source)
    from .q05_platforms import DarwinArm64Adapter
    from .desktop import qt_application
    from .bip39_fusion_gui import Bip39FusionWindow
    from .bip39_12 import Bip39Regtest12Keys
    from mnemonic import Mnemonic
    app = qt_application()
    if app.platformName() != "cocoa":
        raise ValueError("Q06_SPEND_NATIVE_COCOA_REQUIRED")
    from .managed_onboarding import assert_unified_welcome_qt
    assert_unified_welcome_qt()
    print("MACOS_Q06_SPEND_STAGE=FROZEN_UNIFIED_WELCOME_PASS",flush=True)
    adapter = DarwinArm64Adapter()
    adapter.enforce_host()

    data = {
        "status": "FAIL",
        "network": "regtest",
        "mainnet_allowed": False,
        "signed_core": True,
        "q06_bip39_spend_confirmed": False,
        "q06_bip39_same_owner_reopen_reserved": False,
        "q06_bip39_same_chain_seed_history_recovery": False,
        "q06_post_reopen_txid_readonly_reconciliation": False,
        "q06_bip39_fresh_mnemonic_full_history_recovery": False,
        "core_sha256": {name:core_receipt[key] for name,key in
                        (('wamd','wamd_sha256'),('wam-cli','wam_cli_sha256'))},
        "wsp_source_commit": 'ac55f13423620252bdbf848c7e8a280c3b84721e',
        "physical_accepted": False,
        "independent_reviewed": False,
    }
    if getattr(sys, 'frozen', False):
        from .q05_package_provenance import read
        data['source_sha'] = read()['candidate_source_sha']
        data['frozen_executable_sha256'] = sha256(Path(sys.executable).read_bytes()).hexdigest()
    else:
        data['source_sha'] = subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    def stage(message):
        data['last_stage'] = message
        print("MACOS_Q06_SPEND_STAGE=" + message, flush=True)

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QPushButton
    def wait_for(predicate, label, timeout=240, expected_denial=None):
        deadline = time.monotonic() + timeout
        next_beat = time.monotonic()
        while not predicate():
            app.processEvents()
            if (window is not None and idle() and window._last_error_code is not None
                    and window._last_error_code != expected_denial):
                data['gui_denied'] = window._last_error_code
                raise ValueError('Q06_GUI_DENIED_' + label)
            now = time.monotonic()
            if now >= next_beat and window is not None:
                next_beat = now + 5
                print(
                    'MACOS_Q06_LIVENESS wait=' + label
                    + ' stage=' + str(data.get('last_stage') or '')
                    + ' modal=' + ('1' if app.activeModalWidget() is not None else '0')
                    + ' worker=' + ('1' if window._worker is not None else '0')
                    + ' busy=' + ('1' if executor.busy else '0')
                    + ' delivering=' + ('1' if window._delivering_result else '0')
                    + ' core=' + ('1' if executor.state.core_alive is True else '0'),
                    flush=True)
            if now >= deadline:
                raise ValueError('Q06_GUI_WAIT_' + label)
            # QTest.qWait holds the Python GIL on this Cocoa binding and can
            # starve the real wallet owner's file/RPC work. Sleep releases it;
            # Qt events are still delivered on the next main-thread iteration.
            time.sleep(0.01)
        app.processEvents()
    def idle():
        return window._worker is None and not executor.busy and not window._delivering_result
    def approve_click(button, caption, done):
        from .shared_network_probe import click_visible_approval
        timer = QTimer()
        timer.setInterval(150)
        def approve():
            # Retry until the labeled button accepts. A single click() can
            # land while the dialog is opening and must not be the last try.
            click_visible_approval(app, caption)
        timer.timeout.connect(approve)
        timer.start()
        try:
            button.click()
            wait_for(lambda: idle() and done(), 'OPERATOR_APPROVAL')
        finally:
            timer.stop()

    # Retain every disposable profile, including failed/uncertain signed state.
    parent = Path.cwd() / '.wam-regtest-temp'
    if not parent.exists():
        custody.create_directory(parent)
    with nullcontext(tempfile.mkdtemp(prefix='q06-spend-frozen-', dir=parent)) as temp:
        root = Path(temp).resolve() / ("wam-fusion-core-" + secrets.token_hex(8))
        custody.create_directory(root)
        password = b"public-disposable-q06-signed-core-spend-only"
        executor = WalletExecutor(lambda: Bip39ReadOnlyBackend(
            root, core, source, _anchor_factory=adapter.make_anchor))
        window = None
        good = False
        try:
            stage("CREATE_START")
            window = Bip39FusionWindow(executor)
            window.show()
            window.start(password, 'create', '')
            wait_for(lambda: idle() and window._backup_flow_active, 'CREATE_BACKUP')
            created = dict(window._backup_result)
            phrase = created["mnemonic_once"]
            if (len(phrase.split()) != 12 or
                    not created["receive_code"].startswith("wamrtsp1")):
                raise ValueError("Q06_SPEND_CREATE_IDENTITY_DENIED")
            stage("CREATE_PASS")
            backup = window.backup_page
            backup._written_check.setChecked(True)
            backup._back_up_now.click()
            for position, field in zip(backup._challenge_positions, backup._verify_inputs):
                field.setText(phrase.split()[position - 1])
            backup._verify_button.click()
            if backup._stack.currentWidget() is not backup._success_page:
                raise ValueError('Q06_GUI_BACKUP_VERIFICATION_DENIED')
            backup._continue_button.click()
            wait_for(lambda: idle() and window._last_verified is not None, 'BACKUP_SYNC')
            data['normal_gui_backup_verified'] = True
            stage('NORMAL_GUI_BACKUP_PASS')
            stage("FUND_START")
            funded = executor.request("mine", timeout=240)
            before = executor.request("snapshot", timeout=120)
            if (before["confirmed_atoms"] != funded["atoms"]
                    or before["available_atoms"] != funded["atoms"]):
                raise ValueError("Q06_SPEND_RECEIVE_DENIED")
            stage("RECEIVE_FUNDED_PASS")
            stage("ACTIVATE_CHECKPOINT_START")
            approve_click(window.activate, 'Approve', lambda: window._spend_enabled)
            active = executor.request('snapshot', timeout=240)
            if (active["signer_allowed"] is not True
                    or active["broadcast_allowed"] is not True
                    or active["mainnet_allowed"] is not False
                    or active["confirmed_atoms"] != funded["atoms"]
                    or active["receive_code"] != created["receive_code"]):
                raise ValueError("Q06_SPEND_NATIVE_ACTIVATION_DENIED")
            stage("ACTIVATE_CHECKPOINT_PASS")
            if (not window.isVisible() or not window.send.isEnabled()
                    or not window.receive.text() == created["receive_code"]):
                raise ValueError("Q06_SPEND_QT_BINDING_DENIED")
            stage("COCOA_SEND_BUTTON_BOUND_PASS")

            with Bip39Regtest12Keys(
                    Mnemonic("english").to_mnemonic(bytes([1] * 16)),
                    source=source, authorized_disposable=True) as payee:
                destination = payee.public_metadata()["receive_code"]
            atoms = 123_456_789
            if atoms < 330 or funded["atoms"] < atoms + 1000:
                raise ValueError("Q06_SPEND_FUNDS_NOT_SPENDABLE")
            stage("PREPARE_START")
            window.recipient_input.setText(destination)
            window.amount_input.setText('3')
            window.fee_input.setText('0.00010000')
            # Match the existing Windows/Linux Q06 negative: genuine native
            # custody + default-Cancel GUI must dispatch no signature and
            # release only this unsigned draft before a later approved payment.
            approve_click(window.send, 'Cancel', lambda: window._last_review is None)
            cancelled = executor.request('snapshot', timeout=240)
            if (window._signed_ready or cancelled['payment_signed']
                    or cancelled['payment_review'] is not None
                    or cancelled['reservation_count'] != active['reservation_count']
                    or cancelled['confirmed_atoms'] != active['confirmed_atoms']):
                raise ValueError('Q06_SPEND_GUI_CANCEL_SIGNED_OR_CHANGED_CUSTODY')
            data['normal_gui_cancel_does_not_sign'] = True
            stage('GUI_UNSIGNED_CANCEL_PASS')
            window.recipient_input.setText(destination)
            window.amount_input.setText('1.23456789')
            window.fee_input.setText('0.00010000')
            # The GUI caller's Decimal precision must never round approved
            # money. The owner executor still validates the exact integer intent.
            from decimal import localcontext
            with localcontext() as decimal_context:
                decimal_context.prec = 6
                approve_click(window.send, 'Approve Sign', lambda: window._signed_ready)
            data['gui_low_decimal_precision_exact_atoms'] = atoms
            data['gui_raw_amount_input'] = '1.23456789'
            prepared = window._last_review
            if (prepared.code != destination or prepared.atoms != atoms
                    or prepared.fee != 10000 or len(prepared.commitment) != 64
                    or prepared.input_count != 1
                    or prepared.change_atoms != funded['atoms'] - atoms - 10000):
                raise ValueError("Q06_SPEND_INTENT_DENIED")
            stage("PREPARE_ANCHORED_PASS")
            signed = window._last_review
            if signed.commitment != prepared.commitment:
                raise ValueError("Q06_SPEND_SIGNED_INTENT_DENIED")
            stage("SIGNED_ANCHORED_PASS")
            approve_click(window.broadcast, 'Approve Broadcast',
                          lambda: window._pending_confirm_txid is not None)
            broadcast = window._pending_confirm_txid
            data['normal_gui_delayed_sign_broadcast'] = True
            data['public_txid'] = broadcast
            if not isinstance(broadcast, str) or len(broadcast) != 64:
                raise ValueError("Q06_SPEND_TXID_DENIED")
            stage("BROADCAST_ANCHORED_PASS")
            # Exercise the same exact-tx confirmation action exposed by
            # the human GUI, not a CI-only alternate mining path.
            approve_click(window.confirm, 'Approve', lambda: window._pending_confirm_txid is None)
            after = executor.request('snapshot', timeout=240)
            confirmed = dict(height=after['height'], txid=broadcast)
            if (after["height"] != confirmed["height"]
                    or after["history_count_shown"] < 2
                    or after["receive_code"] != created["receive_code"]
                    or after['confirmed_atoms'] != funded['atoms'] - atoms - 10000):
                raise ValueError("Q06_SPEND_HISTORY_DENIED")
            data['confirmed_height'] = after['height']
            data['confirmed_tip'] = after['tip']
            data['payment_atoms'] = atoms
            data['fee_atoms'] = prepared.fee
            data['change_atoms'] = prepared.change_atoms
            stage("ONCHAIN_CONFIRMATION_PASS")
            # The frozen GUI must consume the ACTUAL confirmed transaction.
            # Fixed phase markers reveal exact failure without leaking TXIDs.
            stage("FUSION_BROADCAST_RENDER_START")
            stage("FUSION_BROADCAST_RENDER_PASS")
            window._on_ready("snapshot", after)
            stage("FUSION_CONFIRMED_SNAPSHOT_RENDER_PASS")
            app.processEvents()
            stage("FUSION_EVENT_DELIVERY_PASS")
            from .wallet_read import format_wam
            from .fusion_ui import FUSION_NAV_PAGES
            # Fixed public one-token categories. Never log wallet values,
            # seed, receive code, TXID, RPC response or arbitrary UI text.
            if window.navigation.count()!=len(FUSION_NAV_PAGES):
                stage("FUSION_NAVIGATION_DENIED")
                raise ValueError("Q06_FUSION_NAVIGATION_DENIED")
            stage("FUSION_NAVIGATION_PASS")
            if window._last_verified is None:
                stage("FUSION_VERIFIED_SNAPSHOT_NOT_RENDERED")
                raise ValueError("Q06_FUSION_VERIFIED_SNAPSHOT_NOT_RENDERED")
            stage("FUSION_VERIFIED_SNAPSHOT_RENDERED")
            shown=window.overview.balance_value.text()
            formatted=format_wam(after["confirmed_atoms"],grouped=True)
            if shown not in (formatted+" WAM", formatted):
                stage("FUSION_BALANCE_BINDING_DENIED")
                raise ValueError("Q06_FUSION_AFTER_SEND_BALANCE_DENIED")
            stage("FUSION_BALANCE_BINDING_PASS")
            if window.receive_page.code!=created["receive_code"]:
                stage("FUSION_RECEIVE_BINDING_DENIED")
                raise ValueError("Q06_FUSION_AFTER_SEND_RECEIVE_DENIED")
            stage("FUSION_RECEIVE_BINDING_PASS")
            if window.history_page.table.rowCount()<2:
                stage("FUSION_HISTORY_BINDING_DENIED")
                raise ValueError("Q06_FUSION_AFTER_SEND_HISTORY_DENIED")
            stage("FUSION_HISTORY_BINDING_PASS")
            stage("FUSION_REAL_CORE_CONFIRMED_VIEW_PASS")
            if (not window.last_txid.isReadOnly()
                    or window.last_txid.text() != broadcast):
                raise ValueError("Q06_GUI_TXID_PERSISTENT_COPY_DENIED")
            stage("COCOA_BROADCAST_TXID_COPYABLE_PASS")
            images = Path('fusion-ui-review')
            images.mkdir(exist_ok=True)
            data['normal_gui_screenshots'] = {}
            window.reduce_motion.setChecked(True)
            window.navigation.setCurrentRow(0)
            for theme in (0, 1, 2):
                window.appearance_buttons[theme].click()
                for width,height in ((900,630),(1260,810)):
                    window.resize(width,height)
                    app.processEvents()
                    image = images / f'macos-q06-normal-{theme}-{width}x{height}.png'
                    if not window.grab().save(str(image)):
                        raise ValueError('Q06_NORMAL_GUI_SCREENSHOT_DENIED')
                    data['normal_gui_screenshots'][image.name] = sha256(image.read_bytes()).hexdigest()
            from .q06_history_probe import fund_public_history, verify_pages
            stage('GUI_HISTORY_PAGE_BOUNDARY_START')
            extra = fund_public_history(executor._backend.owner, source, created['receive_code'])
            after, data['gui_history_pagination'] = verify_pages(executor, after, extra, window=window)
            stage('GUI_HISTORY_PAGE_BOUNDARY_PASS')
            # Rebuild a NEW scanner from the 12 words against THIS same
            # attested Core. Do not adopt its checkpoint/signing authority.
            stage("SAME_CHAIN_MNEMONIC_RESCAN_START")
            recovery = executor.request("recovery_verify", phrase, timeout=240)
            if (recovery["status"] != "Q06_SAME_CHAIN_BIP39_HISTORY_RESCAN_PASS"
                    or recovery["history_count"] < 2
                    or recovery["confirmed_atoms"] != after["confirmed_atoms"]
                    or recovery["receive_code"] != created["receive_code"]
                    or recovery["same_chain_only"] is not True
                    or recovery["signer_allowed"] is not False
                    or recovery["signed_reservations_restored"] is not False):
                raise ValueError("Q06_SPEND_SAME_CHAIN_RECOVERY_DENIED")
            data["q06_bip39_same_chain_seed_history_recovery"] = True
            stage("SAME_CHAIN_MNEMONIC_RESCAN_PASS")
            # Fail only the NEW independent proof scanner close. The
            # original native wallet must retain authority and reservations;
            # derived recovery keys must still be invalidated best-effort.
            from unittest.mock import patch
            from wam_sp.scanner import Scanner
            original_scanner_close = Scanner.close
            original_keys_close = Bip39Regtest12Keys.close
            held_scanners, closed_recovery_keys = [], []
            def fail_proof_close(scan):
                held_scanners.append(scan)
                raise OSError('Q06_TEST_RECOVERY_CLOSE_FAULT')
            def observe_keys_close(keys):
                original_keys_close(keys)
                closed_recovery_keys.append(keys._closed and not any(keys._seed))
            try:
                with (patch.object(Scanner, 'close', fail_proof_close),
                      patch.object(Bip39Regtest12Keys, 'close', observe_keys_close)):
                    try:
                        executor.request('recovery_verify', phrase, timeout=240)
                    except Exception as error:
                        if error.args != ('Q06_RECOVERY_TEMP_RUNTIME_PRESERVED',):
                            raise ValueError('Q06_RECOVERY_CLOSE_FAULT_CATEGORY_DENIED') from None
                    else:
                        raise ValueError('Q06_RECOVERY_CLOSE_FAULT_NOT_REFUSED')
                if not closed_recovery_keys or not all(closed_recovery_keys):
                    raise ValueError('Q06_RECOVERY_CLOSE_SECRET_INVALIDATION_DENIED')
                preserved = executor.request('snapshot', timeout=240)
                if any(preserved[key] != after[key] for key in
                       ('receive_code','confirmed_atoms','reservation_count','height','tip')):
                    raise ValueError('Q06_RECOVERY_CLOSE_NATIVE_STATE_CHANGED')
            finally:
                for scan in held_scanners:
                    original_scanner_close(scan)
            data['recovery_close_failure_keys_invalidated_native_state_preserved'] = True
            stage('RECOVERY_CLOSE_FAILURE_INVALIDATION_PASS')
            data["q06_bip39_spend_confirmed"] = True
            data["txid_sha256"] = sha256(broadcast.encode("ascii")).hexdigest()
            data["receive_sha256"] = sha256(
                created["receive_code"].encode("ascii")).hexdigest()

            for cycle in range(3):
                window.custody_switch.click()
                wait_for(lambda: idle() and executor.state.locked, 'LOCK')
                if cycle == 0:
                    timer = QTimer()
                    timer.setInterval(150)
                    def cancel_unlock_dialog():
                        dialog = app.activeModalWidget()
                        if dialog is not None and hasattr(dialog, 'password_input'):
                            for button in dialog.findChildren(QPushButton):
                                if button.text() == 'Cancel':
                                    button.click()
                                    timer.stop()
                    timer.timeout.connect(cancel_unlock_dialog)
                    timer.start()
                    window.custody_switch.click()
                    timer.stop()
                    if not executor.state.locked or window._ready or window._spend_enabled:
                        raise ValueError('Q06_UNLOCK_CANCEL_GRANTED_AUTHORITY')
                    data['normal_gui_unlock_cancel_retains_locked'] = True
                    try:
                        executor.request('unlock', b'wrong-disposable-password', False, timeout=120)
                    except Exception:
                        if not executor.state.locked:
                            raise ValueError('Q06_WRONG_PASSWORD_OPENED')
                    else:
                        raise ValueError('Q06_WRONG_PASSWORD_ACCEPTED')
                timer = QTimer()
                timer.setInterval(150)
                def unlock_dialog():
                    dialog = app.activeModalWidget()
                    if dialog is not None and hasattr(dialog, 'password_input'):
                        dialog.password_input.setText(password.decode())
                        for button in dialog.findChildren(QPushButton):
                            if button.text() == 'Unlock':
                                button.click()
                                timer.stop()
                timer.timeout.connect(unlock_dialog)
                timer.start()
                window.custody_switch.click()
                timer.stop()
                wait_for(lambda: idle() and not executor.state.locked
                         and window._spend_enabled and window._last_verified is not None, 'UNLOCK')
                current = executor.request('snapshot', timeout=240)
                if (current['receive_code'] != created['receive_code']
                        or current['confirmed_atoms'] != after['confirmed_atoms']
                        or current['reservation_count'] != after['reservation_count']):
                    raise ValueError('Q06_UNLOCK_IDENTITY_OR_RESERVATION_CHANGED')
            data['normal_gui_repeated_unlock'] = True
            stage('NORMAL_GUI_LOCK_UNLOCK_PASS')
            evidence_dir = executor._backend.owner.directory / 'q06-payment-evidence'
            if len(list(evidence_dir.glob('*.enc'))) != 3:
                raise ValueError('Q06_SIGNED_EVIDENCE_MISSING')
            from wam_sp.keystore import unseal
            evidence = [json.loads(unseal(custody.storage().read(evidence_dir, p.name),
                         password, b'recovery')) for p in evidence_dir.glob('*.enc')]
            if ({e['stage'] for e in evidence} != {'signed', 'uncertain', 'broadcast'}
                    or any(e['txid'] != broadcast for e in evidence)
                    or len({e['signed_psbt'] for e in evidence}) != 1):
                raise ValueError('Q06_SIGNED_EVIDENCE_MISMATCH')
            data['encrypted_signed_psbt_retained'] = True
            executor.request('lock', timeout=90)
            stage("LOCKED_ORIGINAL_PASS")
            reopened = executor.request("open", password, "reopen", "", timeout=120)
            if (reopened["receive_code"] != created["receive_code"]
                    or reopened["mnemonic_once"]):
                raise ValueError("Q06_SPEND_REOPEN_IDENTITY_DENIED")
            recovered = executor.request("activate", timeout=240)
            if (recovered["height"] != after["height"]
                    or recovered["confirmed_atoms"] != after["confirmed_atoms"]
                    or recovered["reservation_count"] != after["reservation_count"]
                    or recovered["history_count_shown"] < 2
                    or recovered["receive_code"] != created["receive_code"]):
                raise ValueError("Q06_SPEND_REOPEN_STATE_DENIED")
            data["q06_bip39_same_owner_reopen_reserved"] = True
            stage("REOPEN_ANCHORED_RESERVATION_PASS")
            stage("POST_REOPEN_TXID_INSPECTION_START")
            resolved=executor.request("inspect_confirmed",broadcast,timeout=240)
            unknown=executor.request("inspect_confirmed","f"*64,timeout=240)
            if (resolved["status"]!="Q06_CONFIRMED_IN_VERIFIED_HISTORY"
                    or resolved["txid"]!=broadcast
                    or resolved["write_attempted"] is not False
                    or resolved["broadcast_allowed"] is not False
                    or unknown["status"]!="Q06_TX_NOT_IN_CONFIRMED_HISTORY"
                    or unknown["write_attempted"] is not False):
                raise ValueError("Q06_POST_REOPEN_TXID_INSPECTION_DENIED")
            data["q06_post_reopen_txid_readonly_reconciliation"]=True
            stage("POST_REOPEN_TXID_INSPECTION_PASS")
            executor.request("quit", timeout=90)
            if not executor.join(15) or not executor.closed:
                raise ValueError("Q06_SPEND_OWNED_SHUTDOWN_DENIED")
            # A new owner/executor must reopen the SAME persistent profile and
            # start a new original Popen. Reuse the existing test keychain;
            # never recreate anchors or switch to an empty chain.
            window._poll.stop()
            window.hide()
            keychain = root / 'q05-disposable.keychain-db'
            executor = WalletExecutor(lambda: Bip39ReadOnlyBackend(
                root, core, source, keychain=keychain))
            window = Bip39FusionWindow(executor)
            window.show()
            window.start(b'wrong-disposable-initial-password', 'reopen', '')
            wait_for(lambda: idle() and window._last_error_code == 'WALLET_UNLOCK_REFUSED',
                     'INITIAL_PASSWORD_REFUSAL', expected_denial='WALLET_UNLOCK_REFUSED')
            if (not executor.state.locked or not window.unlock.isEnabled()
                    or window._ready or window._spend_enabled):
                raise ValueError('Q06_INITIAL_PASSWORD_RETRY_SCOPE_DENIED')
            timer = QTimer()
            timer.setInterval(150)
            timer.timeout.connect(unlock_dialog)
            timer.start()
            window.custody_switch.click()
            timer.stop()
            wait_for(lambda: idle() and window._ready, 'RESTART_REOPEN')
            data['normal_gui_initial_wrong_password_retry'] = True
            if window._spend_enabled:
                raise ValueError('Q06_RESTART_UNAPPROVED_SIGNER')
            # Reopen authenticates only the seed until explicit activation.
            # Lock/Unlock here must not auto-scan over native reservations.
            window.custody_switch.click()
            wait_for(lambda: idle() and executor.state.locked, 'SEED_ONLY_LOCK')
            timer = QTimer()
            timer.setInterval(150)
            timer.timeout.connect(unlock_dialog)
            timer.start()
            window.custody_switch.click()
            timer.stop()
            wait_for(lambda: idle() and not executor.state.locked, 'SEED_ONLY_UNLOCK')
            if (window._spend_enabled or window._last_verified is not None
                    or window._pending_action is not None):
                raise ValueError('Q06_SEED_ONLY_UNLOCK_AUTHORITY_DENIED')
            data['normal_gui_seed_only_anchored_unlock'] = True
            stage('SEED_ONLY_ANCHORED_UNLOCK_PASS')
            approve_click(window.activate, 'Approve', lambda: window._spend_enabled)
            restart = executor.request('snapshot', timeout=240)
            if any(restart[key] != after[key] for key in
                   ('height','tip','receive_code','confirmed_atoms','reservation_count','history_count_shown')):
                raise ValueError('Q06_RESTART_HISTORY_OR_RESERVATION_CHANGED')
            observed = executor.request('inspect_confirmed', broadcast, timeout=240)
            if observed['status'] != 'Q06_CONFIRMED_IN_VERIFIED_HISTORY':
                raise ValueError('Q06_RESTART_CONFIRMED_TX_MISSING')
            data['same_profile_core_restart'] = True
            stage('SAME_PROFILE_CORE_RESTART_PASS')
            # One explicit close fault on this NEW disposable session only.
            # Keep native/signed evidence and prove the real keyring closes
            # even when SQLite close cannot run. No secret bytes are emitted.
            from unittest.mock import patch
            session = executor._backend._spend_session
            scanner, ring = session.scanner, session.ring
            original_close = scanner.close
            runtime_hash = sha256(session.runtime.read_bytes()).hexdigest()
            reservations = tuple(tuple(row) for row in scanner.store.db.execute(
                'SELECT * FROM reservations ORDER BY txid,vout'))
            anchor = session.vault.anchor.read()
            try:
                with patch.object(scanner, 'close', side_effect=OSError('Q06_TEST_CLOSE_FAULT')):
                    try:
                        executor.request('lock', timeout=90)
                    except Exception as error:
                        if error.args != ('Q06_SPEND_RUNTIME_PRESERVED',):
                            raise ValueError('Q06_LOCK_FAULT_CATEGORY_DENIED') from None
                    else:
                        raise ValueError('Q06_LOCK_FAULT_NOT_REFUSED')
                if (not executor.state.locked or not executor.state.faulted
                        or not ring._closed or any(ring._seed)
                        or session._password is not None
                        or executor._backend._secret is not None
                        or sha256(session.runtime.read_bytes()).hexdigest() != runtime_hash
                        or session.vault.anchor.read() != anchor
                        or tuple(tuple(row) for row in scanner.store.db.execute(
                            'SELECT * FROM reservations ORDER BY txid,vout')) != reservations):
                    raise ValueError('Q06_LOCK_FAULT_SECRET_OR_AUTHORITY_DENIED')
            finally:
                # Release only the deliberately held SQLite connection in
                # this fixture. Runtime/checkpoint/reservations stay retained.
                original_close()
            data['native_lock_failure_key_invalidation_verified'] = True
            data['native_lock_failure_reservations_anchor_runtime_preserved'] = True
            stage('NATIVE_LOCK_FAILURE_INVALIDATION_PASS')
            executor.request('quit', timeout=90)
            if not executor.join(15) or not executor.closed:
                raise ValueError('Q06_RESTART_SHUTDOWN_DENIED')
            stage("CLEAN_CORE_SHUTDOWN_PASS")
            data['empty_owned_core_loss_gui'] = _qualify_empty_core_loss(
                core, source, adapter, data['source_sha'])
            stage('EMPTY_OWNED_CORE_LOSS_GUI_PASS')
            data["status"] = "Q06_NATIVE_BIP39_SEND_CONFIRM_REOPEN_PASS"
            data['timestamp_utc'] = datetime.now(timezone.utc).isoformat()
            good = True
            return data
        finally:
            if window is not None:
                window._poll.stop()
                window.hide()
                if good:
                    from PySide6.QtCore import QCoreApplication, QEvent
                    window.deleteLater()
                    QCoreApplication.sendPostedEvents(
                        None, QEvent.Type.DeferredDelete)
                    app.processEvents()
            # Preserve the exact Core/chain/native state on an uncertain
            # failure. No force-kill, orphan sweep, automatic replay or retry.
            if not good and not executor.busy and not executor.closed:
                try:
                    executor.request("quit", timeout=45)
                    executor.join(15)
                except Exception:
                    stage("UNCERTAIN_OWNER_PRESERVED")
            if not good:
                data['timestamp_utc'] = datetime.now(timezone.utc).isoformat()
                data['profile_retained'] = str(root)
                (root.parent / 'failure-public.json').write_text(json.dumps(data,indent=2)+'\n')
            phrase = None


def _qualify_empty_core_loss(core, source, adapter, source_sha):
    """One explicit original-Popen crash, only on a NEW EMPTY test wallet.

    No application/foreign-owner kill, existing data, transaction, anchor
    replacement or uncertain reservation recovery. The original supervisor
    survives and alone holds the capability for explicit Core recovery.
    """
    from .desktop import qt_application
    from .bip39_fusion_gui import Bip39FusionWindow
    from .rpc_scope import identity
    app = qt_application()
    if app.platformName() != 'cocoa':
        raise ValueError('Q06_CORE_LOSS_NATIVE_COCOA_REQUIRED')
    parent = Path.cwd() / '.wam-regtest-temp'
    if not parent.exists():
        custody.create_directory(parent)
    root = parent / ('wam-fusion-core-' + secrets.token_hex(8))
    custody.create_directory(root)
    password = b'public-disposable-q06-empty-core-loss-only'
    executor = WalletExecutor(lambda: Bip39ReadOnlyBackend(
        root, core, source, _anchor_factory=adapter.make_anchor))
    window = None
    record = dict(status='FAIL', source_sha=source_sha, synthetic_rpc=False,
                  frozen=bool(getattr(sys, 'frozen', False)),
                  max_crashes=1, empty_profile_only=True,
                  mainnet_allowed=False, physical_accepted=False)
    begin = time.monotonic()
    try:
        opened = executor.request('open', password, 'create', '', timeout=120)
        words = opened['mnemonic_once'].split()
        challenge = executor.request('backup_challenge')
        if executor.request('backup_verify', challenge['challenge_id'],
                tuple(words[p - 1] for p in challenge['positions'])) is not True:
            raise ValueError('Q06_CORE_LOSS_BACKUP_DENIED')
        words = None
        opened = dict(opened, mnemonic_once='', backup_status='verified', checkpoint_present=True)
        baseline = executor.request('activate', timeout=120)
        if (baseline['height'] != 0 or any(baseline[key] != 0 for key in
                ('confirmed_atoms','available_atoms','reservation_count'))):
            raise ValueError('Q06_CORE_LOSS_NONEMPTY_FIXTURE_DENIED')
        window = Bip39FusionWindow(executor)
        window._on_ready('open', opened)
        window._on_ready('activate', baseline)
        window.show()
        owner = executor._backend.owner
        process = owner.process
        scope = identity(owner.directory)
        if (process is None or process.poll() is not None
                or owner.binding.process is not process
                or scope is None or scope.binding.process is not process):
            raise ValueError('Q06_CORE_LOSS_ORIGINAL_POPEN_REQUIRED')
        owner.binding._assert_image()
        authority = root.parent / ('core-loss-authority-' + root.name + '.json')
        with authority.open('x') as output:
            json.dump(dict(source_sha=source_sha, original_popen_pid=process.pid,
                action='ONE_EXPLICIT_CRASH_NEW_EMPTY_REGTEST_CORE_ONLY',
                original_binding_verified=True, no_transactions_or_reservations=True), output)
        process.kill()  # Deliberate disposable fault through retained capability.
        process.wait(timeout=10)
        if process.returncode != -9:
            raise ValueError('Q06_CORE_LOSS_CRASH_NOT_OBSERVED')
        window.sync.click()
        deadline = time.monotonic() + 30
        while (window._worker is not None or executor.busy or window._delivering_result
                or window._last_error_code is None):
            app.processEvents()
            if time.monotonic() >= deadline:
                raise ValueError('Q06_CORE_LOSS_GUI_WAIT_DENIED')
            time.sleep(.01)
        if (window._last_error_code != 'WALLET_CORE_IDENTITY_DENIED'
                or executor.state.core_alive is not False
                or window.send.isEnabled() or window.broadcast.isEnabled()
                or window.overview.go_send.isEnabled() or window._last_verified is not None):
            raise ValueError('Q06_CORE_LOSS_CACHED_GUI_AUTHORITY_DENIED')
        executor.request('lock', timeout=30)
        executor.request('control', 'recover-dead', timeout=120)
        if not executor.state.locked or owner.process is process:
            raise ValueError('Q06_CORE_RECOVERY_GRANTED_WALLET_AUTHORITY')
        reopened = executor.request('open', password, 'reopen', '', timeout=120)
        if reopened['signer_allowed'] or reopened['receive_code'] != baseline['receive_code']:
            raise ValueError('Q06_CORE_LOSS_REOPEN_SCOPE_DENIED')
        restored = executor.request('activate', timeout=120)
        if any(restored[key] != baseline[key] for key in
                ('receive_code','height','tip','confirmed_atoms','available_atoms','reservation_count')):
            raise ValueError('Q06_CORE_LOSS_CUSTODY_CONTINUITY_DENIED')
        if time.monotonic() - begin > 180:
            raise ValueError('Q06_CORE_LOSS_TIME_BUDGET')
        record.update(status='PASS', original_popen_only=True, cached_send_revoked=True,
                      unverified_balance_hidden=True, explicit_core_recovery_only=True,
                      seed_reopen_not_spending_authority=True, same_identity_native_chain=True)
        return record
    finally:
        if window is not None:
            window._poll.stop()
            window.hide()
            window.deleteLater()
            app.processEvents()
        if not executor.closed:
            try:
                executor.request('quit', timeout=120)
                record['owner_shutdown_verified'] = executor.join(15) and executor.closed
            except Exception:
                record['owner_shutdown_verified'] = False
        record['seconds'] = time.monotonic() - begin
        with (root.parent / ('core-loss-result-' + root.name + '.json')).open('x') as output:
            json.dump(record, output, indent=2)
        if not record.get('owner_shutdown_verified'):
            with (root.parent / ('core-loss-failure-' + root.name + '.json')).open('x') as output:
                json.dump(record, output, indent=2)
            raise ValueError('Q06_CORE_LOSS_OWNER_RETAINED') from None


_NETWORK_WRITES = frozenset((
    'sendrawtransaction', 'generatetoaddress', 'generateblock', 'generate', 'submitblock',
    'addnode', 'prioritisetransaction', 'sendtoaddress', 'sendmany', 'invalidateblock',
    'reconsiderblock', 'abandontransaction', 'setban', 'disconnectnode'))


def _qualify_recovered_unsigned_cancel(core, source, adapter, source_sha):
    """NEW disposable wallet: unsigned draft -> clean shutdown -> reopen -> Qt Cancel.

    The actual Cancel button is the only release. Proves no signature, no
    network write, same identity/chain/confirmed balance, native generation
    advance, available restored only afterwards, and restart consistency.
    """
    from unittest.mock import patch
    from .desktop import qt_application
    from .bip39_fusion_gui import Bip39FusionWindow
    from .bip39_12 import Bip39Regtest12Keys
    from .qualification_gui import click_visible_approval
    from .wallet_session import WalletCoreCli
    import wam_sp.wallet as wsp_wallet
    from PySide6.QtCore import QTimer
    app = qt_application()
    if app.platformName() != 'cocoa':
        raise ValueError('Q06_RECOVERED_CANCEL_NATIVE_COCOA_REQUIRED')
    parent = Path.cwd() / '.wam-regtest-temp'
    if not parent.exists():
        custody.create_directory(parent)
    root = parent / ('wam-fusion-core-' + secrets.token_hex(8))
    custody.create_directory(root)
    password = b'public-disposable-q06-recovered-unsigned-cancel-only'
    keychain = root / 'q05-disposable.keychain-db'
    record = dict(status='FAIL', source_sha=source_sha, synthetic_rpc=False,
                  frozen=bool(getattr(sys, 'frozen', False)), mainnet_allowed=False,
                  physical_accepted=False, profile=root.name)
    begin = time.monotonic()
    state = {'executor': WalletExecutor(lambda: Bip39ReadOnlyBackend(
        root, core, source, _anchor_factory=adapter.make_anchor)), 'window': None}

    def request(*args, timeout=240):
        return state['executor'].request(*args, timeout=timeout)

    def restart():
        request('quit', timeout=120)
        if not state['executor'].join(15) or not state['executor'].closed:
            raise ValueError('Q06_RECOVERED_CANCEL_SHUTDOWN_DENIED')
        state['executor'] = WalletExecutor(lambda: Bip39ReadOnlyBackend(
            root, core, source, keychain=keychain))

    def ledger():
        session = state['executor']._backend._spend_session
        return (tuple(tuple(r) for r in session.scanner.store.db.execute(
            'SELECT * FROM reservations ORDER BY txid,vout')), session.vault.anchor.read())

    def mempool():
        owner = state['executor']._backend.owner
        observer = WalletCoreCli(owner.cli, owner.directory)
        try:
            return observer._call('getblockhash', [0]), observer._call('getrawmempool', [])
        finally:
            if observer._transport is not None:
                observer._transport.close()

    try:
        opened = request('open', password, 'create', '', timeout=120)
        words = opened['mnemonic_once'].split()
        challenge = request('backup_challenge')
        if request('backup_verify', challenge['challenge_id'],
                   tuple(words[p - 1] for p in challenge['positions'])) is not True:
            raise ValueError('Q06_RECOVERED_CANCEL_BACKUP_DENIED')
        words = opened = None
        request('mine')
        base = request('activate')
        if base['available_atoms'] != base['confirmed_atoms'] or base['confirmed_atoms'] <= 0:
            raise ValueError('Q06_RECOVERED_CANCEL_FUNDING_DENIED')
        with Bip39Regtest12Keys('abandon ' * 11 + 'about', source=source,
                                authorized_disposable=True) as payee:
            destination = payee.public_metadata()['receive_code']
        request('prepare', destination, 123_456_789, 10_000)
        rows, anchor = ledger()
        if not rows or {r[3] for r in rows} != {'draft'} or len({r[2] for r in rows}) != 1:
            raise ValueError('Q06_RECOVERED_CANCEL_DRAFT_DENIED')
        restart()
        window = state['window'] = Bip39FusionWindow(state['executor'])
        executor = state['executor']
        window.show()

        def idle():
            return window._worker is None and not executor.busy and not window._delivering_result

        def wait_for(predicate, label, timeout=240):
            deadline = time.monotonic() + timeout
            while not predicate():
                app.processEvents()
                if idle() and window._last_error_code is not None:
                    record['gui_denied'] = window._last_error_code
                    raise ValueError('Q06_RECOVERED_CANCEL_GUI_DENIED_' + label)
                if time.monotonic() >= deadline:
                    raise ValueError('Q06_RECOVERED_CANCEL_WAIT_' + label)
                time.sleep(0.01)
            app.processEvents()

        window.start(password, 'reopen', '')
        wait_for(lambda: idle() and window._ready, 'REOPEN')
        if window._spend_enabled or window.cancel.isEnabled():
            raise ValueError('Q06_RECOVERED_CANCEL_UNAPPROVED_SCOPE')
        timer = QTimer()
        timer.setInterval(150)
        timer.timeout.connect(lambda: click_visible_approval(app, 'Approve'))
        timer.start()
        try:
            window.activate.click()
            wait_for(lambda: idle() and window._spend_enabled, 'ACTIVATE')
        finally:
            timer.stop()
        wait_for(lambda: idle() and window._recovered_unsigned_cancel, 'RECOVERED_FLAG')
        window._set_actions()
        reopened_rows, reopened_anchor = ledger()
        after = request('snapshot')
        session = executor._backend._spend_session
        if (reopened_rows != rows or reopened_anchor[0] < anchor[0]
                or session._prepared is not None or session._signed is not None
                or after['available_atoms'] != 0
                or after['confirmed_atoms'] != base['confirmed_atoms']
                or after['receive_code'] != base['receive_code']
                or not window.cancel.isEnabled() or window.send.isEnabled()
                or window.broadcast.isEnabled()):
            raise ValueError('Q06_RECOVERED_CANCEL_REOPEN_STATE_DENIED')
        methods, signs = [], []
        o_call, o_raw, o_sign = WalletCoreCli.call, WalletCoreCli._call, wsp_wallet.Signer.sign

        def call(rpc, method, params=None):
            methods.append(method)
            return o_call(rpc, method, params)

        def raw(rpc, method, params=None):
            methods.append(method)
            return o_raw(rpc, method, params)

        def sign(*args, **kwargs):
            signs.append(1)
            return o_sign(*args, **kwargs)

        with (patch.object(WalletCoreCli, 'call', call), patch.object(WalletCoreCli, '_call', raw),
              patch.object(wsp_wallet.Signer, 'sign', sign)):
            window.cancel.click()
            wait_for(lambda: idle() and not window._recovered_unsigned_cancel
                     and window._pending_action is None, 'QT_CANCEL')
            final = request('snapshot')
            final_rows, final_anchor = ledger()
            genesis, pool = mempool()
            try:
                request('cancel', timeout=120)
            except Exception as error:
                repeated = error.args[0] if error.args else type(error).__name__
            else:
                raise ValueError('Q06_RECOVERED_CANCEL_REPEAT_NOT_REFUSED')
        writes = sorted(set(methods) & _NETWORK_WRITES)
        if (final_rows != () or final_anchor[0] <= reopened_anchor[0]
                or ledger()[1] != final_anchor or repeated != 'WALLET_ONLY_UNSIGNED_DRAFT_CAN_CANCEL'
                or final['available_atoms'] != base['available_atoms']
                or final['confirmed_atoms'] != base['confirmed_atoms']
                or final['receive_code'] != base['receive_code']
                or (final['height'], final['tip']) != (after['height'], after['tip'])
                or final['recovered_unsigned_cancel_available'] is not False
                or window.cancel.isEnabled() or not window.send.isEnabled()
                or pool != [] or signs or writes):
            raise ValueError('Q06_RECOVERED_CANCEL_RESULT_DENIED')
        window._poll.stop()
        window.hide()
        restart()
        request('open', password, 'reopen', '', timeout=120)
        again = request('activate')
        again_rows, again_anchor = ledger()
        if (again_rows != () or again_anchor[0] < final_anchor[0]
                or again['available_atoms'] != base['available_atoms']
                or again['confirmed_atoms'] != base['confirmed_atoms']
                or again['recovered_unsigned_cancel_available'] is not False
                or mempool() != (genesis, [])):
            raise ValueError('Q06_RECOVERED_CANCEL_RESTART_DENIED')
        if time.monotonic() - begin > 420:
            raise ValueError('Q06_RECOVERED_CANCEL_TIME_BUDGET')
        record.update(status='PASS', actual_qt_cancel_button=True, reservation_state_before='draft',
                      reservation_rows_before=len(rows), anchor_generation=[anchor[0], reopened_anchor[0],
                      final_anchor[0], again_anchor[0]], confirmed_atoms=final['confirmed_atoms'],
                      available_restored_atoms=final['available_atoms'], repeated_cancel=repeated,
                      sign_calls=0, network_writes=[], mempool_empty=True, restart_consistent=True,
                      rpc_methods_during_cancel=sorted(set(methods)))
        return record
    finally:
        window = state['window']
        if window is not None:
            window._poll.stop()
            window.hide()
            window.deleteLater()
            app.processEvents()
        executor = state['executor']
        if not executor.closed:
            try:
                executor.request('quit', timeout=120)
                record['owner_shutdown_verified'] = executor.join(15) and executor.closed
            except Exception:
                record['owner_shutdown_verified'] = False
        else:
            record['owner_shutdown_verified'] = True
        record['seconds'] = time.monotonic() - begin
        with (parent / ('recovered-cancel-result-' + root.name + '.json')).open('x') as output:
            json.dump(record, output, indent=2)
        if not record.get('owner_shutdown_verified'):
            raise ValueError('Q06_RECOVERED_CANCEL_OWNER_RETAINED') from None


def run(core, source):
    try:
        receipt = qualify(core, source)
        from .q06_same_chain_restore_probe import qualify as restore_same_chain
        from .q05_platforms import DarwinArm64Adapter
        restored = restore_same_chain(core,source,Path.cwd(),DarwinArm64Adapter())
        receipt['fresh_profile_same_chain_history'] = restored
        if (restored['status']!='FRESH_PROFILE_SAME_CHAIN_HISTORY_RESTORE_PASS'
                or restored['all_original_owners_shutdown_verified'] is not True):
            raise ValueError('Q06_MAC_FRESH_SAME_CHAIN_RESTORE_DENIED')
        receipt['fresh_same_chain_profile_full_history_recovered'] = True
        recovered = _qualify_recovered_unsigned_cancel(
            core, source, DarwinArm64Adapter(), receipt['source_sha'])
        receipt['recovered_unsigned_cancel'] = recovered
        if recovered['status'] != 'PASS' or recovered['owner_shutdown_verified'] is not True:
            raise ValueError('Q06_MAC_RECOVERED_UNSIGNED_CANCEL_DENIED')
        with Path("q06-frozen-spend-evidence.json").open("x") as output:
            json.dump(receipt, output, sort_keys=True, indent=2)
            output.write("\n")
        if (receipt["status"] != "Q06_NATIVE_BIP39_SEND_CONFIRM_REOPEN_PASS"
                or receipt["q06_bip39_spend_confirmed"] is not True
                or receipt["q06_bip39_same_owner_reopen_reserved"] is not True):
            raise ValueError("Q06_SPEND_NOT_QUALIFIED")
        print("MACOS_Q06_NATIVE_BIP39_SEND_CONFIRM_REOPEN_PASS", flush=True)
        return 0
    except Exception:
        print("MACOS_Q06_NATIVE_BIP39_SEND_CONFIRM_REOPEN_DENIED", flush=True)
        return 2
