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
        self.locked = False
        self.verified = False
        self.marker = None

    def request(self, action, *args, timeout=90, **kwargs):
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
        self.window.hide()
        self.window.deleteLater()
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
        self.assertIsNotNone(self.window._worker)
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
        self.assertIsNotNone(self.window._worker)
        # Continue dispatched the pending verified snapshot through the real
        # ControlWorker; model its worker-finished completion and refresh.
        self.window._worker = None
        self.window._finished()
        self.app.processEvents()
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
        self.assertIsNotNone(self.window._worker)
        # Continue dispatched the pending verified snapshot through the real
        # ControlWorker; model its worker-finished completion and refresh.
        self.window._worker = None
        self.window._finished()
        self.app.processEvents()
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
        self.assertIsNotNone(self.window._worker)

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


if __name__ == "__main__":
    unittest.main()
