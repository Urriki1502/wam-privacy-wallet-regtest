"""K-01 GUI unit/negative contracts. No genuine Core or wallet acceptance here.

All displayed test mnemonics below are generated from public, deterministic
all-zero entropy; never reuse them with funds. No screenshots, clipboard,
exports or mnemonic-bearing assertion messages.
"""
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QDialog
from mnemonic import Mnemonic
from wam_regtest.desktop import qt_application
from wam_regtest.bip39_gui import Bip39CreationDialog


PUBLIC_12=Mnemonic("english").to_mnemonic(bytes(16))
PUBLIC_24=Mnemonic("english").to_mnemonic(bytes(32))


class Bip39WizardContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=qt_application()

    def make(self, words=12):
        dialog=Bip39CreationDialog()
        self.addCleanup(self.cleanup_dialog,dialog)
        dialog.word_count.setCurrentIndex(0 if words==12 else 1)
        self.assertFalse(dialog.generate_button.isEnabled())
        dialog.ack.setChecked(True)
        self.assertTrue(dialog.generate_button.isEnabled())
        return dialog

    def cleanup_dialog(self,dialog):
        from shiboken6 import delete,isValid
        if isValid(dialog):
            dialog.reject()
            delete(dialog)
            self.app.processEvents()

    def test_creation_does_not_claim_a_wallet_or_persist_seed(self):
        dialog=self.make(12)
        with patch("wam_regtest.bip39_gui.generate_phrase",
                   return_value=PUBLIC_12) as generate:
            dialog._generate()
        generate.assert_called_once_with(12,authorized_disposable=True)
        self.assertIn("NOT LINKED",dialog.warning.text())
        self.assertIn("NOT A CREATED",dialog.status.text())
        self.assertEqual(dialog._phase,"show")
        self.assertEqual(len(dialog._phrase.split()),12)
        self.assertFalse(dialog.word_count.isEnabled())
        self.assertFalse(dialog.words_view.textInteractionFlags())
        # The same dialog cannot secretly rotate/reissue a new recovery phrase.
        with patch("wam_regtest.bip39_gui.generate_phrase",
                   side_effect=AssertionError("SECRET_ROTATION")) as gen:
            dialog._generate()
            gen.assert_not_called()
        self.assertFalse(dialog.confirmed)
        dialog.reject()
        self.assertIsNone(dialog._phrase)
        self.assertEqual(dialog.words_view.text(),"")
        self.assertEqual(dialog.confirm_text.toPlainText(),"")
        self.assertEqual(dialog.result(),QDialog.DialogCode.Rejected)

    def test_full_24_word_backup_requires_exact_order_and_passphrase(self):
        dialog=self.make(24)
        with patch("wam_regtest.bip39_gui.generate_phrase",return_value=PUBLIC_24):
            dialog._generate()
        dialog._advance()
        self.assertEqual(dialog.words_view.text(),"")
        self.assertIsNotNone(dialog._phrase)
        self.assertEqual(dialog._phase,"confirm")
        # A checksum-valid but different 24-word phrase must not pass.
        dialog.confirm_text.setPlainText(PUBLIC_12)
        dialog._verify()
        self.assertFalse(dialog.confirmed)
        self.assertEqual(dialog.confirm_text.toPlainText(),"")
        # Matching recovery phrase with an unacknowledged optional passphrase
        # must still refuse, never generate/persist a wallet.
        dialog.confirm_text.setPlainText(PUBLIC_24)
        dialog.passphrase.setText("public-TREZOR-passphrase")
        dialog.passphrase_confirmation.setText("public-TREZOR-passphrase")
        dialog._verify()
        self.assertFalse(dialog.confirmed)
        self.assertEqual(dialog.passphrase.text(),"")
        dialog.confirm_text.setPlainText(PUBLIC_24)
        dialog.passphrase.setText("public-TREZOR-passphrase")
        dialog.passphrase_confirmation.setText("different")
        dialog.extra_ack.setChecked(True)
        dialog._verify()
        self.assertFalse(dialog.confirmed)
        dialog.confirm_text.setPlainText(PUBLIC_24)
        dialog.passphrase.setText("public-TREZOR-passphrase")
        dialog.passphrase_confirmation.setText("public-TREZOR-passphrase")
        dialog._verify()
        self.assertTrue(dialog.confirmed)
        self.assertEqual(dialog.result(),QDialog.DialogCode.Accepted)
        self.assertIsNone(dialog._phrase)
        self.assertEqual(dialog.words_view.text(),"")
        self.assertEqual(dialog.confirm_text.toPlainText(),"")
        self.assertEqual(dialog.passphrase.text(),"")
        self.assertEqual(dialog.passphrase_confirmation.text(),"")
        self.assertEqual(repr(dialog),"<Bip39CreationDialog redacted>")

    def test_empty_passphrase_and_unconfirmed_accept_are_distinct(self):
        dialog=self.make(12)
        dialog.accept()
        self.assertNotEqual(dialog.result(),QDialog.DialogCode.Accepted)
        with patch("wam_regtest.bip39_gui.generate_phrase",return_value=PUBLIC_12):
            dialog._generate()
        dialog._advance()
        dialog.confirm_text.setPlainText(PUBLIC_12)
        dialog._verify()
        self.assertTrue(dialog.confirmed)
        self.assertIsNone(dialog._phrase)

    def test_wordlist_failure_clears_ui_without_core_or_fallback(self):
        dialog=self.make()
        with patch("wam_regtest.bip39_gui.generate_phrase",
                   side_effect=ValueError("PRIVATE_INTERNAL_CANARY")):
            dialog._generate()
        self.assertIsNone(dialog._phrase)
        self.assertNotIn("PRIVATE_INTERNAL_CANARY",dialog.status.text())
        self.assertNotIn("PRIVATE_INTERNAL_CANARY",repr(dialog))
        self.assertFalse(dialog.confirmed)
        self.assertEqual(dialog.words_view.text(),"")


if __name__=="__main__":
    unittest.main()
