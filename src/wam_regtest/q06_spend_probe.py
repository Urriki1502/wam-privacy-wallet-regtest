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
        data['source_sha'] = read()['source_head_sha']
        data['frozen_executable_sha256'] = sha256(Path(sys.executable).read_bytes()).hexdigest()
    else:
        data['source_sha'] = subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    def stage(message):
        data['last_stage'] = message
        print("MACOS_Q06_SPEND_STAGE=" + message, flush=True)

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QDialog, QPushButton
    from PySide6.QtTest import QTest
    def wait_for(predicate, label, timeout=240):
        deadline = time.monotonic() + timeout
        while not predicate():
            app.processEvents()
            if (window is not None and idle() and window._last_error_code is not None):
                raise ValueError('Q06_GUI_DENIED_' + label)
            if time.monotonic() >= deadline:
                raise ValueError('Q06_GUI_WAIT_' + label)
            # QTest.qWait holds the Python GIL on this Cocoa binding and can
            # starve the real wallet owner's file/RPC work. Sleep releases it;
            # Qt events are still delivered on the next main-thread iteration.
            time.sleep(0.01)
        app.processEvents()
    def idle():
        return window._worker is None and not executor.busy and not window._delivering_result
    def approve_click(button, caption, done):
        timer = QTimer()
        timer.setInterval(150)
        def approve():
            dialog = app.activeModalWidget()
            if isinstance(dialog, QDialog):
                for control in dialog.findChildren(QPushButton):
                    if control.text() == caption:
                        control.click()
                        timer.stop()
                        break
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
            atoms = 300_000_000
            if atoms < 330 or funded["atoms"] < atoms + 1000:
                raise ValueError("Q06_SPEND_FUNDS_NOT_SPENDABLE")
            stage("PREPARE_START")
            window.recipient_input.setText(destination)
            window.amount_input.setText('3')
            window.fee_input.setText('0.00010000')
            approve_click(window.send, 'Approve Sign', lambda: window._signed_ready)
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
            # Fixed public one-token categories. Never log wallet values,
            # seed, receive code, TXID, RPC response or arbitrary UI text.
            if window.navigation.count()!=6:
                stage("FUSION_NAVIGATION_DENIED")
                raise ValueError("Q06_FUSION_NAVIGATION_DENIED")
            stage("FUSION_NAVIGATION_PASS")
            if window._last_verified is None:
                stage("FUSION_VERIFIED_SNAPSHOT_NOT_RENDERED")
                raise ValueError("Q06_FUSION_VERIFIED_SNAPSHOT_NOT_RENDERED")
            stage("FUSION_VERIFIED_SNAPSHOT_RENDERED")
            if (window.overview.balance_value.text()
                    !=format_wam(after["confirmed_atoms"],grouped=True)+" WAM"):
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
            data["q06_bip39_spend_confirmed"] = True
            data["txid_sha256"] = sha256(broadcast.encode("ascii")).hexdigest()
            data["receive_sha256"] = sha256(
                created["receive_code"].encode("ascii")).hexdigest()

            for cycle in range(3):
                window.custody_switch.click()
                wait_for(lambda: idle() and executor.state.locked, 'LOCK')
                if cycle == 0:
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
            window.start(password, 'reopen', '')
            wait_for(lambda: idle() and window._ready, 'RESTART_REOPEN')
            if window._spend_enabled:
                raise ValueError('Q06_RESTART_UNAPPROVED_SIGNER')
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
            executor.request('quit', timeout=90)
            if not executor.join(15) or not executor.closed:
                raise ValueError('Q06_RESTART_SHUTDOWN_DENIED')
            stage("CLEAN_CORE_SHUTDOWN_PASS")
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


def run(core, source):
    try:
        receipt = qualify(core, source)
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
