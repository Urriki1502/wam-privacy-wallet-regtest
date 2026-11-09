"""Clipboard adapter may notify an ownership change during its current read."""
import os
import sys
import unittest
from unittest.mock import patch

if sys.platform == "linux" and not os.environ.get("DISPLAY"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from wam_regtest.desktop import qt_application
    from wam_regtest.bip39_owner_gui import Bip39RecoveryVerifyDialog
except ImportError:
    qt_application = None


@unittest.skipIf(qt_application is None, "PySide6 required")
class ClipboardReadTransition(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use the existing application lifetime; never destroy/recreate Qt.
        cls.app = qt_application()

    def test_republished_same_text_during_final_read_is_not_cleared(self):
        dialog = Bip39RecoveryVerifyDialog()
        clip = self.app.clipboard()
        public = "abandon " * 11 + "about"
        clip.setText(public)
        real = clip.text
        reads = 0

        def read(*args):
            nonlocal reads
            reads += 1
            if reads == 2:
                clip.setText("public intermediate")
                clip.setText(public)
            return real(*args)

        try:
            with patch.object(clip, "text", read):
                dialog._on_paste()
            self.assertEqual(real(), public)
        finally:
            clip.clear()
            dialog.reject()
            dialog.deleteLater()
            self.app.processEvents()
