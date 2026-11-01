"""Native Qt Q06 12-word REGTEST owner trial, separate from Q05 GUI.

Full REGTEST Send remains disabled until owned-Core/native-checkpoint activation.
No keys leave this local GUI or enter native CI artifacts.
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
        box.addWidget(QLabel("REGTEST wallet. Send is available only after native checkpoint"
                              " verification and explicit transaction review. No mainnet funds."))
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
        self.sync=QPushButton("Sync real Core")
        self.fund=QPushButton("Fund 1 test receive on fresh REGTEST")
        self.activate=QPushButton("Activate verified REGTEST Send")
        self.send=QPushButton("Prepare Send")
        self.broadcast=QPushButton("Broadcast signed transaction")
        self.confirm=QPushButton("Confirm 1 REGTEST block")
        self.recovery=QPushButton("Verify 12-word recovery on this chain")
        self.inspect=QPushButton("Inspect past TXID (read-only)")
        self.cancel=QPushButton("Cancel unsigned draft")
        self.lock=QPushButton("Lock Q06")
        self.quit=QPushButton("Stop owned Core and quit")
        bar.addWidget(self.sync);bar.addWidget(self.fund);bar.addWidget(self.activate)
        box.addLayout(bar)
        payment=QHBoxLayout()
        payment.addWidget(self.send);payment.addWidget(self.broadcast);payment.addWidget(self.cancel)
        box.addLayout(payment)
        box.addWidget(self.confirm)
        box.addWidget(self.recovery)
        box.addWidget(self.inspect)
        utility=QHBoxLayout()
        utility.addWidget(self.lock);utility.addWidget(self.quit)
        box.addLayout(utility)
        self.sync.clicked.connect(lambda:self._command("snapshot"))
        self.fund.clicked.connect(self._confirm_funding)
        self.activate.clicked.connect(self._confirm_activation)
        self.send.clicked.connect(self._prepare_send)
        self.broadcast.clicked.connect(self._confirm_broadcast)
        self.confirm.clicked.connect(self._confirm_one_block)
        self.recovery.clicked.connect(self._verify_recovery_phrase)
        self.inspect.clicked.connect(self._inspect_past_txid)
        self.cancel.clicked.connect(lambda:self._command("cancel"))
        self.lock.clicked.connect(lambda:self._command("lock"))
        self.quit.clicked.connect(self.request_quit)
        self._poll=QTimer(self);self._poll.timeout.connect(self._check_quit)
        self._poll.setInterval(100);self._poll.start()
        self._ready=False
        self._test_funded=False
        self._spend_enabled=False
        self._signed_ready=False
        self._approved_commitment=None
        self._pending_confirm_txid=None
        self._pending_action=None
        self._set_actions()

    def _set_actions(self):
        busy=self._worker is not None or self.executor.busy
        safe=not self.executor.state.faulted
        self.sync.setEnabled(self._ready and safe and not busy and not self._quit_requested)
        self.fund.setEnabled(self._ready and safe and not self._test_funded and not self._spend_enabled
                             and not busy and not self._quit_requested)
        self.activate.setEnabled(self._ready and safe and not self._spend_enabled and not busy and not self._quit_requested)
        self.send.setEnabled(safe and self._spend_enabled and self._approved_commitment is None
                             and not busy and not self._quit_requested)
        self.broadcast.setEnabled(safe and self._spend_enabled and self._signed_ready
                                  and not busy and not self._quit_requested)
        self.cancel.setEnabled(safe and self._spend_enabled and self._approved_commitment is not None
                               and not self._signed_ready and not busy and not self._quit_requested)
        self.confirm.setEnabled(safe and self._spend_enabled and self._pending_confirm_txid is not None
                                and not busy and not self._quit_requested)
        self.recovery.setEnabled(safe and self._spend_enabled and self._pending_confirm_txid is None
                                 and not busy and not self._quit_requested)
        self.inspect.setEnabled(safe and self._spend_enabled
                                and not busy and not self._quit_requested)
        self.lock.setEnabled(self._ready and not busy and not self._quit_requested)
        self.quit.setEnabled(not busy and not self.executor.closed)

    def _command(self, action, *args):
        if self._worker is not None or self.executor.busy or self.executor.closed:
            return False
        worker=ControlWorker(self.executor, action, args,
                             kwargs={"timeout":240} if action in ("mine","snapshot","activate","prepare","sign","broadcast","confirm","recovery_verify","inspect_confirmed") else None,
                             parent=self)
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

    def _confirm_funding(self):
        if not self._ready or self._worker is not None or self.executor.busy:
            return
        answer=QMessageBox.question(
            self, "One-time disposable WAM REGTEST receive",
            "This runs the existing Q05 PUBLIC fixture on your NEW isolated "
            "WAM REGTEST Core: generate 101 local blocks, send a public test "
            "BIP352 payment to YOUR Q06 12-word address, then confirm it.\\n"
            "This is irreversible on the test chain. Never use mainnet or "
            "personal keys. Run only once on a fresh height-0 Core?",
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer==QMessageBox.StandardButton.Yes:
            self.status.setText("Funding test-only receive on owned Core; do not retry if uncertain…")
            self._command("mine")

    def _confirm_activation(self):
        if not self._ready or self._spend_enabled:
            return
        choice=QMessageBox.question(
            self,"Native BIP39 REGTEST signing",
            "Activate the existing Q05 transaction engine on the authenticated "
            "BIP39 scanner journal of this original WAM REGTEST Core? "
            "Uncertain reservations will stay locked. "
            "Never use real/mainnet seed words.",
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if choice==QMessageBox.StandardButton.Yes:
            self._command("activate")

    def _prepare_send(self):
        if not self._spend_enabled or self._approved_commitment is not None:
            return
        code,ok=QInputDialog.getText(
            self,"Prepare WAM REGTEST Send","Recipient BIP352 REGTEST receive code:")
        if not ok:
            return
        amount,ok=QInputDialog.getText(
            self,"Prepare WAM REGTEST Send",
            "Amount in integer atoms (1 WAM = 100,000,000 atoms):")
        if not ok:
            return
        fee,ok=QInputDialog.getText(
            self,"Prepare WAM REGTEST Send",
            "Transaction fee in integer atoms (1–1,000,000):")
        if not ok:
            return
        if (not code.startswith("wamrtsp1") or len(amount)>19 or len(fee)>7
                or not amount.isascii() or not amount.isdecimal()
                or not fee.isascii() or not fee.isdecimal()):
            QMessageBox.warning(self,"Invalid Send input","Use a REGTEST address and integer atom amounts.")
            return
        atoms_value,fee_value=int(amount),int(fee)
        if not (330<=atoms_value<=22_000_000*100_000_000
                and 1<=fee_value<=1_000_000):
            QMessageBox.warning(self,"Invalid Send input","Amount or fee outside WSP policy.")
            return
        self._command("prepare",code,atoms_value,fee_value)

    def _confirm_broadcast(self):
        if not self._signed_ready or self._approved_commitment is None:
            return
        choice=QMessageBox.question(
            self,"Broadcast signed REGTEST transaction",
            "The previously reviewed PSBT is signed. Broadcast it to the "
            "original owned WAM REGTEST Core now? Ambiguous results must "
            "keep their reservation locked.",
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if choice==QMessageBox.StandardButton.Yes:
            self._command("broadcast",self._approved_commitment)

    def _confirm_one_block(self):
        txid = self._pending_confirm_txid
        if not self._spend_enabled or txid is None:
            return
        choice=QMessageBox.question(
            self,"Confirm one REGTEST block",
            "Mine exactly ONE block on this original, owned, disposable REGTEST "
            "Core to confirm the just-broadcast transaction?\\n"
            "TXID: {}\\n"
            "This changes the test chain. Never use mainnet funds or seed words. "
            "If the result is uncertain, do NOT retry.".format(txid),
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if choice==QMessageBox.StandardButton.Yes:
            self._command("confirm",txid)

    def _verify_recovery_phrase(self):
        if not self._spend_enabled or self._worker is not None or self.executor.busy:
            return
        phrase,ok=QInputDialog.getMultiLineText(
            self,"Independent BIP39 history recovery (REGTEST)",
            "Enter your 12 DISPOSABLE REGTEST words to independently rescan "
            "THIS original Core blockchain. Read-only: no native reservation "
            "migration, no clean-device recovery, no signing authority.")
        if ok:
            self.status.setText("Independently rescanning original REGTEST chain…")
            self._command("recovery_verify",phrase)
        phrase=""

    def _inspect_past_txid(self):
        if not self._spend_enabled or self.executor.state.faulted:
            return
        txid,ok=QInputDialog.getText(
            self,"Read-only previous transaction inspection",
            "Enter a previously broadcast REGTEST transaction ID (64 lowercase hex). "
            "This checks complete authenticated local history: no retry, mining, "
            "broadcast, reservation release or claim if not yet found.")
        if ok:
            self._command("inspect_confirmed",txid)

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
            self.status.setText("BIP39 native seed opened. Activate Send after checkpoint verification.")
            if result.get("mnemonic_once"):self._show_words_once(result["mnemonic_once"])
        elif action=="mine":
            self._test_funded=True
            self.status.setText("Public REGTEST receive confirmed at block {} — click Sync real Core".format(result["height"]))
        elif action in ("snapshot","activate"):
            if result.get("signer_allowed") is True:
                self._spend_enabled=True
            self.receive.setText(result["receive_code"])
            self.balance.setText("Confirmed: {:,} atoms · available: {:,} atoms".format(
                result["confirmed_atoms"],result["available_atoms"]))
            self.tip.setText("Owned REGTEST Core: height {} · tip {}".format(
                result["height"],result["tip"]))
            self._test_funded = result["height"] > 0
            rows=result["history"]
            self.history.setPlainText(
                "\n".join("{}  height={}  atoms={}".format(
                    row["txid"],row["height"],row["atoms"]) for row in rows)
                if rows else "No confirmed BIP352 transactions found on this disposable Core")
            if (self._spend_enabled and result.get("reservation_count",0)>0
                    and self._pending_confirm_txid is None):
                self.status.setText(
                    "Anchored transaction reservations exist; check previous TXID "
                    "against verified history. Never auto-rebroadcast or release locks.")
            else:
                self.status.setText(
                    "Verified BIP39 REGTEST Send session; review every transaction"
                    if self._spend_enabled else
                    "Verified WAM Core and WSP scan; Send remains disabled")
        elif action=="prepare":
            self._approved_commitment=result.commitment
            self._signed_ready=False
            choice=QMessageBox.question(
                self,"Exact REGTEST transaction approval",
                "Recipient: {}\nAmount: {:,} atoms\nFee: {:,} atoms\n"
                "Change: {:,} atoms\nInputs: {}\nPSBT SHA256: {}\n\n"
                "SIGN and irreversibly reserve these coins?".format(
                    result.code,result.atoms,result.fee,result.change_atoms,
                    result.input_count,result.commitment),
                QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            self._pending_action=(
                ("sign",result.commitment)
                if choice==QMessageBox.StandardButton.Yes else ("cancel",))
            self.status.setText("Exact-transaction approval received; securing reservation")
        elif action=="sign":
            if result.commitment!=self._approved_commitment:
                self._signed_ready=False
                self.status.setText("Signed commitment mismatch — broadcast disabled")
            else:
                self._signed_ready=True
                self.status.setText("PSBT signed; broadcast requires separate explicit approval")
        elif action=="broadcast":
            self._approved_commitment=None
            self._signed_ready=False
            self._pending_confirm_txid=result
            self.status.setText(
                "Broadcast submitted. Record the TXID before closing: {}. "
                "Confirm 1 REGTEST block to verify on-chain.".format(result))
            self._pending_action=("snapshot",)
        elif action=="confirm":
            if result.get("txid")!=self._pending_confirm_txid:
                self.status.setText("Confirmation identity mismatch — stop for review")
            else:
                self._pending_confirm_txid=None
                self.status.setText("REGTEST transaction confirmed on original Core")
                self._pending_action=("snapshot",)
        elif action=="recovery_verify":
            self.status.setText(
                "Same-chain BIP39 rescan PASS: {} confirmed history records, "
                "{:,} atoms. Separate device/chain restoration remains unverified.".format(
                    result["history_count"],result["confirmed_atoms"]))
        elif action=="inspect_confirmed":
            self.status.setText(
                "TXID is in complete verified confirmed history."
                if result["status"]=="Q06_CONFIRMED_IN_VERIFIED_HISTORY" else
                "TXID NOT in complete verified confirmed history; status uncertain. "
                "Do NOT retry, remine or release coin reservations.")
        elif action=="cancel":
            self._approved_commitment=None
            self._signed_ready=False
            self.status.setText("Unsigned draft cancelled")
        elif action=="lock":
            self._ready=False
            self._spend_enabled=False
            self._signed_ready=False
            self._approved_commitment=None
            self._pending_confirm_txid=None
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
        if self._approved_commitment is not None:
            self._signed_ready=False
        self.status.setText(
            "Wallet faulted — stop spending; original state preserved for review."
            if self.executor.state.faulted else
            "Operation refused safely: " + str(code))
        self._set_actions()

    def _finished(self):
        self._worker=None
        pending,self._pending_action=self._pending_action,None
        if pending is not None and not self._quit_requested:
            self._command(*pending)
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
