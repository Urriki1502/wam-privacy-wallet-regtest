"""Frozen Windows/Linux Q06 REGTEST integration qualification.

Real owned Core, pinned WSP and native custody. One fresh disposable profile;
no RPC mocks, no foreign checkpoint, no mainnet, no owner merge authorization.
Native GUI binding is checked on desktop builds; Linux headless omits Qt.
"""
from hashlib import sha256
import json
from pathlib import Path
import platform
import re
import sys
import time

from .bip39_12 import Bip39Regtest12Keys
from .bip39_owner_backend import Bip39ReadOnlyBackend
from .q05_platforms import detect_adapter
from .wallet_executor import WalletExecutor
from .wsp_live import _pinned_source
from .core import verified_core_paths


class Q06PlatformQualificationError(ValueError):
    pass


def qualify(core, source, root, receipt, *, confirmed=False,
            linux_manifest=None, linux_witness=None, headless=False):
    if (confirmed is not True or not getattr(sys, "frozen", False)
            or platform.system() not in ("Windows", "Linux")
            or not root.is_absolute() or not receipt.is_absolute()
            or root.exists() or root.is_symlink() or receipt.exists() or receipt.is_symlink()
            or not re.fullmatch(r"wam-fusion-core-[0-9a-f]{16}", root.name)
            or not root.parent.is_dir()
            or type(headless) is not bool
            or (platform.system() == "Windows" and headless)):
        raise Q06PlatformQualificationError("Q06_PLATFORM_SCOPE_DENIED")
    adapter = detect_adapter()
    adapter.enforce_host()
    _pinned_source(source)
    stage = "PREFLIGHT"
    record = {
        "schema": "q06-native-frozen-owned-core/v1",
        "status": "FAIL", "failure_stage": stage,
        "platform": adapter.platform_id, "frozen": True,
        "headless": headless, "synthetic_rpc": False,
        "official_signed_core": adapter.official_signed,
        "native_custody": True, "mainnet_allowed": False,
        "physical_accepted": False, "independent_reviewed": False,
        "same_chain_mnemonic_history_recovered": False,
        "fresh_chain_full_history_recovered": False,
        "fresh_profile_seed_identity_restored": False,
        "same_owner_reopened": False, "post_reopen_txid_verified": False,
        "signed_core_transaction_confirmed": False,
        "native_gui_checked": False,
    }
    exe = Path(sys.executable)
    if not exe.is_file():
        raise Q06PlatformQualificationError("Q06_PLATFORM_FROZEN_EXECUTABLE_MISSING")
    record["frozen_executable_sha256"] = sha256(exe.read_bytes()).hexdigest()
    executor = None
    restored_executor = None
    window = None
    good = False
    phrase = None
    approval_failure = []
    def step(name):
        nonlocal stage
        stage = name
        record["failure_stage"] = name
        print("Q06_" + adapter.platform_id.upper().replace("-", "_")
              + "_STAGE=" + name, flush=True)
    def idle():
        return (window._worker is None and not executor.busy
                and not window._delivering_result)

    def wait_gui(predicate, label):
        deadline = time.monotonic() + 240
        while not predicate():
            app.processEvents()
            if approval_failure:
                raise Q06PlatformQualificationError(approval_failure[0])
            if window._last_error_code:
                raise Q06PlatformQualificationError("Q06_PLATFORM_GUI_OPERATION_DENIED")
            if time.monotonic() >= deadline:
                raise Q06PlatformQualificationError("Q06_PLATFORM_GUI_WAIT_" + label)
            time.sleep(.01)
        app.processEvents()

    def gui_approval(button, caption, done, *, duplicate=False):
        from PySide6.QtCore import QTimer, Qt
        from .fusion_pages import PaymentApproval
        from .qualification_gui import click_visible_approval
        timer = QTimer()
        timer.setInterval(100)
        clicked = [False]
        def consent():
            for dialog in app.allWidgets():
                if isinstance(dialog, PaymentApproval) and dialog.isVisible():
                    # QDialog.open() intentionally switches the visible
                    # dialog to WindowModal; constructor ApplicationModal is
                    # checked separately by source widget contracts.
                    record['visible_payment_approval'] = {
                        'modality':dialog.windowModality().name,
                        'modal':dialog.isModal(),'cancel_default':dialog.cancel.isDefault(),
                        'approve_default':dialog.approve.isDefault()}
                    if (dialog.windowModality() != Qt.WindowModality.WindowModal
                            or not dialog.isModal() or not dialog.cancel.isDefault()
                            or dialog.approve.isDefault()):
                        approval_failure.append("Q06_PLATFORM_PAYMENT_APPROVAL_DENIED")
                        timer.stop()
                        return
                    if duplicate and caption == "Approve Sign":
                        # Deliver repeated clicks to the same visible native
                        # approval. The real executor below must see one sign.
                        control = dialog.approve
                        control.clicked.emit()
                        control.clicked.emit()
                        clicked[0] = True
                        return
            if click_visible_approval(app, caption):
                clicked[0] = True
        timer.timeout.connect(consent)
        timer.start()
        try:
            button.click()
            if duplicate:
                button.click()  # A busy/disabled Send must not prepare twice.
            wait_gui(lambda: clicked[0] and idle() and done(), "APPROVAL")
        finally:
            timer.stop()

    try:
        step("TRUST")
        adapter.prepare_trust(core, linux_manifest, linux_witness, test_witness=False)
        node, cli, _ = verified_core_paths(core)
        from .q05_package_provenance import read
        provenance = read()
        record["source_sha"] = provenance["candidate_source_sha"]
        record["checkout_sha"] = provenance["checkout_sha"]
        record["core_version"] = adapter.core_version
        record["core_sha256"] = {path.name:sha256(path.read_bytes()).hexdigest() for path in (node,cli)}
        record["wsp_source_commit"] = "ac55f13423620252bdbf848c7e8a280c3b84721e"
        step("CREATE")
        password = b"disposable-native-frozen-q06-cross-platform"
        executor = WalletExecutor(lambda: Bip39ReadOnlyBackend(
            root, core, source, _anchor_factory=adapter.make_anchor))
        if headless:
            opened = executor.request("open", password, "create", "", timeout=120)
            phrase = opened["mnemonic_once"]
        else:
            from .desktop import qt_application
            from .bip39_fusion_gui import Bip39FusionWindow
            app = qt_application()
            expected = "windows" if sys.platform == "win32" else "xcb"
            if app.platformName() != expected:
                raise Q06PlatformQualificationError("Q06_PLATFORM_NATIVE_QT_DENIED")
            from .managed_onboarding import assert_unified_welcome_qt
            assert_unified_welcome_qt()
            step("FROZEN_UNIFIED_WELCOME_PASS")
            # Transparent observation of the real executor Future boundary.
            # Forward every request unchanged; never intercept Core RPC/keys.
            dispatch_counts = {}
            original_submit = executor.submit
            def observed_submit(action, *args, **kwargs):
                dispatch_counts[action] = dispatch_counts.get(action, 0) + 1
                return original_submit(action, *args, **kwargs)
            executor.submit = observed_submit
            window = Bip39FusionWindow(executor)
            gui_results = {}
            original_ready = window._on_ready
            def observed_ready(action, result):
                if action == "confirm":
                    gui_results[action] = dict(result)  # Actual backend public result.
                return original_ready(action, result)
            window._on_ready = observed_ready
            window.show()
            window.start(password, "create", "")
            wait_gui(lambda: idle() and window._backup_flow_active, "CREATE")
            opened = dict(window._backup_result)
            phrase = opened["mnemonic_once"]
            backup = window.backup_page
            backup._written_check.setChecked(True)
            backup._back_up_now.click()
            words = phrase.split()
            for position, field in zip(backup._challenge_positions, backup._verify_inputs):
                field.setText(words[position - 1])
            words = None
            backup._verify_button.click()
            if backup._stack.currentWidget() is not backup._success_page:
                raise Q06PlatformQualificationError("Q06_PLATFORM_GUI_BACKUP_DENIED")
            backup._continue_button.click()
            wait_gui(lambda: idle() and window._last_verified is not None, "BACKUP")
            record["normal_gui_backup_verified"] = True
        if (len(phrase.split()) != 12
                or not opened["receive_code"].startswith("wamrtsp1")
                or opened["signer_allowed"] is not False):
            raise Q06PlatformQualificationError("Q06_PLATFORM_CREATE_DENIED")
        step("FUND")
        funded = executor.request("mine", timeout=240)
        first = executor.request("snapshot", timeout=240)
        if (first["confirmed_atoms"] != funded["atoms"]
                or first["available_atoms"] != funded["atoms"]
                or first["history_count_shown"] < 1):
            raise Q06PlatformQualificationError("Q06_PLATFORM_FUNDED_RECEIVE_DENIED")
        step("ACTIVATE")
        if window is None:
            active = executor.request("activate", timeout=240)
        else:
            gui_approval(window.activate, "Approve", lambda: window._spend_enabled)
            active = executor.request("snapshot", timeout=240)
        if (active["signer_allowed"] is not True
                or active["broadcast_allowed"] is not True
                or active["confirmed_atoms"] != funded["atoms"]
                or active["mainnet_allowed"] is not False):
            raise Q06PlatformQualificationError("Q06_PLATFORM_NATIVE_SPEND_DENIED")
        if window is not None:
            step("NATIVE_QT")
            window._on_ready("snapshot", active)
            app.processEvents()
            from .fusion_ui import FUSION_NAV_PAGES
            if (not window.isVisible() or not window.send.isEnabled()
                    or window.receive.text()!=opened["receive_code"]
                    or window.navigation.count()!=len(FUSION_NAV_PAGES)
                    or window.overview.balance_value.text()=="—"
                    or not hasattr(window.overview, "balance_chart")
                    or not hasattr(window.overview, "go_send")
                    or not hasattr(window.overview, "go_receive")
                    or window.receive_page.code!=opened["receive_code"]
                    or window.history_page.table.rowCount()<1):
                raise Q06PlatformQualificationError("Q06_PLATFORM_FUSION_QT_BINDING_DENIED")
            from PySide6.QtWidgets import QLabel
            if any("Quick Actions" in (label.text() or "") for label in window.findChildren(QLabel)):
                raise Q06PlatformQualificationError("Q06_PLATFORM_FUSION_QUICK_ACTIONS_DENIED")
            record["native_gui_checked"] = True
        from mnemonic import Mnemonic
        with Bip39Regtest12Keys(Mnemonic("english").to_mnemonic(bytes([1]*16)),
                                source=source, authorized_disposable=True) as other:
            destination = other.public_metadata()["receive_code"]
        atoms = min(50_000, funded["atoms"]//4)
        if atoms < 330 or funded["atoms"] < atoms + 1_000:
            raise Q06PlatformQualificationError("Q06_PLATFORM_INSUFFICIENT_TEST_FUNDS")
        step("PREPARE")
        if window is None:
            draft = executor.request("prepare", destination, atoms, 1_000, timeout=240)
            if draft.code != destination or draft.atoms != atoms or len(draft.commitment) != 64:
                raise Q06PlatformQualificationError("Q06_PLATFORM_INTENT_DENIED")
            step("SIGN")
            signed = executor.request("sign", draft.commitment, timeout=240)
            if signed.commitment != draft.commitment:
                raise Q06PlatformQualificationError("Q06_PLATFORM_SIGN_DENIED")
            step("BROADCAST")
            txid = executor.request("broadcast", draft.commitment, timeout=240)
        else:
            window.recipient_input.setText(destination)
            window.amount_input.setText(f"{atoms // 100_000_000}.{atoms % 100_000_000:08d}")
            window.fee_input.setText("0.00001000")
            before = executor.request("snapshot", timeout=240)
            gui_approval(window.send, "Cancel", lambda: window._last_review is None)
            cancelled = executor.request("snapshot", timeout=240)
            if (window._signed_ready or cancelled["reservation_count"] != before["reservation_count"]
                    or cancelled["confirmed_atoms"] != before["confirmed_atoms"]):
                raise Q06PlatformQualificationError("Q06_PLATFORM_CANCEL_SIGNED")
            if dispatch_counts.get("sign", 0) != 0:
                raise Q06PlatformQualificationError("Q06_PLATFORM_CANCEL_DISPATCHED_SIGN")
            record["gui_cancel_does_not_sign"] = True
            window.recipient_input.setText(destination)
            window.amount_input.setText(f"{atoms // 100_000_000}.{atoms % 100_000_000:08d}")
            window.fee_input.setText("0.00001000")
            step("SIGN")
            gui_approval(window.send, "Approve Sign", lambda: window._signed_ready, duplicate=True)
            draft = window._last_review
            if (draft.code != destination or draft.atoms != atoms or draft.fee != 1_000
                    or len(draft.commitment) != 64):
                raise Q06PlatformQualificationError("Q06_PLATFORM_INTENT_DENIED")
            signed_view = executor.request("snapshot", timeout=240)
            if signed_view["reservation_count"] != before["reservation_count"] + 1:
                raise Q06PlatformQualificationError("Q06_PLATFORM_DUPLICATE_SIGN_DENIED")
            if dispatch_counts.get("sign", 0) != 1:
                raise Q06PlatformQualificationError("Q06_PLATFORM_SIGN_DISPATCH_COUNT_DENIED")
            record["gui_sign_dispatch_count"] = dispatch_counts["sign"]
            record["gui_duplicate_send_one_reservation"] = True
            step("BROADCAST")
            gui_approval(window.broadcast, "Cancel", lambda: window._signed_ready)
            if window._pending_confirm_txid is not None or dispatch_counts.get("broadcast", 0) != 0:
                raise Q06PlatformQualificationError("Q06_PLATFORM_CANCEL_BROADCAST_DENIED")
            gui_approval(window.broadcast, "Approve Broadcast",
                         lambda: window._pending_confirm_txid is not None)
            txid = window._pending_confirm_txid
            if dispatch_counts.get("broadcast", 0) != 1:
                raise Q06PlatformQualificationError("Q06_PLATFORM_BROADCAST_DISPATCH_COUNT_DENIED")
            record["gui_broadcast_dispatch_count"] = dispatch_counts["broadcast"]
            record["normal_gui_separate_sign_broadcast"] = True
        if type(txid) is not str or re.fullmatch(r"[0-9a-f]{64}", txid) is None:
            raise Q06PlatformQualificationError("Q06_PLATFORM_BROADCAST_DENIED")
        step("CONFIRM")
        if window is None:
            confirmed_tx = executor.request("confirm", txid, timeout=240)
        else:
            gui_approval(window.confirm, "Approve", lambda: window._pending_confirm_txid is None)
            confirmed_tx = gui_results.get("confirm")
            if type(confirmed_tx) is not dict:
                raise Q06PlatformQualificationError("Q06_PLATFORM_GUI_CONFIRM_RESULT_MISSING")
            record["normal_gui_confirm_verified"] = True
        after = executor.request("snapshot", timeout=240)
        if (confirmed_tx["status"] != "Q06_REGTEST_EXACT_SEND_CONFIRMED"
                or confirmed_tx["txid"] != txid
                or after["height"] != confirmed_tx["height"]
                or after["history_count_shown"] < 2):
            raise Q06PlatformQualificationError("Q06_PLATFORM_CONFIRM_DENIED")
        if window is not None:
            window._on_ready("broadcast", txid)
            window._on_ready("snapshot", after)
            app.processEvents()
            if window.last_txid.text() != txid or not window.last_txid.isReadOnly():
                raise Q06PlatformQualificationError("Q06_PLATFORM_TXID_COPY_DENIED")
        record["signed_core_transaction_confirmed"] = True
        step("INDEPENDENT_SAME_CHAIN_RESCAN")
        rescan = executor.request("recovery_verify", phrase, timeout=240)
        if (rescan["status"] != "Q06_SAME_CHAIN_BIP39_HISTORY_RESCAN_PASS"
                or rescan["receive_code"] != opened["receive_code"]
                or rescan["confirmed_atoms"] != after["confirmed_atoms"]
                or rescan["history_count"] < 2
                or rescan["same_chain_only"] is not True
                or rescan["signed_reservations_restored"] is not False
                or rescan["signer_allowed"] is not False):
            raise Q06PlatformQualificationError("Q06_PLATFORM_RESCAN_DENIED")
        record["same_chain_mnemonic_history_recovered"] = True
        step("LOCK_REOPEN")
        executor.request("lock", timeout=120)
        again = executor.request("open", password, "reopen", "", timeout=120)
        current = executor.request("activate", timeout=240)
        if (again["receive_code"] != opened["receive_code"] or again["mnemonic_once"]
                or current["confirmed_atoms"] != after["confirmed_atoms"]
                or current["reservation_count"] != after["reservation_count"]
                or current["history_count_shown"] < 2):
            raise Q06PlatformQualificationError("Q06_PLATFORM_REOPEN_DENIED")
        record["same_owner_reopened"] = True
        step("POST_REOPEN_READONLY_TXID")
        found = executor.request("inspect_confirmed", txid, timeout=240)
        absent = executor.request("inspect_confirmed", "f"*64, timeout=240)
        if (found["status"] != "Q06_CONFIRMED_IN_VERIFIED_HISTORY"
                or found["write_attempted"] is not False
                or absent["status"] != "Q06_TX_NOT_IN_CONFIRMED_HISTORY"
                or absent["write_attempted"] is not False):
            raise Q06PlatformQualificationError("Q06_PLATFORM_TXID_RECONCILIATION_DENIED")
        record["post_reopen_txid_verified"] = True
        record["txid_sha256"] = sha256(txid.encode("ascii")).hexdigest()
        record["receive_code_sha256"] = sha256(opened["receive_code"].encode("ascii")).hexdigest()
        step("CLEAN_SHUTDOWN")
        executor.request("quit", timeout=120)
        if not executor.join(15) or not executor.closed:
            raise Q06PlatformQualificationError("Q06_PLATFORM_OWNER_STILL_LIVE")
        step("FRESH_PROFILE_SEED_RESTORE")
        # A separate owned Core has a different disposable genesis-only
        # history. BIP39 restores keys/identity, never past blockchain blocks.
        from .custody import create_directory
        import secrets
        restored_root = root.parent / ("wam-fusion-core-" + secrets.token_hex(8))
        # Avoid copying any chain, credential, checkpoint or original vault.
        restored_executor = WalletExecutor(lambda: Bip39ReadOnlyBackend(
            restored_root, core, source, _anchor_factory=adapter.make_anchor))
        restored = restored_executor.request(
            "open", password, "restore", phrase, timeout=120)
        fresh_view = restored_executor.request("snapshot", timeout=120)
        if (restored["mnemonic_once"]
                or restored["receive_code"] != opened["receive_code"]
                or restored["account_id"] != opened["account_id"]
                or fresh_view["height"] != 0
                or fresh_view["confirmed_atoms"] != 0
                or fresh_view["history_count_shown"] != 0
                or fresh_view["signer_allowed"] is not False):
            raise Q06PlatformQualificationError("Q06_PLATFORM_NEW_CHAIN_RESTORE_DENIED")
        restored_executor.request("quit", timeout=120)
        if not restored_executor.join(15) or not restored_executor.closed:
            raise Q06PlatformQualificationError("Q06_PLATFORM_RESTORE_OWNER_STILL_LIVE")
        record["fresh_profile_seed_identity_restored"] = True
        step("FRESH_PROFILE_SAME_CHAIN_HISTORY_RESTORE")
        from .q06_same_chain_restore_probe import qualify as restore_same_chain
        restored_history = restore_same_chain(core,source,root.parent,adapter)
        record["fresh_profile_same_chain_history"] = restored_history
        if (restored_history['status']!='FRESH_PROFILE_SAME_CHAIN_HISTORY_RESTORE_PASS'
                or restored_history['all_original_owners_shutdown_verified'] is not True):
            raise Q06PlatformQualificationError("Q06_PLATFORM_FRESH_SAME_CHAIN_RESTORE_DENIED")
        record["fresh_same_chain_profile_full_history_recovered"] = True
        good = True
        record["status"] = "Q06_NATIVE_FROZEN_REAL_CORE_PASS"
        record["failure_stage"] = None
        return record
    except Exception as error:
        # Fixed public diagnostic codes only; never format exception repr,
        # native OS strings, RPC bodies, process arguments or seed words.
        from .wallet_executor import WalletExecutorError
        code = error.args[0] if (type(error) in (
            Q06PlatformQualificationError, WalletExecutorError)
            and len(error.args) == 1) else None
        record["failure_code"] = (code if type(code) is str
                                  and re.fullmatch(r"(?:Q06|WALLET|MANAGED|RPC|CORE)_[A-Z0-9_]{3,80}", code)
                                  else "Q06_NATIVE_ENGINE_DENIED")
        return record
    finally:
        if window is not None:
            window._poll.stop()
            window.hide()
            if good:
                # Match the already qualified macOS frozen Q06 teardown:
                # complete Qt's deferred widget destruction while the native
                # QApplication still exists, BEFORE Linux entry shuts Qt down.
                # The owned Core was positively stopped above. No owner
                # shutdown or custody operation happens in the Qt cleanup.
                from PySide6.QtCore import QCoreApplication, QEvent
                window.deleteLater()
                QCoreApplication.sendPostedEvents(
                    None, QEvent.Type.DeferredDelete)
                app.processEvents()
        if not good:
            # Executor's owner thread is intentionally non-daemon. On a
            # synchronous read/validation failure, use the *original*
            # authenticated owner to request bounded clean shutdown ONLY
            # if idle; preserve all chain/anchor/SQLite bytes. Never cancel a
            # pending write, replay a transaction or force-stop an unknown Core.
            record["owner_after_failure"] = "PRESERVED_UNCERTAIN"
            safe_shutdown = True
            for worker in (restored_executor, executor):
                if worker is None or worker.closed:
                    continue
                if worker.busy:
                    safe_shutdown = False
                    continue
                try:
                    worker.request("quit", timeout=45)
                    if not worker.join(15) or not worker.closed:
                        safe_shutdown = False
                except Exception:
                    safe_shutdown = False
            if safe_shutdown:
                record["owner_after_failure"] = "CLEAN_STOP_BYTES_PRESERVED"
        else:
            adapter.teardown()
        # Failed native journal, frozen Core bytes, chain and witness are
        # never swept or silently repaired. No re-signing or auto-broadcast.
        phrase = None


def run(core, source, argv):
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--confirm-disposable-regtest", action="store_true")
    parser.add_argument("--linux-developer-manifest")
    parser.add_argument("--linux-root-witness", type=Path)
    parser.add_argument("--headless", action="store_true")
    a = parser.parse_args(argv)
    record = qualify(
        core, source, a.root, a.receipt, confirmed=a.confirm_disposable_regtest,
        linux_manifest=a.linux_developer_manifest,
        linux_witness=a.linux_root_witness, headless=a.headless)
    with a.receipt.open("x", encoding="utf8") as output:
        json.dump(record, output, sort_keys=True, indent=2)
        output.write("\n")
    return 0 if record["status"] == "Q06_NATIVE_FROZEN_REAL_CORE_PASS" else 2
