"""Native disposable test-wallet Send/Sign/Broadcast and Security/Settings UI."""
from decimal import Decimal, InvalidOperation
from pathlib import Path
import secrets
import re
from PySide6.QtCore import QThread, Signal, QTimer, Qt
from PySide6.QtWidgets import (
    QApplication,QFrame,QVBoxLayout,QLabel,QLineEdit,QPushButton,QHBoxLayout,
    QFileDialog,QMessageBox,QInputDialog,QComboBox,
)
from wam_regtest.desktop import RegtestWalletWindow, qt_application
from wam_regtest.wallet_session import WalletSession, PaymentReview


def _parse_atoms(value,minimum,maximum):
    if (type(value) is not str or not re.fullmatch(r"(?:0|[1-9][0-9]{0,7})(?:\.[0-9]{1,8})?",value)):
        raise ValueError("WALLET_AMOUNT_DENIED")
    amount=Decimal(value)*100_000_000
    if not minimum<=amount<=maximum:
        raise ValueError("WALLET_AMOUNT_DENIED")
    return int(amount)


def parse_amount(value):
    return _parse_atoms(value,330,22_000_000*100_000_000)


class OperationWorker(QThread):
    ready=Signal(str,object)
    denied=Signal(str)
    def __init__(self, session, action, args):
        super().__init__()
        self.session,self.action,self.args=session,action,args
    def run(self):
        try:
            methods={"prepare":self.session.prepare,"sign":self.session.sign,
                     "broadcast":self.session.broadcast,"cancel":self.session.cancel,
                     "lock":self.session.lock,"unlock":self.session.unlock,
                     "backup":self.session.backup,"recover":self.session.recover_backup,
                     "mine":self.session.mine}
            result=methods[self.action](*self.args)
            self.ready.emit(self.action,result)
        except Exception:
            self.denied.emit("WALLET_OPERATION_DENIED_STATE_RETAINED")
        finally:
            self.args=()  # Release temporary GUI passphrase copies, best effort.


class OperationalWalletWindow(RegtestWalletWindow):
    operation_completed=Signal(str,object)
    operation_failed=Signal(str)
    def __init__(self,session):
        self.session=session
        self.review=None
        self.signed=False
        super().__init__(session.core_dir,session.datadir,session.source,session=session)
        self.setWindowTitle("WAM Privacy Wallet · Disposable REGTEST")
        self.warning.setText("REGTEST ONLY · DISPOSABLE TEST KEYS · NO REAL FUNDS")
        self.navigation.addItems(["Send","Security","Settings"])
        send=QFrame()
        send.setObjectName("ContentCard")
        layout=QVBoxLayout(send)
        layout.setContentsMargins(24,24,24,24)
        layout.addWidget(QLabel("Send · BIP352 silent payment"))
        self.recipient=QLineEdit()
        self.recipient.setMaxLength(256)
        self.recipient.setPlaceholderText("wamrtsp1… disposable REGTEST recipient")
        self.amount=QLineEdit()
        self.amount.setMaxLength(32)
        self.amount.setPlaceholderText("Amount in WAM")
        self.fee=QLineEdit("0.00010000")
        self.fee.setMaxLength(32)
        for label,widget in (("Recipient",self.recipient),("Amount (WAM)",self.amount),("Fee (WAM; max 0.01)",self.fee)):
            layout.addWidget(QLabel(label))
            layout.addWidget(widget)
        self.review_text=QLabel("Prepare a payment, verify the exact recipient/amount/fee, then approve signing and broadcast separately.")
        self.review_text.setWordWrap(True)
        self.review_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.review_text)
        row=QHBoxLayout()
        self.prepare_button=QPushButton("Prepare")
        self.sign_button=QPushButton("Approve & Sign")
        self.broadcast_button=QPushButton("Broadcast")
        self.cancel_button=QPushButton("Cancel unsigned draft")
        for button in (self.prepare_button,self.sign_button,self.broadcast_button,self.cancel_button):
            row.addWidget(button)
        layout.addLayout(row)
        layout.addStretch()
        self.stack.addWidget(send)
        self.prepare_button.clicked.connect(self.prepare_payment)
        self.sign_button.clicked.connect(lambda:self.start_operation("sign",self.review.commitment) if self.review else None)
        self.broadcast_button.clicked.connect(lambda:self.start_operation("broadcast",self.review.commitment) if self.review else None)
        self.cancel_button.clicked.connect(lambda:self.start_operation("cancel"))

        security=QFrame()
        security.setObjectName("ContentCard")
        layout=QVBoxLayout(security)
        layout.setContentsMargins(24,24,24,24)
        text=QLabel("Encrypted wallet keys and authenticated checkpoints · AES-GCM / scrypt\n"
                    "Independent macOS Keychain generation/digest anchor\n\n"
                    "Keep the latest backup after each payment. Older anchored generations are rejected.\n"
                    "Recovery always verifies and scans the live REGTEST chain.\n"
                    "Unlocked SQLite is a private disposable runtime; memory clearing is best effort.")
        text.setWordWrap(True)
        layout.addWidget(text)
        self.lock_button=QPushButton("Lock wallet")
        self.unlock_button=QPushButton("Unlock with passphrase")
        self.backup_button=QPushButton("Save latest encrypted backup…")
        self.recover_button=QPushButton("Recover latest anchored backup…")
        for button in (self.lock_button,self.unlock_button,self.backup_button,self.recover_button):
            layout.addWidget(button)
        layout.addStretch()
        self.stack.addWidget(security)
        self.lock_button.clicked.connect(lambda:self.start_operation("lock"))
        self.unlock_button.clicked.connect(self.unlock_wallet)
        self.backup_button.clicked.connect(self.backup_wallet)
        self.recover_button.clicked.connect(self.recover_wallet)

        settings=QFrame()
        settings.setObjectName("ContentCard")
        layout=QVBoxLayout(settings)
        layout.setContentsMargins(24,24,24,24)
        layout.addWidget(QLabel("Settings · isolated REGTEST node"))
        layout.addWidget(QLabel("Official WAM Core v0.1.11 · zero peers · localhost only\n"
                               "Background sync every 30 seconds; appearance follows macOS in Auto mode.\n"
                               "The test chain is deleted when this developer session closes."))
        self.mine_button=QPushButton("Mine 1 REGTEST block to confirm pending transactions")
        self.mine_button.clicked.connect(lambda:self.start_operation("mine"))
        layout.addWidget(self.mine_button)
        layout.addStretch()
        self.stack.addWidget(settings)
        self.appearance.setItemText(0,"Auto · macOS")
        hints=QApplication.styleHints()
        hints.colorSchemeChanged.connect(self.apply_theme)
        self._appearance_connected=True
        self._actions=(self.prepare_button,self.sign_button,self.broadcast_button,self.cancel_button,
                       self.lock_button,self.unlock_button,self.backup_button,self.recover_button,self.mine_button)
        self._update_controls()

    def _update_controls(self):
        if not hasattr(self,"_actions"):
            return
        busy=self._worker is not None
        unlocked=not self.session.locked and not self.session.faulted
        for button in self._actions:
            button.setEnabled(not busy and unlocked)
        self.prepare_button.setEnabled(not busy and unlocked and self.review is None)
        self.sign_button.setEnabled(not busy and unlocked and self.review is not None and not self.signed)
        self.broadcast_button.setEnabled(not busy and unlocked and self.review is not None and self.signed)
        self.cancel_button.setEnabled(not busy and unlocked and self.review is not None and not self.signed)
        self.unlock_button.setEnabled(not busy and self.session.locked)
        self.recover_button.setEnabled(not busy and self.session.locked)
        self.lock_button.setEnabled(not busy and not self.session.locked)
        editable=not busy and unlocked and self.review is None
        for field in (self.recipient,self.amount,self.fee):
            field.setEnabled(editable)

    def start_operation(self,action,*args):
        if self._worker is not None:
            return
        worker=OperationWorker(self.session,action,args)
        self._worker=worker
        self.refresh_button.setEnabled(False)
        self.status.setText("Working on verified disposable REGTEST wallet…")
        worker.ready.connect(self._operation_ready)
        worker.denied.connect(self._operation_denied)
        worker.finished.connect(self._worker_finished)
        worker.finished.connect(worker.deleteLater)
        self._update_controls()
        worker.start()

    def _worker_finished(self):
        super()._worker_finished()
        self._update_controls()

    def prepare_payment(self):
        try:
            atoms=parse_amount(self.amount.text())
            # Fee has a lower dust-independent floor and explicit WSP limit.
            fee=_parse_atoms(self.fee.text(),1,1_000_000)
            self.start_operation("prepare",self.recipient.text().strip(),atoms,fee)
        except (ValueError,InvalidOperation,OverflowError):
            self._operation_denied("WALLET_AMOUNT_OR_FEE_DENIED")

    def _operation_ready(self,action,result):
        if action in ("prepare","sign"):
            self.review=result
            self.signed=action=="sign"
            self.review_text.setText(
                f"{'SIGNED — ready to broadcast' if self.signed else 'REVIEW BEFORE SIGNING'}\n"
                f"Recipient: {result.code}\nAmount: {result.atoms} atoms\n"
                f"Fee: {result.fee} atoms\nChange back to this wallet: {result.change_atoms} atoms\n"
                f"Inputs: {result.input_count}")
        elif action in ("cancel","broadcast","lock"):
            self.review=None
            self.signed=False
            self.review_text.setText("Broadcast txid: "+result if action=="broadcast" else "No active payment review")
        if action=="lock":
            self._clear_balance()
            self.status.setText("LOCKED · encrypted snapshot anchored in macOS Keychain")
        else:
            self.status.setText("REGTEST wallet operation completed; sync to refresh confirmed history")
            if action in ("unlock","recover","mine"):
                self.apply_snapshot(result)
        self._update_controls()
        self.operation_completed.emit(action,result)

    def _operation_denied(self,reason):
        self._clear_balance()
        self.status.setText("DENIED · wallet state/reservations retained; unlock/recover or verify chain")
        self.operation_failed.emit("WALLET_OPERATION_DENIED_STATE_RETAINED")
        self._update_controls()

    def request_sync(self):
        if self.session.locked or self.session.faulted:
            return
        super().request_sync()
        self._update_controls()

    def _passphrase(self,label):
        password,ok=QInputDialog.getText(self,"Disposable REGTEST wallet",label,QLineEdit.EchoMode.Password)
        return password.encode() if ok else None

    def unlock_wallet(self):
        password=self._passphrase("Wallet passphrase (12+ characters)")
        if password is not None:
            self.start_operation("unlock",password)

    def backup_wallet(self):
        parent=QFileDialog.getExistingDirectory(self,"Select parent for a new private encrypted backup folder")
        if parent:
            directory=Path(parent).resolve()/("wam-regtest-backup-"+secrets.token_hex(6))
            try:
                directory.mkdir(mode=0o700)
                self.start_operation("backup",directory,"wallet-backup.enc")
            except OSError:
                self._operation_denied("WALLET_BACKUP_DIRECTORY_DENIED")

    def recover_wallet(self):
        name,_=QFileDialog.getOpenFileName(self,"Latest anchored REGTEST backup",filter="Encrypted backups (*.enc)")
        if name:
            password=self._passphrase("Backup passphrase")
            if password is not None:
                path=Path(name).absolute()
                self.start_operation("recover",path.parent,path.name,password)

    def closeEvent(self,event):
        if self._worker is not None:
            super().closeEvent(event)
            return
        try:
            self.session.close()
        except Exception:
            event.ignore()
            self.status.setText("DENIED · waiting for safe wallet shutdown")
            return
        if self._appearance_connected:
            QApplication.styleHints().colorSchemeChanged.disconnect(self.apply_theme)
            self._appearance_connected=False
        super().closeEvent(event)


def launch_disposable_wallet(core_dir,datadir,source,mining_address):
    app=qt_application()
    choice,ok=QInputDialog.getItem(None,"Disposable REGTEST wallet",
        "Fresh test chain · no personal keys or real funds",
        ["Create fresh test keys","Recover latest backup on this Mac"],0,False)
    if not ok:
        return 0
    backup=None
    if choice=="Recover latest backup on this Mac":
        name,_=QFileDialog.getOpenFileName(None,"Latest anchored REGTEST backup",filter="Encrypted backups (*.enc)")
        if not name:
            return 0
        backup=Path(name).absolute()
    while True:
        password,ok=QInputDialog.getText(None,"Disposable REGTEST wallet",
            "Wallet backup passphrase (12+ characters).\n"
            "Recovery rescans a fresh test chain and creates a new test receive epoch.",QLineEdit.EchoMode.Password)
        if not ok:
            return 0
        encoded=password.encode()
        if len(password)>=12 and len(encoded)<=1024:
            break
        QMessageBox.warning(None,"Passphrase length","Use a longer passphrase (at least 12 characters).")
    if backup is None:
        session=WalletSession.create(core_dir,datadir,source,encoded,mining_address,authorized=True)
    else:
        session=WalletSession.from_backup(core_dir,datadir,source,backup.parent,backup.name,
                                           encoded,mining_address,authorized=True)
    window=OperationalWalletWindow(session)
    window.show()
    QTimer.singleShot(0,window.request_sync)
    return app.exec()
