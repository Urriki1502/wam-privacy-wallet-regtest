"""Native Qt Q06 12-word REGTEST owner trial, separate from Q05 GUI.

Never show an unverified BIP39 Send/Sign button. No user keys are sent over
supervisor IPC, stored in logs, or included in native CI artifacts.
"""
from PySide6.QtCore import Qt,QTimer
from PySide6.QtWidgets import (
    QCheckBox,QDialog,QDialogButtonBox,QHBoxLayout,QInputDialog,QLabel,
    QLineEdit,QMessageBox,QPushButton,QTextEdit,QVBoxLayout,QWidget,
)

from .desktop import qt_application
from .managed_gui import ControlWorker
from .wallet_executor import WalletExecutor
from .bip39_owner_backend import Bip39ReadOnlyBackend


class Bip39TrialWindow(QWidget):
    def __init__(self, executor):
        super().__init__()
        self.executor = executor
        self._worker = None
        self._quit_requested = False
        self._closed = False
        self.setWindowTitle("WAM Fusion · BIP39 12-word REGTEST trial")
        self.resize(750, 475)
        box = QVBoxLayout(self)
        title = QLabel("WAM Fusion — BIP39 12-word · REGTEST")
        title.setStyleSheet("font-size: 19px; font-weight: bold;")
        box.addWidget(title)
        box.addWidget(QLabel("Experimental read-only wallet using the original signed WAM Core. "
                              "No mainnet, no personal keys, no spending."))
        self.status = QLabel("Native Core not opened")
        box.addWidget(self.status)
        box.addWidget(QLabel("Your BIP352 receive code (REGTEST):"))
        self.receive = QLineEdit()
        self.receive.setReadOnly(True)
        self.receive.setPlaceholderText("Unlock this Q06 wallet to view your real derived receive code")
        box.addWidget(self.receive)
        self.account = QLabel("Account: locked")
        self.balance = QLabel("Balance: unverified")
        self.tip = QLabel("Chain: unverified")
        for item in (self.account,self.balance,self.tip):box.addWidget(item)
        box.addWidget(QLabel("Verified recent REGTEST history (up to 10):"))
        self.history = QTextEdit()
        self.history.setReadOnly(True)
        self.history.setPlaceholderText("Select Sync real Core to scan the owned node")
        box.addWidget(self.history)
        bar=QHBoxLayout()
        self.sync=QPushButton("Sync real Core (read-only)")
        self.lock=QPushButton("Lock Q06")
        self.quit=QPushButton("Stop owned Core and quit")
        bar.addWidget(self.sync);bar.addWidget(self.lock);bar.addWidget(self.quit)
        box.addLayout(bar)
        self.sync.clicked.connect(lambda:self._command("snapshot"))
        self.lock.clicked.connect(lambda:self._command("lock"))
        self.quit.clicked.connect(self.request_quit)
        self._poll=QTimer(self);self._poll.timeout.connect(self._check_quit)
        self._poll.setInterval(100);self._poll.start()
        self._ready=False
        self._set_actions()

    def _set_actions(self):
        busy=self._worker is not None or self.executor.busy
        self.sync.setEnabled(self._ready and not busy and not self._quit_requested)
        self.lock.setEnabled(self._ready and not busy and not self._quit_requested)
        self.quit.setEnabled(not busy and not self.executor.closed)

    def _command(self, action, *args):
        if self._worker is not None or self.executor.busy or self.executor.closed:
            return False
        worker=ControlWorker(self.executor, action, args, parent=self)
        self._worker=worker
        worker.ready.connect(self._on_ready, Qt.ConnectionType.QueuedConnection)
        worker.denied.connect(self._on_denied, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(self._finished)
        worker.finished.connect(worker.deleteLater)
        self._set_actions()
        worker.start()
        return True

    def start(self, password, mode, phrase):
        self.status.setText("Verifying original Core, native custody and BIP39 profile…")
        self._command("open", password, mode, phrase)

    def _show_words_once(self, phrase):
        dlg=QDialog(self)
        dlg.setWindowTitle("REGTEST recovery phrase — shown once")
        layout=QVBoxLayout(dlg)
        layout.addWidget(QLabel("Write down these 12 disposable REGTEST words in order. "
                                 "They are NOT for mainnet or real funds."))
        words=QTextEdit()
        words.setPlainText(phrase)
        words.setReadOnly(True)
        words.setMinimumHeight(85)
        layout.addWidget(words)
        check=QCheckBox("I have recorded these 12 REGTEST-only words securely.")
        layout.addWidget(check)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button=buttons.button(QDialogButtonBox.StandardButton.Ok)
        button.setEnabled(False)
        check.toggled.connect(button.setEnabled)
        buttons.accepted.connect(dlg.accept)
        layout.addWidget(buttons)
        dlg.exec()
        words.clear()
        phrase=None

    def _on_ready(self, action, result):
        if action=="open":
            self._ready=True
            self.receive.setText(result["receive_code"])
            self.account.setText("BIP39 account: "+result["account_id"])
            self.balance.setText("Balance: not yet synced against Core")
            self.tip.setText("Chain: not yet verified")
            self.status.setText("BIP39 12-word encrypted native seed opened — read-only")
            if result.get("mnemonic_once"):self._show_words_once(result["mnemonic_once"])
        elif action=="snapshot":
            self.receive.setText(result["receive_code"])
            self.balance.setText("Confirmed: {:,} atoms · available: {:,} atoms".format(
                result["confirmed_atoms"],result["available_atoms"]))
            self.tip.setText("Owned REGTEST Core: height {} · tip {}".format(
                result["height"],result["tip"]))
            rows=result["history"]
            self.history.setPlainText(
                "\n".join("{}  height={}  atoms={}".format(
                    row["txid"],row["height"],row["atoms"]) for row in rows)
                if rows else "No confirmed BIP352 transactions found on this disposable Core")
            self.status.setText("Verified real WAM Core + WSP scan · Send/Sign disabled")
        elif action=="lock":
            self._ready=False
            self.receive.clear()
            self.account.setText("Account: locked")
            self.balance.setText("Balance: unverified")
            self.tip.setText("Chain: unverified")
            self.history.clear()
            self.status.setText("Q06 seed locked. Stop Core and quit to leave this trial.")
        elif action=="quit":
            self._ready=False
            self._closed=True
        self._set_actions()

    def _on_denied(self, code):
        self.status.setText("Operation refused safely: " + str(code))
        self._set_actions()

    def _finished(self):
        self._worker=None
        self._set_actions()
        self._check_quit()

    def _check_quit(self):
        if self.executor.closed and self.executor.join(0):
            self._poll.stop()
            self._closed=True
            qt_application().quit()
        elif self._quit_requested and self._worker is None and not self.executor.busy:
            self._command("quit")

    def request_quit(self):
        self._quit_requested=True
        self.status.setText("Stopping only this original owned REGTEST Core…")
        self._check_quit()

    def closeEvent(self,event):
        if self.executor.closed:
            event.accept()
        else:
            event.ignore()
            self.request_quit()


def launch_bip39_trial(root,core,source,*,mode,authorized=False):
    if authorized is not True or mode not in ("create","restore","reopen"):
        raise ValueError("Q06_GUI_EXPLICIT_REGTEST_CONSENT_REQUIRED")
    app=qt_application()
    app.setQuitOnLastWindowClosed(False)
    executor=WalletExecutor(lambda:Bip39ReadOnlyBackend(root,core,source))
    window=Bip39TrialWindow(executor)
    window.show()
    password, ok=QInputDialog.getText(
        window, "Q06 BIP39 wallet (REGTEST only)",
        "Disposable encrypted-seed password (12–1024 UTF-8 bytes)",
        QLineEdit.EchoMode.Password,
    )
    if ok and not 12 <= len(password.encode("utf-8")) <= 1024:
        QMessageBox.warning(window,"Q06 password","Use a disposable password of 12–1024 bytes.")
        ok=False
    phrase=""
    if ok and mode=="restore":
        phrase,ok=QInputDialog.getMultiLineText(
            window,"Restore BIP39 12 words into a NEW REGTEST profile",
            "Enter exactly your 12 disposable REGTEST words. "
            "Restoring on a new isolated chain does not recreate old transactions.")
    if ok:
        window.start(password.encode("utf-8"),mode,phrase)
    else:
        window.request_quit()
    password=phrase=""
    result=app.exec() if not executor.closed else 0
    if not executor.closed:
        raise ValueError("Q06_GUI_ORIGINAL_OWNER_STILL_ACTIVE")
    executor.join()
    return result
