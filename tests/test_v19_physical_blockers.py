"""V19 physical-acceptance regressions (macOS Reconcile clipping, shared fault code).

Source/widget contracts only; genuine-Core reproduction evidence is retained
separately and is not inferred from these tests.
"""
import importlib.util
import json
import os
import sys
import unittest

if sys.platform == "linux" and not os.environ.get("DISPLAY"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import test_q05_core_supervisor as fixture
from wam_regtest.shared_regtest import SharedRegtestError
from wam_regtest.supervisor_store import read_exact

_TITLE = 'Reconcile original Shared REGTEST wallet'
_MESSAGE = ('Authenticate this original profile and reconstruct observation from its latest native '
            'checkpoint. A competing branch requires greater verified Core work. Signed/unknown '
            'reservations and old runtime evidence stay retained. No payment is retried. Sending '
            'requires a separate approval afterwards.')


class ConsentDialogLayout(unittest.TestCase):
    def setUp(self):
        if importlib.util.find_spec("PySide6") is None:
            self.skipTest("Qt widgets verified on Qt-capable runners")

    def test_wrapped_title_and_explanation_are_never_clipped(self):
        from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QPushButton
        from wam_regtest.fusion_pages import WalletConsent
        from wam_regtest.fusion_ui import fusion_stylesheet
        app = QApplication.instance() or QApplication([])
        dialog = WalletConsent(_TITLE, _MESSAGE, None, password=True, accept_text='Reconcile')
        try:
            dialog.setStyleSheet(fusion_stylesheet('dark'))
            dialog.show()
            app.processEvents(); app.processEvents()
            texts = {w.text(): w for w in dialog.findChildren(QLabel)}
            for text in (_TITLE, _MESSAGE):
                widget = texts[text]
                self.assertGreaterEqual(widget.height(), widget.heightForWidth(widget.width()), text[:20])
            rect = dialog.rect()
            for cls in (QLineEdit, QPushButton):
                for widget in dialog.findChildren(cls):
                    if widget.isVisible():
                        self.assertTrue(rect.contains(widget.mapTo(dialog, widget.rect().bottomRight())))
            self.assertTrue(dialog.password_input.isVisible())
        finally:
            dialog.hide()
            dialog.deleteLater()
            app.processEvents()


class SharedFaultDiagnostic(unittest.TestCase):
    setUp = fixture.SupervisorLifecycleUnit.setUp
    owner = fixture.SupervisorLifecycleUnit.owner

    def test_unexpected_shared_peer_is_recorded_with_its_public_code(self):
        owner = self.owner()
        owner._record_failure('status', SharedRegtestError('SHARED_UNEXPECTED_PEER_DENIED'))
        self.assertEqual(json.loads(read_exact(owner.root, 'supervisor.failure')),
                         {'stage': 'status', 'code': 'SHARED_UNEXPECTED_PEER_DENIED'})

    def test_shared_error_with_free_text_still_never_echoes(self):
        owner = self.owner()
        owner._record_failure('status', SharedRegtestError('peer 192.168.1.9 secret'))
        raw = read_exact(owner.root, 'supervisor.failure')
        self.assertNotIn(b'192.168', raw)
        self.assertEqual(json.loads(raw)['code'], 'MANAGED_UNCLASSIFIED_FAILURE')


if __name__ == '__main__':
    unittest.main()
