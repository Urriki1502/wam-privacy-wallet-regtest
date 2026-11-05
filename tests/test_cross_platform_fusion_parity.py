"""Source wiring of the shared V2.2 Fusion desktop. Not native Win/Linux PASS."""
from pathlib import Path
import ast
import sys
import unittest

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel

from wam_regtest.desktop import qt_application
from wam_regtest.fusion_pages import PaymentApproval
from wam_regtest.fusion_ui import FUSION_NAV_PAGES
from wam_regtest.wallet_session import PaymentReview

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "wam_regtest"


class CrossPlatformFusionParity(unittest.TestCase):
    def test_desktop_entries_share_welcome_and_fusion_not_a_second_backend(self):
        onboarding = (SRC / "managed_onboarding.py").read_text()
        owner = (SRC / "bip39_owner_gui.py").read_text()
        self.assertIn("launch_bip39_trial", onboarding)
        self.assertIn("Bip39FusionWindow", owner)
        self.assertIn("from wam_regtest.managed_onboarding import launch",
                      (SRC / "windows_package_entry.py").read_text())
        self.assertIn("from wam_regtest.managed_onboarding import launch",
                      (SRC / "linux_package_entry.py").read_text())
        self.assertIn("from wam_regtest.managed_onboarding import launch",
                      (SRC / "package_entry.py").read_text())
        extras = list((ROOT / "scripts").glob("build_windows_*.py"))
        self.assertEqual(extras, [ROOT / "scripts" / "build_windows_bundle.py"])

    def test_win_linux_frozen_q06_probe_binds_v22_overview_and_approval(self):
        text = (SRC / "q06_platform_probe.py").read_text()
        self.assertIn("balance_chart", text)
        self.assertIn("Quick Actions", text)
        self.assertIn("PaymentApproval", text)
        self.assertIn("ApplicationModal", text)
        self.assertIn("inspect_confirmed", text)
        self.assertNotIn("shared_network_probe", text)

    def test_win_linux_entries_do_not_import_cocoa_v1_net_lab(self):
        for name in ("windows_package_entry.py", "linux_package_entry.py"):
            tree = ast.parse((SRC / name).read_text())
            imports = [alias.name for node in ast.walk(tree)
                       if isinstance(node, ast.ImportFrom) and node.module
                       for alias in node.names]
            self.assertNotIn("shared_network_probe", imports)

    def test_shared_regtest_identity_constants_are_unmodified(self):
        from wam_regtest.shared_regtest import MAGIC
        self.assertEqual(MAGIC, b"WAMR")
        self.assertEqual(MAGIC.hex(), "57414d52")
        probe = (SRC / "shared_network_probe.py").read_text()
        self.assertIn("b88f3d262f285e38e184f50bf3eea1c8e615486ae67d3d9eaf0976fbd6d3d30d", probe)
        self.assertIn("29554", probe)
        self.assertIn("29555", probe)

    def test_payment_approval_default_cancel_is_application_modal(self):
        qt_application()
        review = PaymentReview("wamrtsp1public", 100000, 10000, 400000, 1, "a" * 64)
        dialog = PaymentApproval(review, "sign", None)
        self.addCleanup(dialog.deleteLater)
        self.assertEqual(dialog.windowModality(), Qt.WindowModality.ApplicationModal)
        self.assertTrue(dialog.cancel.isDefault())
        self.assertFalse(dialog.approve.isDefault())
        self.assertEqual(dialog.approve.text(), "Approve Sign")
        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)

    def test_fusion_overview_has_v22_hierarchy_and_no_quick_actions(self):
        from types import SimpleNamespace
        from wam_regtest.bip39_fusion_gui import Bip39FusionWindow
        from wam_regtest.wallet_executor import ExecutorState
        app = qt_application()
        window = Bip39FusionWindow(SimpleNamespace(
            state=ExecutorState(), busy=False, closed=False))
        self.addCleanup(window.deleteLater)
        window._poll.stop()
        window.show()
        app.processEvents()
        self.assertEqual(
            [window.navigation.item(i).text() for i in range(window.navigation.count())],
            [name for name, _ in FUSION_NAV_PAGES],
        )
        self.assertTrue(hasattr(window.overview, "balance_chart"))
        self.assertTrue(hasattr(window.overview, "go_send"))
        self.assertTrue(hasattr(window.overview, "go_receive"))
        self.assertTrue(hasattr(window, "network_page"))
        labels = [w.text() for w in window.findChildren(QLabel) if w.text()]
        self.assertFalse(any("Quick Actions" in text for text in labels))
        for width, height in ((1024, 768), (1280, 800), (1440, 900)):
            window.resize(width, height)
            app.processEvents()
            self.assertGreaterEqual(window.width(), 900)
            self.assertTrue(window.overview.balance_value.isVisible())
        window.hide()

    @unittest.skipUnless(sys.platform == "darwin", "this host is Darwin; Win 125/150 DPI remains native")
    def test_this_host_cannot_claim_windows_dpi_or_linux_xcb_pass(self):
        self.assertNotEqual(sys.platform, "win32")
        self.assertNotEqual(sys.platform, "linux")


if __name__ == "__main__":
    unittest.main()
