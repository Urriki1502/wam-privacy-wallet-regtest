"""K-01: local BIP39 recovery-phrase creation/confirmation wizard (REGTEST).

This deliberately does NOT create/rekey an original managed WSP wallet:
K-02 defines its final derivation profile; K-03 binds seed to native custody
and signer. Existing 32-byte WSP Keyring backups are not BIP39 mnemonics.

No mnemonic, BIP39 passphrase or seed crosses a Qt signal, log, file, Core
socket, clipboard or persisted checkpoint. Python and Qt cannot guarantee
secure memory erasure or prevent OS-level screenshots.
"""
from __future__ import annotations

import secrets
import unicodedata

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QVBoxLayout,
)

from .bip39_wallet import generate_phrase, normalize_phrase, MnemonicWalletError


class Bip39CreationDialog(QDialog):
    """Explicit disposable 12/24-word BIP39 backup wizard, no wallet authority."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._phrase=None
        self._phase="setup"
        self._verified=False
        self.setWindowTitle("WAM Fusion REGTEST · Create BIP39 recovery words")
        self.setMinimumSize(710,410)

        layout=QVBoxLayout(self)
        self.warning=QLabel(
            "LOCAL BIP39 BACKUP ONLY · NOT LINKED TO YOUR CURRENT WSP WALLET.\n"
            "K-02/K-03 must integrate a confirmed derivation profile and native "
            "custody before these words can back a usable wallet. "
            "Never use real funds or treat this as a completed wallet backup.")
        self.warning.setWordWrap(True)
        layout.addWidget(self.warning)

        self.word_count=QComboBox()
        self.word_count.addItem("12 recovery words · 128-bit entropy",12)
        self.word_count.addItem("24 recovery words · 256-bit entropy",24)
        self.word_count.setCurrentIndex(1)
        layout.addWidget(self.word_count)

        self.ack=QCheckBox(
            "I understand: these words do NOT restore the existing Fusion "
            "wallet, and I must record them privately offline.")
        layout.addWidget(self.ack)

        self.words_view=QLabel("")
        self.words_view.setObjectName("k01WordsView")
        self.words_view.setTextFormat(Qt.TextFormat.PlainText)
        self.words_view.setTextInteractionFlags(
            Qt.TextInteractionFlag.NoTextInteraction)
        self.words_view.setStyleSheet("font-family: monospace; font-size: 12pt;")
        self.words_view.setWordWrap(True)
        self.words_view.setVisible(False)
        layout.addWidget(self.words_view)

        self.instructions=QLabel(
            "Generate locally with the verified English BIP39 wordlist. "
            "There is no clipboard/export/auto-save action.")
        self.instructions.setWordWrap(True)
        layout.addWidget(self.instructions)

        self.confirm_text=QPlainTextEdit()
        self.confirm_text.setObjectName("k01FullPhraseConfirmation")
        self.confirm_text.setPlaceholderText(
            "Type every word in its original order, from your offline notes")
        self.confirm_text.setVisible(False)
        layout.addWidget(self.confirm_text)

        self.passphrase=QLineEdit()
        self.passphrase.setObjectName("k01OptionalPassphrase")
        self.passphrase.setEchoMode(QLineEdit.EchoMode.Password)
        self.passphrase.setPlaceholderText(
            "Optional BIP39 passphrase · blank means NO extra passphrase")
        self.passphrase.setVisible(False)
        layout.addWidget(self.passphrase)

        self.passphrase_confirmation=QLineEdit()
        self.passphrase_confirmation.setObjectName("k01ConfirmPassphrase")
        self.passphrase_confirmation.setEchoMode(QLineEdit.EchoMode.Password)
        self.passphrase_confirmation.setPlaceholderText(
            "Confirm the exact optional passphrase (may be blank)")
        self.passphrase_confirmation.setVisible(False)
        layout.addWidget(self.passphrase_confirmation)

        self.extra_ack=QCheckBox(
            "If an optional passphrase is used, both the words AND this "
            "passphrase will be required; neither is stored by this wizard.")
        self.extra_ack.setVisible(False)
        layout.addWidget(self.extra_ack)

        self.status=QLabel("No recovery phrase has been created.")
        self.status.setObjectName("k01WizardStatus")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        controls=QHBoxLayout()
        self.generate_button=QPushButton("Generate words locally")
        self.generate_button.setEnabled(False)
        self.generate_button.clicked.connect(self._generate)
        self.ack.toggled.connect(self.generate_button.setEnabled)
        controls.addWidget(self.generate_button)

        self.next_button=QPushButton("Written offline · verify")
        self.next_button.setEnabled(False)
        self.next_button.setVisible(False)
        self.next_button.clicked.connect(self._advance)
        controls.addWidget(self.next_button)

        self.verify_button=QPushButton("Verify full phrase and finish")
        self.verify_button.setEnabled(False)
        self.verify_button.setVisible(False)
        self.verify_button.clicked.connect(self._verify)
        controls.addWidget(self.verify_button)

        self.cancel_button=QPushButton("Cancel and clear")
        self.cancel_button.clicked.connect(self.reject)
        controls.addWidget(self.cancel_button)
        layout.addLayout(controls)

    def __repr__(self):
        return "<Bip39CreationDialog redacted>"

    def _generate(self):
        if self._phase!="setup" or not self.ack.isChecked():
            return
        try:
            words=self.word_count.currentData()
            phrase=generate_phrase(words,authorized_disposable=True)
            if type(phrase) is not str or len(phrase.split())!=words:
                raise MnemonicWalletError("BIP39_GENERATION_INVALID")
            self._phrase=normalize_phrase(phrase)
        except Exception:
            self._clear_sensitive()
            self.status.setText("BIP39_GENERATION_DENIED")
            return
        chunks=self._phrase.split()
        # A numbered on-screen view is unavoidable for a paper backup.
        # It is not copied, serialized, cached in status or logged.
        rows=[]
        for offset in range(0,len(chunks),4):
            rows.append("    ".join(
                f"{i+1:02d} {chunks[i]}" for i in
                range(offset,min(offset+4,len(chunks)))))
        self.words_view.setText("\n".join(rows))
        self.words_view.setVisible(True)
        self.word_count.setEnabled(False)
        self.ack.setEnabled(False)
        self.generate_button.setVisible(False)
        self.next_button.setVisible(True)
        self.next_button.setEnabled(True)
        self.instructions.setText(
            "Write all numbered words on paper, in order. They will disappear "
            "from this window before confirmation. Do not take screenshots.")
        self.status.setText(
            "LOCAL BIP39 WORDS GENERATED · NOT A CREATED OR RECOVERABLE FUSION WALLET")
        self._phase="show"

    def _advance(self):
        if self._phase!="show" or self._phrase is None:
            return
        self.words_view.clear()
        self.words_view.setVisible(False)
        self.next_button.setVisible(False)
        self.confirm_text.setVisible(True)
        self.passphrase.setVisible(True)
        self.passphrase_confirmation.setVisible(True)
        self.extra_ack.setVisible(True)
        self.verify_button.setVisible(True)
        self.verify_button.setEnabled(True)
        self.instructions.setText(
            "Enter the complete phrase from your paper backup. An optional "
            "BIP39 passphrase changes the derived seed and is NOT your "
            "current Fusion wallet password.")
        self.status.setText("PHRASE CONFIRMATION REQUIRED")
        self._phase="confirm"

    def _verify(self):
        if self._phase!="confirm" or self._phrase is None:
            return
        from mnemonic import Mnemonic
        candidate=self.confirm_text.toPlainText()
        entered=self.passphrase.text()
        repeated=self.passphrase_confirmation.text()
        seed=None
        try:
            canonical=normalize_phrase(candidate)
            if not secrets.compare_digest(
                    canonical.encode("utf8"),self._phrase.encode("utf8")):
                raise MnemonicWalletError("BIP39_CONFIRMATION_DENIED")
            if (len(entered)>1024 or len(repeated)>1024
                    or (entered and not self.extra_ack.isChecked())
                    or not secrets.compare_digest(
                        entered.encode("utf8"),repeated.encode("utf8"))):
                raise MnemonicWalletError("BIP39_PASSPHRASE_CONFIRMATION_DENIED")
            if len(unicodedata.normalize("NFKD",entered).encode("utf8"))>4096:
                raise MnemonicWalletError("BIP39_PASSPHRASE_INVALID")
            # Verify the full BIP39 64-byte PBKDF2 seed path with the optional
            # passphrase locally only. Never interpret it as a legacy WSP seed,
            # derive an unapproved account profile or publish key material.
            seed=bytearray(Mnemonic.to_seed(self._phrase,passphrase=entered))
            if len(seed)!=64:
                raise MnemonicWalletError("BIP39_SEED_LENGTH_DENIED")
        except Exception:
            self.status.setText(
                "BIP39_CONFIRMATION_DENIED · re-enter words/passphrase")
            return
        finally:
            self.confirm_text.clear()
            self.passphrase.clear()
            self.passphrase_confirmation.clear()
            if seed is not None:
                seed[:]=b"\0"*len(seed)  # best effort, not OS memory sanitization
            candidate=entered=repeated=None
        self._verified=True
        self._clear_sensitive()
        self.accept()

    def _clear_sensitive(self):
        self.words_view.clear()
        self.confirm_text.clear()
        self.passphrase.clear()
        self.passphrase_confirmation.clear()
        self._phrase=None

    def accept(self):
        if not self._verified:
            return
        self._clear_sensitive()
        super().accept()

    def reject(self):
        self._verified=False
        self._clear_sensitive()
        super().reject()

    def closeEvent(self,event):
        self._clear_sensitive()
        super().closeEvent(event)

    @property
    def confirmed(self):
        """Non-secret acknowledgement; NEVER implies wallet persistence."""
        return self._verified and self.result()==QDialog.DialogCode.Accepted
