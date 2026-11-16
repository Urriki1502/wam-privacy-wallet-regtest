"""Displayed BIP39 backup words cannot be selected or copied (X11 PRIMARY, clipboard history)."""
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QLabel
except ImportError:  # headless Linux qualification env has no Qt
    Qt = None


@unittest.skipIf(Qt is None, 'PySide6 not installed (headless no-Qt environment)')
class BackupWordsNotSelectable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_word_cards_have_no_text_interaction_or_context_menu(self):
        from wam_regtest.bip39_backup_page import _WordCard
        card = _WordCard(1, 'abandon')
        try:
            labels = [w for w in card.findChildren(QLabel) if w.text() == 'abandon']
            self.assertEqual(len(labels), 1)
            word = labels[0]
            self.assertEqual(word.textInteractionFlags(), Qt.TextInteractionFlag.NoTextInteraction)
            self.assertEqual(word.contextMenuPolicy(), Qt.ContextMenuPolicy.NoContextMenu)
            self.assertFalse(word.hasSelectedText())
        finally:
            card.deleteLater()


if __name__ == '__main__':
    unittest.main()
