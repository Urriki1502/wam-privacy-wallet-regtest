"""Q06 GUI backup acknowledgement contracts for the WAM Fusion onboarding page.

Real Qt widgets and the production Bip39BackupPage are exercised (no dialog
mocking). This never fakes Core, custody or acceptance; Q06 engineering tests
must keep reusing the existing tests/test_q06_bip39*.py discovery path.
No profile, native anchor or acceptance status is touched.
"""
import ast
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from mnemonic import Mnemonic

# Same runner pattern as tests/test_q06_bip39_fusion_gui.py: never force
# offscreen on Cocoa/Windows; headless Linux source tests need the fallback.
if sys.platform == "linux" and not os.environ.get("DISPLAY"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Fixed disposable REGTEST-only display material (checksum-valid BIP39 words
# from distinct entropy, not a published vector or any wallet in use). No
# container, key or transaction is ever derived with it. It must never appear
# in logs, receipts, status widgets or command output.
_DISPLAY_PHRASE_WORDS = Mnemonic("english").to_mnemonic(bytes(range(16)))


class _StubExecutor:
    """Records the exact backend requests the GUI would issue during ack."""

    def __init__(self, seed_folder, phrase):
        from wam_regtest.wallet_executor import ExecutorState
        self.state = ExecutorState()
        self.busy = False
        self.closed = False
        self.seed_folder = seed_folder
        self.phrase = phrase
        self.log = []          # list of action records
        self.requests = []     # durable action names; no secret arguments
        self.locked = False
        self.verified = False
        self.marker = None

    def submit(self, action, *args, **kwargs):
        # ControlWorker uses submit(), as the real executor does. Preserve
        # completion/denial via an actual Future instead of an absent method.
        from concurrent.futures import Future
        future = Future()
        try:
            future.set_result(self.request(action, *args, **kwargs))
        except Exception as error:
            future.set_exception(error)
        return future

    def request(self, action, *args, timeout=90, **kwargs):
        self.requests.append(action)
        if action == "acknowledge_create_pending":
            folder = args[0]
            self.log.append(("pending", folder))
            self.marker = (False, True)
            return None
        if action == "backup_defer":
            self.log.append(("defer",))
            self.locked = True
            self.marker = (False, True)
            return None
        if action == "backup_verify":
            positions, answers = args
            self.log.append(("verify", positions, answers))
            words = self.phrase.split()
            ok = (len(positions) == len(answers)
                  and all(words[p - 1].lower() == a.strip().lower()
                          for p, a in zip(positions, answers)))
            if ok:
                self.locked = False
                self.verified = True
                self.marker = (True, False)
            return ok
        raise RuntimeError(f"unexpected stub request: {action}")


if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import (
        QApplication, QLineEdit, QCheckBox, QPushButton, QLabel)

    from wam_regtest.wallet_executor import ExecutorState
    from wam_regtest.bip39_fusion_gui import Bip39FusionWindow
    from wam_regtest.bip39_owner_gui import Bip39RecoveryVerifyDialog


def _make_window():
    app = QApplication.instance() or QApplication([])
    tmp = tempfile.mkdtemp(prefix="q06-stub-")
    seed_folder = str(Path(tmp) / "bip39-12-stub")
    executor = _StubExecutor(seed_folder, _DISPLAY_PHRASE_WORDS)
    window = Bip39FusionWindow(executor)
    return app, window


def _open_result(status, reveal="", seed_folder=None):
    return {"status": "Q06_REGTEST_READ_ONLY_OWNER_OPENED",
            "profile": "fusion-bip39-12-bip32-bip352-regtest-v1",
            "account_id": "test-account-identity",
            "receive_code": "wamrtsp1public-test",
            "mnemonic_once": reveal,
            "seed_folder": seed_folder,
            "backup_status": status,
            "signer_allowed": False, "broadcast_allowed": False,
            "mainnet_allowed": False}


def _find_button(parent, text):
    for btn in parent.findChildren(QPushButton):
        if text in btn.text():
            return btn
    raise AssertionError(f"button {text!r} not found")


def _find_line_edits(parent):
    return parent.findChildren(QLineEdit)


class BackupPageContract(unittest.TestCase):
    """Widget-level contracts on the production onboarding backup page."""

    def setUp(self):
        if importlib.util.find_spec("PySide6") is None:
            self.skipTest("Native Qt widgets verified on Qt-capable runners")
        self.app, self.window = _make_window()

    def tearDown(self):
        self.window._poll.stop()
        worker = self.window._worker
        if worker is not None:
            self.assertTrue(worker.wait(2000))
        self.app.processEvents()
        self.window.hide()
        self.window.deleteLater()
        self.app.processEvents()

    def _assert_snapshot_dispatched(self):
        # A fast real ControlWorker can already have finished after events
        # are processed. Observe its request instead of transient liveness.
        import time
        deadline = time.monotonic() + 2
        while "snapshot" not in self.window.executor.requests:
            self.assertLess(time.monotonic(), deadline, "snapshot not dispatched")
            QTest.qWait(5)
            self.app.processEvents()
        self.assertEqual(self.window.executor.requests.count("snapshot"), 1)

    def _finish_snapshot_worker(self):
        self._assert_snapshot_dispatched()
        worker = self.window._worker
        if worker is not None:
            self.assertTrue(worker.wait(2000))
        self.app.processEvents()

    def _show_required(self):
        self.window._on_ready(
            "open", _open_result("required", _DISPLAY_PHRASE_WORDS,
                                 self.window.executor.seed_folder))
        self.app.processEvents()

    def _show_deferred(self):
        self.window._on_ready(
            "open", _open_result("deferred", "",
                                 self.window.executor.seed_folder))
        self.app.processEvents()

    def test_create_shows_numbered_three_by_four_grid(self):
        self._show_required()
        cards = self.window.backup_page.findChildren(QPushButton)
        # The page uses QFrame cards, not QPushButton; inspect grid labels.
        labels = [w.text() for w in self.window.backup_page.findChildren(QLabel)
                  if w.text() in _DISPLAY_PHRASE_WORDS.split()]
        self.assertEqual(len(labels), 12)
        self.assertEqual(sorted(labels), sorted(_DISPLAY_PHRASE_WORDS.split()))
        self.assertEqual(self.window.stack.currentWidget(), self.window.backup_page)
        self.assertFalse(self.window.navigation.isEnabled())

    def test_back_up_now_disabled_until_written_checkbox(self):
        self._show_required()
        now = _find_button(self.window.backup_page, "Back up now")
        self.assertFalse(now.isEnabled())
        check = self.window.backup_page.findChildren(QCheckBox)[0]
        check.setChecked(True)
        self.assertTrue(now.isEnabled())

    def test_back_up_later_defers_and_locks_backend(self):
        self._show_required()
        _find_button(self.window.backup_page, "Back up later").click()
        self.app.processEvents()
        self.assertTrue(self.window.executor.locked)
        self.assertIn(("defer",), self.window.executor.log)
        self.assertTrue(self.window._backup_unacked)
        self.assertFalse(self.window._ready)
        self.assertEqual(self.window.stack.currentIndex(), 0)
        self.assertTrue(self.window.navigation.isEnabled())

    def test_backup_verify_back_returns_to_phrase_page(self):
        self._show_required()
        self.window.backup_page.findChildren(QCheckBox)[0].setChecked(True)
        _find_button(self.window.backup_page, "Back up now").click()
        self.app.processEvents()
        self.window.backup_page._verify_back.click()
        self.app.processEvents()
        self.assertEqual(self.window.backup_page._stack.currentWidget(), self.window.backup_page._phrase_page)

    def test_backup_verify_page_shows_step_2_of_2_progress_and_three_cards(self):
        self._show_required()
        self.window.backup_page.findChildren(QCheckBox)[0].setChecked(True)
        _find_button(self.window.backup_page, "Back up now").click()
        self.app.processEvents()
        self.assertIn("STEP 2 OF 2", self.window.backup_page._step_label.text())
        self.assertEqual(self.window.backup_page._step_progress.value(), 2)
        self.assertEqual(self.window.backup_page._step_progress.maximum(), 2)
        self.assertEqual(len(self.window.backup_page._verify_inputs), 3)
        positions = self.window.backup_page._challenge_positions
        self.assertEqual(len(positions), 3)
        self.assertEqual(len(set(positions)), 3)
        self.assertTrue(all(1 <= position <= 12 for position in positions))
        for index, (card, title, edit) in enumerate(self.window.backup_page._verify_cards):
            self.assertEqual(title.text(), f"WORD #{positions[index]}")
            self.assertEqual(edit.echoMode(), QLineEdit.EchoMode.Password)
        privacy = [w.text() for w in self.window.backup_page.findChildren(QLabel) if "locally" in w.text()]
        self.assertEqual(privacy, ["Verification happens locally."])

    def test_escape_defers_and_locks_backend(self):
        self._show_required()
        QTest.keyClick(self.window.backup_page, Qt.Key_Escape)
        self.app.processEvents()
        self.assertTrue(self.window.executor.locked)
        self.assertTrue(self.window._backup_unacked)
        self.assertFalse(self.window._ready)

    def test_successful_verification_unlocks_and_schedules_snapshot(self):
        self._show_required()
        self.window.backup_page.findChildren(QCheckBox)[0].setChecked(True)
        _find_button(self.window.backup_page, "Back up now").click()
        self.app.processEvents()

        positions = self.window.backup_page._challenge_positions
        words = _DISPLAY_PHRASE_WORDS.split()
        for edit, pos in zip(_find_line_edits(self.window.backup_page), positions):
            edit.setText(words[pos - 1])
        _find_button(self.window.backup_page, "Verify").click()
        self.app.processEvents()

        self.assertTrue(self.window.executor.verified)
        self.assertFalse(self.window.executor.locked)
        # Success page is shown; pressing Continue completes the flow.
        _find_button(self.window.backup_page, "Continue").click()
        self.app.processEvents()
        self.assertTrue(self.window._ready)
        self.assertEqual(self.window.receive.text(), "wamrtsp1public-test")
        self._assert_snapshot_dispatched()
        self.assertEqual(self.window.stack.currentIndex(), 0)
        self.assertTrue(self.window.navigation.isEnabled())

    def test_backup_success_continue_unlocks_fund_lock_and_keeps_send_locked(self):
        self._show_required()
        self.window.backup_page.findChildren(QCheckBox)[0].setChecked(True)
        _find_button(self.window.backup_page, "Back up now").click()
        self.app.processEvents()
        positions = self.window.backup_page._challenge_positions
        words = _DISPLAY_PHRASE_WORDS.split()
        for edit, pos in zip(self.window.backup_page._verify_inputs, positions):
            edit.setText(words[pos - 1])
        _find_button(self.window.backup_page, "Verify").click()
        self.app.processEvents()
        self.assertTrue(self.window.executor.verified)
        _find_button(self.window.backup_page, "Continue").click()
        self.app.processEvents()
        # Genuinely successful authenticated backup -> ready wallet session.
        self.assertTrue(self.window._ready)
        self.assertFalse(self.window._backup_flow_active)
        self._assert_snapshot_dispatched()
        # Continue dispatched the pending verified snapshot through the real
        # ControlWorker; model its worker-finished completion and refresh.
        self._finish_snapshot_worker()
        self.assertTrue(self.window._ready)
        # Fund enabled on a fresh unfunded REGTEST chain; Lock enabled; Send
        # stays disabled until native checkpoint + explicit signer activation.
        self.assertTrue(self.window.fund.isEnabled())
        self.assertTrue(self.window.lock.isEnabled())
        self.assertFalse(self.window.send.isEnabled())
        self.assertFalse(self.window.broadcast.isEnabled())
        # A verified snapshot refresh keeps the ready state and does not relock.
        self.assertFalse(self.window.executor.locked)
        self.assertFalse(self.window.executor.state.faulted)

    def test_failed_verification_keeps_wallet_locked_then_retry_unlocks(self):
        self._show_required()
        self.window.backup_page.findChildren(QCheckBox)[0].setChecked(True)
        _find_button(self.window.backup_page, "Back up now").click()
        self.app.processEvents()
        for edit in self.window.backup_page._verify_inputs:
            edit.setText("wrong")
        _find_button(self.window.backup_page, "Verify").click()
        self.app.processEvents()
        self.assertFalse(self.window._ready)
        self.assertTrue(self.window._backup_flow_active)
        self.assertFalse(self.window.fund.isEnabled())
        self.assertFalse(self.window.lock.isEnabled())
        self.assertFalse(self.window.send.isEnabled())
        err = self.window.backup_page._verify_error
        self.assertIn("do not match", err.text())
        self.assertFalse(err.isHidden())
        # Retry with the correct words -> verified -> Continue -> ready.
        positions = self.window.backup_page._challenge_positions
        words = _DISPLAY_PHRASE_WORDS.split()
        for edit, pos in zip(self.window.backup_page._verify_inputs, positions):
            edit.setText(words[pos - 1])
        _find_button(self.window.backup_page, "Verify").click()
        self.app.processEvents()
        self.assertTrue(self.window.executor.verified)
        _find_button(self.window.backup_page, "Continue").click()
        self.app.processEvents()
        self.assertTrue(self.window._ready)
        self._assert_snapshot_dispatched()
        # Continue dispatched the pending verified snapshot through the real
        # ControlWorker; model its worker-finished completion and refresh.
        self._finish_snapshot_worker()
        self.assertTrue(self.window.fund.isEnabled())
        self.assertTrue(self.window.lock.isEnabled())
        self.assertFalse(self.window.send.isEnabled())

    def test_wrong_verification_shows_error_and_allows_retry(self):
        self._show_required()
        self.window.backup_page.findChildren(QCheckBox)[0].setChecked(True)
        _find_button(self.window.backup_page, "Back up now").click()
        self.app.processEvents()

        for edit in _find_line_edits(self.window.backup_page):
            edit.setText("wrong")
        _find_button(self.window.backup_page, "Verify").click()
        self.app.processEvents()

        self.assertFalse(self.window.executor.verified)
        self.assertFalse(self.window._ready)
        err = self.window.backup_page._verify_error
        self.assertIn("do not match", err.text())
        self.assertFalse(err.isHidden())
        # A fresh challenge is generated for retry.
        self.assertNotEqual(
            len(self.window.backup_page._challenge_positions), 0)

    def test_deferred_mode_skips_grid_and_requires_verification(self):
        self._show_deferred()
        self.assertEqual(self.window.stack.currentWidget(), self.window.backup_page)
        labels = [w.text() for w in self.window.backup_page.findChildren(QLabel)
                  if w.text() in _DISPLAY_PHRASE_WORDS.split()]
        self.assertEqual(labels, [])  # grid hidden
        positions = self.window.backup_page._challenge_positions
        words = _DISPLAY_PHRASE_WORDS.split()
        for edit, pos in zip(_find_line_edits(self.window.backup_page), positions):
            edit.setText(words[pos - 1])
        _find_button(self.window.backup_page, "Verify").click()
        self.app.processEvents()
        self.assertTrue(self.window.executor.verified)
        _find_button(self.window.backup_page, "Continue").click()
        self.app.processEvents()
        self.assertTrue(self.window._ready)
        self._assert_snapshot_dispatched()

    def test_verified_status_bypasses_backup_page(self):
        self.window._on_ready(
            "open", _open_result("verified", "",
                                 self.window.executor.seed_folder))
        self.app.processEvents()
        self.assertNotEqual(self.window.stack.currentWidget(), self.window.backup_page)
        self.assertTrue(self.window._ready)
        self.assertEqual(self.window.receive.text(), "wamrtsp1public-test")

    def test_no_phrase_in_stdout_status_or_test_artifacts(self):
        captured = io.StringIO()
        self._show_required()
        with contextlib.redirect_stdout(captured):
            self.app.processEvents()
        self.assertEqual(captured.getvalue(), "")
        status = self.window.status.text()
        for word in _DISPLAY_PHRASE_WORDS.split():
            self.assertNotIn(word, status)


class BackupAckSourceContract(unittest.TestCase):
    """Static module hygiene; complements, never replaces, real widget runs."""

    def test_gui_source_uses_backup_page_hook_not_dialog(self):
        path = (Path(__file__).resolve().parents[1]
                / "src" / "wam_regtest" / "bip39_owner_gui.py")
        source = path.read_text(encoding="utf8")
        self.assertIn("_present_backup_ack", source)
        self.assertIn("_backup_flow_completed", source)
        self.assertNotIn("backup_ack_dialog", source)
        self.assertNotIn("_show_words_once", source)

    def test_backend_enforces_authenticated_ack_sidecar(self):
        path = (Path(__file__).resolve().parents[1]
                / "src" / "wam_regtest" / "bip39_owner_backend.py")
        source = path.read_text(encoding="utf8")
        self.assertIn("backup_verify", source)
        self.assertIn("backup_defer", source)
        self.assertIn("backup_ack_key", source)
        self.assertIn("_q06_write_ack", source)
        self.assertIn("hmac.compare_digest", source)

    def test_wallet_executor_admits_backup_ack_actions(self):
        from wam_regtest import wallet_executor as _we
        self.assertIn("backup_verify", _we.COMMANDS)
        self.assertIn("backup_defer", _we.COMMANDS)
        self.assertIn("acknowledge_create_pending", _we.COMMANDS)

    def test_fixture_words_are_twelve_and_checksum_valid(self):
        self.assertEqual(len(_DISPLAY_PHRASE_WORDS.split()), 12)
        self.assertTrue(Mnemonic("english").check(_DISPLAY_PHRASE_WORDS))


class InSessionLockUnlockContract(unittest.TestCase):
    """Owner UX correction: in-session Lock <-> Unlock + remembered profile.

    The owner must be able to lock and unlock WITHOUT quitting the app or
    browsing for a wallet folder, and reopen the remembered original profile
    after an app restart. All of this stays fail-closed on the authenticated
    same-owner REGTEST boundary.
    """

    def setUp(self):
        if importlib.util.find_spec("PySide6") is None:
            self.skipTest("Native Qt widgets verified on Qt-capable runners")
        self.app, self.window = _make_window()

    def tearDown(self):
        self.window._poll.stop()
        worker = self.window._worker
        if worker is not None:
            self.assertTrue(worker.wait(2000))
        self.app.processEvents()
        self.window.hide()
        self.window.deleteLater()
        self.app.processEvents()

    def _verified_open(self):
        self.window._on_ready(
            "open", _open_result("verified", "", self.window.executor.seed_folder))
        self.app.processEvents()

    def test_unlock_and_lock_controls_follow_authenticated_state(self):
        self.assertFalse(self.window.unlock.isEnabled())
        self.assertFalse(self.window.lock.isEnabled())
        self._verified_open()
        # Genuinely verified wallet -> unlocked: Lock enabled, Unlock hidden
        # until the next Lock.
        self.assertTrue(self.window.lock.isEnabled())
        self.assertFalse(self.window.unlock.isEnabled())
        self.assertTrue(self.window._ready)
        # Lock -> clear sensitive GUI data and disable spend/send/broadcast.
        self.window._on_ready("lock", None)
        self.app.processEvents()
        self.assertFalse(self.window._ready)
        self.assertTrue(self.window.unlock.isEnabled())
        self.assertFalse(self.window.lock.isEnabled())
        self.assertFalse(self.window.fund.isEnabled())
        self.assertFalse(self.window.send.isEnabled())
        self.assertFalse(self.window.broadcast.isEnabled())

    def test_unlock_after_lock_promotes_to_ready_and_schedules_snapshot(self):
        self._verified_open()
        self.window._on_ready("lock", None)
        self.app.processEvents()
        self.window._on_ready(
            "unlock", _open_result("verified", "", self.window.executor.seed_folder))
        self.app.processEvents()
        # Same receive code, account and pending verified refresh — no new
        # profile and no phrase regeneration.
        self.assertTrue(self.window._ready)
        self.assertEqual(self.window.receive.text(), "wamrtsp1public-test")
        self.assertEqual(self.window.account.text(), "BIP39 account: test-account-identity")
        self.assertEqual(self.window._pending_action, ("snapshot",))

    def test_unlock_deferred_returns_to_fail_closed_backup_flow(self):
        self._verified_open()
        self.window._on_ready("lock", None)
        self.app.processEvents()
        self.window._on_ready(
            "unlock", _open_result("deferred", "", self.window.executor.seed_folder))
        self.app.processEvents()
        self.assertTrue(self.window._backup_flow_active)
        self.assertFalse(self.window._ready)
        self.assertEqual(self.window.stack.currentWidget(), self.window.backup_page)

    def test_unlock_refusal_keeps_wallet_locked_and_allows_retry(self):
        self._verified_open()
        self.window._on_ready("lock", None)
        self.app.processEvents()
        self.window._on_denied("WALLET_UNLOCK_REFUSED")
        self.app.processEvents()
        self.assertFalse(self.window._ready)
        self.assertTrue(self.window.unlock.isEnabled())
        # Retry path is still available for a corrected password attempt.
        self.window._on_ready(
            "unlock", _open_result("verified", "", self.window.executor.seed_folder))
        self.app.processEvents()
        self.assertTrue(self.window._ready)


class LockUnlockSourceContract(unittest.TestCase):
    """Static module hygiene for the in-session Lock <-> Unlock surface."""

    def test_gui_uses_authenticated_in_session_unlock(self):
        owner_source = (
            Path(__file__).resolve().parents[1]
            / "src" / "wam_regtest" / "bip39_owner_gui.py"
        ).read_text(encoding="utf8")
        self.assertIn("_unlock_prompt", owner_source)
        self.assertIn("EchoMode.Password", owner_source)
        self.assertIn('self._command("unlock", password, False)', owner_source)
        self.assertIn('self._unlock_allowed', owner_source)
        self.assertIn("QSettings", owner_source)
        self.assertIn("last_bip39_profile", owner_source)
        self.assertIn("_remember_profile", owner_source)
        self.assertNotIn('root = Path(remembered)', owner_source)
        self.assertIn("Unlock wallet", owner_source)

    def test_backend_reopen_revalidates_same_original_profile(self):
        backend_source = (
            Path(__file__).resolve().parents[1]
            / "src" / "wam_regtest" / "bip39_owner_backend.py"
        ).read_text(encoding="utf8")
        self.assertIn("def _reopen_q06", backend_source)
        self.assertIn('if action == "unlock":', backend_source)
        self.assertIn("Q06_GUI_UNLOCK_ARGUMENTS_DENIED", backend_source)
        self.assertIn("Q06_GUI_ALREADY_UNLOCKED", backend_source)
        self.assertIn("Q06_GUI_BACKUP_ACK_TAMPERED", backend_source)


class RecoveryUxSourceContract(unittest.TestCase):
    """Static module hygiene for the owner-approved recovery/backup UX."""

    def _read_source(self, name):
        return (Path(__file__).resolve().parents[1]
                / "src" / "wam_regtest" / name).read_text(encoding="utf8")

    def test_owner_gui_uses_custom_recovery_modal(self):
        source = self._read_source("bip39_owner_gui.py")
        self.assertIn("Bip39RecoveryVerifyDialog", source)
        self.assertIn("_on_recovery_verify_requested", source)
        self.assertIn("_on_recovery_verify_cancelled", source)
        self.assertIn('self._command("recovery_verify", phrase)', source)
        self.assertNotIn("Independent BIP39 history recovery", source)

    def test_backup_page_uses_owner_approved_step_ui(self):
        source = self._read_source("bip39_backup_page.py")
        self.assertIn("_step_label", source)
        self.assertIn("_step_progress", source)
        self.assertIn("_verify_cards_row", source)
        self.assertIn("ResponsiveRow", source)


class RecoveryVerifyDispatchContract(unittest.TestCase):
    """Owner window wires the custom modal into the backend recovery command."""

    def setUp(self):
        if importlib.util.find_spec("PySide6") is None:
            self.skipTest("Native Qt widgets verified on Qt-capable runners")
        self.app, self.window = _make_window()

    def tearDown(self):
        self.window._poll.stop()
        worker = self.window._worker
        if worker is not None:
            self.assertTrue(worker.wait(2000))
        self.app.processEvents()
        self.window.hide()
        self.window.deleteLater()
        self.app.processEvents()

    def test_owner_window_dispatches_custom_dialog_phrase_to_backend(self):
        from unittest import mock
        with mock.patch.object(self.window, "_command") as command:
            self.window._on_recovery_verify_requested(_DISPLAY_PHRASE_WORDS)
            command.assert_called_once_with("recovery_verify", _DISPLAY_PHRASE_WORDS)
        self.assertIsNone(self.window._recovery_dialog)
        self.window._on_recovery_verify_cancelled()
        self.assertIsNone(self.window._recovery_dialog)


class RecoveryVerifyDialogContract(unittest.TestCase):
    """Owner-approved Scope A: custom independent 12-word recovery modal."""

    def setUp(self):
        if importlib.util.find_spec("PySide6") is None:
            self.skipTest("Native Qt widgets verified on Qt-capable runners")
        self.app, self.window = _make_window()

    def tearDown(self):
        self.window._poll.stop()
        worker = self.window._worker
        if worker is not None:
            self.assertTrue(worker.wait(2000))
        self.app.processEvents()
        self.window.hide()
        self.window.deleteLater()
        self.app.processEvents()

    def _make_dialog(self):
        dialog = Bip39RecoveryVerifyDialog(self.window)
        self.verified_phrase = None
        self.cancelled_flag = False

        def _capture_verify(phrase):
            self.verified_phrase = phrase

        def _capture_cancel():
            self.cancelled_flag = True

        dialog.verify_requested.connect(_capture_verify)
        dialog.cancelled.connect(_capture_cancel)
        dialog.show()
        self.app.processEvents()
        return dialog

    def test_dialog_layout_is_three_by_four_numbered_fields(self):
        dialog = self._make_dialog()
        self.dialog = dialog
        self.assertEqual(len(dialog.findChildren(QLineEdit)), 12)
        self.assertEqual(dialog._grid.columnCount(), 3)
        self.assertEqual(dialog._grid.rowCount(), 4)
        labels = sorted(
            w.text() for w in dialog.findChildren(QLabel)
            if str(w.text()).startswith("WORD "))
        self.assertEqual(labels, sorted(f"WORD {i:02d}" for i in range(1, 13)))
        self.assertFalse(dialog._verify_button.isEnabled())
        self.assertEqual(dialog._count_label.text(), "0/12 words entered")

    def test_verify_requires_full_valid_checksum_phrase(self):
        dialog = self._make_dialog()
        self.dialog = dialog
        words = _DISPLAY_PHRASE_WORDS.split()
        broken = list(words)
        broken[0] = Mnemonic("english").wordlist[1]
        for field, word in zip(dialog._fields, words):
            field.setText(word)
        self.app.processEvents()
        self.assertTrue(dialog._verify_button.isEnabled())
        dialog._fields[0].setText(broken[0])
        self.app.processEvents()
        self.assertFalse(dialog._verify_button.isEnabled())
        self.verified_phrase = None
        dialog._on_verify_phrase()
        self.app.processEvents()
        self.assertIsNone(self.verified_phrase)
        for field, word in zip(dialog._fields, words):
            field.setText(word)
        self.app.processEvents()
        self.assertTrue(dialog._verify_button.isEnabled())
        _find_button(dialog, "Verify phrase").click()
        self.app.processEvents()
        self.assertEqual(self.verified_phrase, _DISPLAY_PHRASE_WORDS)

    def test_full_phrase_paste_splits_fields_and_clear_all_resets(self):
        dialog = self._make_dialog()
        self.dialog = dialog
        words = _DISPLAY_PHRASE_WORDS.split()
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText("  ".join(words) + "  ")
        _find_button(dialog, "Paste 12 words").click()
        self.app.processEvents()
        for field, word in zip(dialog._fields, words):
            self.assertEqual(field.text(), word)
        self.assertTrue(dialog._verify_button.isEnabled())
        _find_button(dialog, "Clear all").click()
        self.app.processEvents()
        self.assertEqual(dialog._count_label.text(), "0/12 words entered")
        self.assertFalse(dialog._verify_button.isEnabled())
        QApplication.clipboard().setText(words[4])
        _find_button(dialog, "Paste 12 words").click()
        self.app.processEvents()
        self.assertEqual(dialog._fields[0].text(), words[4])
        self.assertEqual(dialog._count_label.text(), "1/12 words entered")

    def test_cancel_clears_fields_and_emits_cancelled(self):
        dialog = self._make_dialog()
        self.dialog = dialog
        words = _DISPLAY_PHRASE_WORDS.split()
        dialog._fields[0].setText(words[0])
        self.assertEqual(dialog._count_label.text(), "1/12 words entered")
        _find_button(dialog, "Cancel").click()
        self.app.processEvents()
        self.assertTrue(self.cancelled_flag)
        self.assertEqual(dialog._fields[0].text(), "")
        self.assertFalse(dialog._verify_button.isEnabled())

    def test_sequential_tab_backspace_and_return_navigation(self):
        dialog = self._make_dialog()
        self.dialog = dialog
        # Cocoa activation is asynchronous. Establish the actual key window
        # before asserting keyboard focus; show()/processEvents() alone can
        # return while activation still belongs to the previous test window.
        dialog.activateWindow()
        self.assertTrue(QTest.qWaitForWindowActive(dialog, 2000))
        dialog._fields[3].setFocus()
        self.assertTrue(dialog._fields[3].hasFocus())
        QTest.keyClick(dialog._fields[3], Qt.Key_Backspace)
        self.app.processEvents()
        self.assertTrue(dialog._fields[2].hasFocus())
        QTest.keyClick(dialog._fields[2], Qt.Key_Tab)
        self.app.processEvents()
        self.assertTrue(dialog._fields[3].hasFocus())
        QTest.keyClick(dialog._fields[3], Qt.Key_Backtab)
        self.app.processEvents()
        self.assertTrue(dialog._fields[2].hasFocus())
        dialog._on_field_returned(0)
        self.app.processEvents()
        self.assertTrue(dialog._fields[1].hasFocus())

    def test_dialog_dismiss_clears_references(self):
        dialog = self._make_dialog()
        self.dialog = dialog
        dialog._fields[0].setText(_DISPLAY_PHRASE_WORDS.split()[0])
        dialog.reject()
        self.app.processEvents()
        self.assertTrue(self.cancelled_flag)
        self.assertEqual(dialog._fields[0].text(), "")


if __name__ == "__main__":
    unittest.main()
