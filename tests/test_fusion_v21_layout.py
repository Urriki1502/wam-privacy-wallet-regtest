"""Fusion UI V2.1 layout, status mapping and motion contracts. Not live-Core evidence."""
from __future__ import annotations

import os
import unittest
from dataclasses import replace

from PySide6.QtCore import Qt, QRect
from PySide6.QtWidgets import QAbstractButton, QDialog, QLabel, QToolButton

from wam_regtest.desktop import qt_application
from wam_regtest.fusion_status import classify
from wam_regtest.fusion_ui import FlowGrid, FusionOverview, StatusCard
from wam_regtest.fusion_motion import StatusGlyph, TransitionHost, motion_reduced
from wam_regtest.wallet_read import HistoryRow, WalletReadSnapshot


def verified_snapshot():
    return WalletReadSnapshot(
        chain="regtest", height=110, tip="a" * 64,
        receive_code="wamrtsp1-public-demo-test",
        confirmed_atoms=150000000, confirmed_utxos=2,
        history=(
            HistoryRow("b" * 64, 108, 3, 200000000, 0),
            HistoryRow("c" * 64, 110, 1, 0, 50000000),
        ),
        core_sha256="e" * 64,
    )


def label_fits(widget):
    if widget.width() <= 0 or widget.height() <= 0:
        return False
    text = widget.text()
    br = widget.fontMetrics().boundingRect(
        QRect(0, 0, max(1, widget.width()), 4000),
        Qt.TextFlag.TextWordWrap, text)
    return br.height() <= widget.height() + 2 and br.width() <= widget.width() + 4


class FusionStatusMapping(unittest.TestCase):
    def test_unknown_and_offline_are_never_verified(self):
        for kind in ("core", "chain", "security", "network", "snapshot"):
            state, title, detail = classify(kind, snap=None, core_alive=False)
            self.assertNotEqual(state, "verified")
            self.assertNotIn("green", title.lower())
            self.assertTrue(detail)

    def test_core_identity_is_not_live_process_proof(self):
        state, title, detail = classify("core", snap=verified_snapshot(), core_alive=False)
        self.assertEqual(state, "warning")
        self.assertIn("pinned", title.lower())
        self.assertIn("not connected", detail.lower())

    def test_unlocked_is_not_a_green_health_badge(self):
        state, title, detail = classify(
            "security", snap=verified_snapshot(), locked=False, operational=True)
        self.assertEqual(state, "warning")
        self.assertEqual(title, "Unlocked")
        self.assertIn("not a security score", detail.lower())

    def test_busy_snapshot_is_pending_not_verified(self):
        state, title, _ = classify("snapshot", snap=None, busy=True, core_alive=True)
        self.assertEqual(state, "pending")
        self.assertNotEqual(title, "Verified")


class FusionV21LayoutAndMotion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = qt_application()

    def test_compact_overview_has_no_horizontal_overflow_or_clipped_status(self):
        page = FusionOverview()
        self.addCleanup(page.deleteLater)
        page.render_snapshot(
            verified_snapshot(), operational=True, core_alive=False,
            network={"mode": "Isolated REGTEST"})
        page.resize(680, 720)
        page.show()
        self.app.processEvents()
        page.status_board.resizeEvent(None)
        self.app.processEvents()
        self.assertEqual(
            page.horizontalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.assertLessEqual(page.horizontalScrollBar().maximum(), 0)
        for card in (page.core_card, page.chain_card, page.security_card, page.network_card):
            self.assertGreaterEqual(card.height(), 64)
            self.assertTrue(label_fits(card.value), card.value.text())
            titles = [item for item in card.findChildren(QLabel)
                      if item.objectName() == "FusionCardTitle"]
            self.assertTrue(titles)
            self.assertTrue(label_fits(titles[0]), titles[0].text())
        self.assertEqual(page.core_card.glyph.state(), "warning")
        self.assertIn("Identity pinned", page.core_status.text())
        self.assertIn("1.50000000", page.balance_value.text())
        self.assertTrue(
            "WAM" in page.balance_value.text() or page.balance_unit.isVisible())
        self.assertEqual(page.findChildren(QToolButton, "FusionQuick"), [])
        self.assertTrue(page.go_send.isVisible())
        self.assertTrue(page.go_receive.isVisible())
        self.assertTrue(page.balance_chart.isVisible())
        self.assertGreaterEqual(page.verticalScrollBar().maximum(), 0)
        page.verticalScrollBar().setValue(page.verticalScrollBar().maximum())
        self.app.processEvents()
        self.assertTrue(page.security_card.isVisible())
        self.assertTrue(label_fits(page.security_card.value), page.security_card.value.text())

    def test_flow_grid_uses_two_columns_when_four_do_not_fit(self):
        cards = [StatusCard("WAM Core", "Pinned binary identity") for _ in range(4)]
        grid = FlowGrid(*cards, min_item=210, max_columns=4)
        self.addCleanup(grid.deleteLater)
        grid.resize(500, 400)
        grid.show()
        self.app.processEvents()
        grid.resizeEvent(None)
        self.assertEqual(grid._columns, 2)

    def test_status_spinner_stops_on_terminal_state(self):
        glyph = StatusGlyph()
        self.addCleanup(glyph.deleteLater)
        glyph.set_state("pending", animate=False)
        if not motion_reduced(glyph):
            self.assertTrue(glyph._spin.isActive())
        glyph.set_state("error", animate=False)
        self.assertFalse(glyph._spin.isActive())
        self.assertEqual(glyph.state(), "error")

    def test_rapid_transition_host_settles_on_latest_index(self):
        host = TransitionHost()
        self.addCleanup(host.deleteLater)
        from PySide6.QtWidgets import QLabel
        for name in ("a", "b", "c"):
            host.addWidget(QLabel(name))
        host.resize(400, 300)
        host.show()
        self.app.processEvents()
        host.set_current(1, reduced=True)
        host.set_current(2, reduced=True)
        host.set_current(0, reduced=True)
        self.assertEqual(host.currentIndex(), 0)
        self.assertEqual(host.currentWidget().text(), "a")

    def test_quick_actions_are_absent_and_workflows_remain_on_pages(self):
        from types import SimpleNamespace
        from wam_regtest.wallet_executor import ExecutorState
        from wam_regtest.bip39_fusion_gui import Bip39FusionWindow
        owner = SimpleNamespace(state=ExecutorState(), busy=False, closed=False)
        window = Bip39FusionWindow(owner)
        self.addCleanup(window.deleteLater)
        window._poll.stop()
        window.show()
        self.app.processEvents()
        self.assertEqual(window.overview.findChildren(QToolButton, "FusionQuick"), [])
        labels = " ".join(item.text() for item in window.overview.findChildren(QLabel))
        self.assertNotIn("Quick actions", labels)
        self.assertNotIn("Wallet environment", labels)
        self.assertTrue(window.recovery.isVisible() or window.recovery.parent() is not None)
        self.assertTrue(window.custody_switch.isVisible() or window.custody_switch.parent() is not None)
        self.assertTrue(window.backup_review.isVisible() or window.backup_review.parent() is not None)
        self.assertTrue(window.network_page is not None)
        window.navigation.setCurrentRow(5)
        self.app.processEvents()
        self.assertEqual(window.stack.currentWidget(), window.network_page)
        window.reduce_motion.setChecked(True)
        window._play_overview_intro()
        self.assertTrue(window.reduce_motion.isChecked())

    def test_theme_controls_stay_synchronized(self):
        from types import SimpleNamespace
        from wam_regtest.wallet_executor import ExecutorState
        from wam_regtest.bip39_fusion_gui import Bip39FusionWindow
        owner = SimpleNamespace(state=ExecutorState(), busy=False, closed=False)
        window = Bip39FusionWindow(owner)
        self.addCleanup(window.deleteLater)
        window._poll.stop()
        window.appearance_buttons[0].click()
        window.settings_theme.setCurrentIndex(2)
        self.assertEqual(window.header_theme.currentIndex(), 2)
        self.assertEqual(window.appearance_group.checkedId(), 2)

    def test_quick_backup_dialog_defaults_to_cancel_and_hides_seed(self):
        from types import SimpleNamespace
        from wam_regtest.wallet_executor import ExecutorState
        from wam_regtest.bip39_fusion_gui import Bip39FusionWindow
        owner = SimpleNamespace(state=ExecutorState(), busy=False, closed=False)
        window = Bip39FusionWindow(owner)
        self.addCleanup(window.deleteLater)
        window._poll.stop()
        dialogs = []
        original = window._quick_backup

        def wrapped():
            from wam_regtest.fusion_pages import WalletConsent
            real = WalletConsent
            seen = []

            class Spy(real):
                def exec(self):
                    seen.append(self)
                    self.reject()
                    return QDialog.DialogCode.Rejected
            import wam_regtest.bip39_fusion_gui as gui
            previous = gui.WalletConsent
            gui.WalletConsent = Spy
            try:
                original()
            finally:
                gui.WalletConsent = previous
            dialogs.extend(seen)

        wrapped()
        self.assertEqual(len(dialogs), 1)
        self.assertNotIn("mnemonic", dialogs[0].windowTitle().lower())

    def test_reduced_motion_skips_page_travel(self):
        previous = os.environ.get("QT_REDUCE_MOTION")
        os.environ["QT_REDUCE_MOTION"] = "1"
        self.addCleanup(lambda: (
            os.environ.__setitem__("QT_REDUCE_MOTION", previous)
            if previous is not None else os.environ.pop("QT_REDUCE_MOTION", None)))
        host = TransitionHost()
        self.addCleanup(host.deleteLater)
        host.addWidget(QLabel("one"))
        host.addWidget(QLabel("two"))
        host.resize(320, 200)
        host.show()
        self.app.processEvents()
        host.set_current(1)
        self.assertEqual(host.currentIndex(), 1)
        self.assertIsNone(host._motion)

    def test_status_glyph_never_verified_for_unknown(self):
        glyph = StatusGlyph()
        self.addCleanup(glyph.deleteLater)
        glyph.set_state("unknown", animate=False)
        self.assertEqual(glyph.state(), "unknown")
        self.assertFalse(glyph._spin.isActive())

    def test_compact_chart_stays_visible_without_horizontal_overflow(self):
        page = FusionOverview()
        self.addCleanup(page.deleteLater)
        page.render_snapshot(verified_snapshot(), operational=True, core_alive=False)
        page.resize(520, 760)
        page.show()
        self.app.processEvents()
        page.hero.resizeEvent(None)
        self.app.processEvents()
        self.assertTrue(page.balance_chart.isVisible())
        self.assertLessEqual(page.horizontalScrollBar().maximum(), 0)
        self.assertIn("1.50000000", page.balance_value.text())

    def test_broadcast_result_semantics_unchanged(self):
        from wam_regtest.fusion_pages import describe_broadcast_result
        txid = "1e66b1d7d7c14d914ac34d523b3d2a9847521e7786fe5c9ba8a1cfa5cee6ff77"
        self.assertIn("pending in this Core mempool", describe_broadcast_result(txid, {
            "status": "Q06_TX_NOT_IN_CONFIRMED_HISTORY", "in_mempool": True,
        }))
        self.assertTrue(describe_broadcast_result(txid, {
            "status": "Q06_CONFIRMED_IN_VERIFIED_HISTORY", "in_mempool": False,
        }).startswith("Confirmed"))


if __name__ == "__main__":
    unittest.main()
