"""Native Qt Q06 12-word REGTEST owner trial, separate from Q05 GUI.

Full REGTEST Send remains disabled until owned-Core/native-checkpoint activation.
No keys leave this local GUI or enter native CI artifacts.
"""
from pathlib import Path

from PySide6.QtCore import Qt,QTimer,QEvent,Signal
from PySide6.QtWidgets import (
    QCheckBox,QDialog,QDialogButtonBox,QHBoxLayout,QGridLayout,QInputDialog,QLabel,
    QLineEdit,QMessageBox,QPushButton,QTextEdit,QVBoxLayout,QWidget,QApplication,
)

from .desktop import qt_application
from .gui_errors import operation_error, public_code, error_text
from .managed_gui import ControlWorker
from .wallet_executor import WalletExecutor
from .bip39_owner_backend import Bip39ReadOnlyBackend
from .bip39_12 import normalize_phrase
from .bip39_locale import t
from .fusion_ui import label, action


class Bip39RecoveryVerifyDialog(QDialog):
    """Owner-approved Q06 independent 12-word recovery verification modal.

    Scope A of the owner-approved Recovery & Backup Verification UX. Real Qt
    inputs only: sequential focus navigation, user-initiated paste, explicit
    clear, clean inline validation errors and a backend-authority BIP39
    checksum gate. No generic Qt message boxes for ordinary validation
    failures, no automatic clipboard reads/writes and no seed echo.
    """

    WORD_COUNT = 12

    verify_requested = Signal(str)
    cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("FusionPanel")
        self.setWindowTitle(t("recovery_verify_title"))
        self._fields = []
        self._count_label = None
        self._verify_button = None
        self._verify_error = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)
        layout.addWidget(label(t("recovery_verify_kicker"), "FusionKicker"))
        layout.addWidget(label(t("recovery_verify_title"), "PageTitle"))
        layout.addWidget(label(t("recovery_verify_subtitle")))
        layout.addWidget(label(t("recovery_readonly_notice"), "FusionMuted"))
        grid = QGridLayout()
        grid.setSpacing(12)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        self._grid = grid
        for index in range(self.WORD_COUNT):
            field_box = QWidget()
            field_box.setObjectName("FusionInset")
            field_layout = QVBoxLayout(field_box)
            field_layout.setContentsMargins(12, 10, 12, 10)
            field_layout.setSpacing(6)
            position_label = QLabel(f"WORD {index + 1:02d}")
            position_label.setObjectName("FusionMuted")
            position_label.setStyleSheet("font-size:11px;font-weight:600;letter-spacing:0.4px;")
            field = QLineEdit()
            field.setObjectName("RecoveryWordField")
            field.setMaxLength(16)
            field.setPlaceholderText(t("word_label"))
            field.setEchoMode(QLineEdit.EchoMode.Password)
            field.setAccessibleName(f"Recovery word {index + 1}")
            field.textChanged.connect(self._refresh_state)
            field.returnPressed.connect(lambda i=index: self._on_field_returned(i))
            field_layout.addWidget(position_label)
            field_layout.addWidget(field)
            grid.addWidget(field_box, index // 3, index % 3)
            self._fields.append(field)
            field.installEventFilter(self)
        layout.addLayout(grid)
        self._verify_error = label("", "FusionGold")
        self._verify_error.hide()
        layout.addWidget(self._verify_error)
        self._count_label = label(t("recovery_word_count").format(entered=0), "FusionMuted")
        self._paste_button = QPushButton(t("recovery_paste_words"))
        self._paste_button.setObjectName("FusionSecondary")
        self._paste_button.clicked.connect(self._on_paste)
        self._clear_button = QPushButton(t("recovery_clear_words"))
        self._clear_button.setObjectName("FusionDestructive")
        self._clear_button.clicked.connect(self._on_clear)
        self._cancel_button = action(t("recovery_cancel"), "backup")
        self._cancel_button.setObjectName("FusionSecondary")
        self._cancel_button.clicked.connect(self._on_cancel)
        self._verify_button = action(t("recovery_verify_phrase"), "check", primary=True)
        self._verify_button.setObjectName("FusionPrimary")
        self._verify_button.setEnabled(False)
        self._verify_button.clicked.connect(self._on_verify_phrase)
        footer = QHBoxLayout()
        footer.addWidget(self._paste_button)
        footer.addWidget(self._clear_button)
        footer.addStretch()
        footer.addWidget(self._count_label)
        footer.addStretch()
        footer.addWidget(self._cancel_button)
        footer.addWidget(self._verify_button)
        layout.addLayout(footer)
        layout.addStretch()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            index = -1
            for i, field in enumerate(self._fields):
                if field is obj:
                    index = i
                    break
            if index >= 0:
                handled = False
                if key == Qt.Key_Backspace and not obj.text():
                    if index > 0:
                        self._fields[index - 1].setFocus()
                        handled = True
                elif key in (Qt.Key_Tab, Qt.Key_Backtab):
                    next_index = index + 1 if key == Qt.Key_Tab else index - 1
                    if 0 <= next_index < len(self._fields):
                        self._fields[next_index].setFocus()
                        handled = True
                if handled:
                    event.accept()
                    return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._on_cancel()
            return
        super().keyPressEvent(event)

    def _on_field_returned(self, index):
        if index < len(self._fields) - 1:
            self._fields[index + 1].setFocus()
        else:
            self._on_verify_phrase()

    def _current_phrase(self):
        return " ".join(
            field.text().strip().lower()
            for field in self._fields if field.text().strip())

    def _refresh_state(self):
        words = [field.text().strip().lower() for field in self._fields]
        valid = False
        if len(words) == self.WORD_COUNT and all(words):
            try:
                normalize_phrase(" ".join(words))
                valid = True
            except Exception:
                valid = False
        self._verify_button.setEnabled(valid)
        self._count_label.setText(t("recovery_word_count").format(
            entered=sum(1 for field in self._fields if field.text().strip())))

    def _clear_fields(self):
        for field in self._fields:
            field.clear()
        self._refresh_state()

    def _on_verify_phrase(self):
        phrase = self._current_phrase()
        words = phrase.split()
        valid = False
        if len(words) == self.WORD_COUNT and all(words):
            try:
                normalize_phrase(phrase)
                valid = True
            except Exception:
                valid = False
        if not valid:
            self._verify_error.setText(t("recovery_invalid"))
            self._verify_error.show()
            return
        self.verify_requested.emit(phrase)
        self._clear_fields()
        self.accept()

    def _on_paste(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        self._apply_paste(text)
        if text:
            # The phrase is consumed by this explicit Paste; never leave a BIP39
            # seed readable in the system pasteboard for other processes.
            clipboard.clear()

    def _apply_paste(self, text):
        tokens = str(text or "").strip().lower().split()
        targets = [field for field in self._fields if not field.text().strip()]
        for token, field in zip(tokens, targets):
            field.setText(token)
        self._refresh_state()

    def _on_clear(self):
        for field in self._fields:
            field.clear()
        self._refresh_state()

    def _on_cancel(self):
        self._clear_fields()
        self.cancelled.emit()
        self.accept()

    def reject(self):
        self._clear_fields()
        self.cancelled.emit()
        super().reject()

    def closeEvent(self, event):
        self._clear_fields()
        super().closeEvent(event)


class Bip39TrialWindow(QWidget):
    def __init__(self, executor):
        super().__init__()
        self.executor = executor
        self._worker = None
        self._quit_requested = False
        self._closed = False
        self._backup_unacked = False
        self._backup_flow_active = False
        self._backup_result = None
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
        box.addWidget(QLabel("Last broadcast TXID (copy before closing):"))
        self.last_txid=QLineEdit()
        self.last_txid.setReadOnly(True)
        self.last_txid.setPlaceholderText(
            "No transaction broadcast in this GUI session. "
            "Copy the TXID before closing; it is not auto-replayed.")
        box.addWidget(self.last_txid)
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
        self.unlock=QPushButton("Unlock wallet")
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
        utility.addWidget(self.lock);utility.addWidget(self.unlock);utility.addWidget(self.quit)
        box.addLayout(utility)
        self.unlock.clicked.connect(self._unlock_prompt)
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
        self._unlock_allowed=False
        self._test_funded=False
        self._spend_enabled=False
        self._signed_ready=False
        self._approved_commitment=None
        self._pending_confirm_txid=None
        self._pending_action=None
        self._completed_result=None
        self._delivering_result=False
        self._last_error_code=None
        self._recovery_dialog=None
        self._recovered_unsigned_cancel=False
        self.cancel.setToolTip("Cancel requires an authenticated unsigned draft. Signed or uncertain reservations cannot be released.")
        self._set_actions()

    def _set_actions(self):
        busy=self._worker is not None or self.executor.busy or self._delivering_result
        safe=not self.executor.state.faulted
        spend_safe=(safe and not self.executor.state.locked
                    and not self.executor.state.reauthentication_required
                    and self.executor.state.core_alive is True)
        self.sync.setEnabled(self._ready and safe and not busy and not self._quit_requested)
        self.fund.setEnabled(self._ready and safe and not self._test_funded and not self._spend_enabled
                             and not busy and not self._quit_requested)
        self.activate.setEnabled(self._ready and safe and not self._spend_enabled and not busy and not self._quit_requested)
        self.send.setEnabled(spend_safe and self._spend_enabled and self._approved_commitment is None
                             and not self._recovered_unsigned_cancel and not busy and not self._quit_requested)
        self.broadcast.setEnabled(spend_safe and self._spend_enabled and self._signed_ready
                                  and not busy and not self._quit_requested)
        self.cancel.setEnabled(spend_safe and self._spend_enabled
                               and (self._approved_commitment is not None or self._recovered_unsigned_cancel)
                               and not self._signed_ready and not busy and not self._quit_requested)
        self.confirm.setEnabled(spend_safe and self._spend_enabled and self._pending_confirm_txid is not None
                                and not busy and not self._quit_requested)
        self.recovery.setEnabled(spend_safe and self._spend_enabled and self._pending_confirm_txid is None
                                 and not busy and not self._quit_requested)
        self.inspect.setEnabled(spend_safe and self._spend_enabled
                                and not busy and not self._quit_requested)
        self.lock.setEnabled(self._ready and not busy and not self._quit_requested)
        self.unlock.setEnabled(self._unlock_allowed and not self._ready and not busy
                                and not self._quit_requested)
        self.quit.setEnabled(not busy and not self.executor.closed)

    def _command(self, action, *args):
        if (self._worker is not None or self.executor.busy or self.executor.closed
                or self._delivering_result):
            return False
        worker=ControlWorker(self.executor, action, args,
                             kwargs={"timeout":240} if action in ("mine","snapshot","activate","prepare","sign","broadcast","confirm","recovery_verify","inspect_confirmed") else None,
                             parent=self)
        self._worker=worker
        self._completed_result = None
        self._last_error_code = None
        worker.ready.connect(self._receive_result, Qt.ConnectionType.QueuedConnection)
        worker.denied.connect(self._receive_denial, Qt.ConnectionType.QueuedConnection)
        worker.pending.connect(lambda _: self.status.setText(
            'Original operation still running. Waiting for its result; do not retry.'),
            Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(self._finished)
        worker.finished.connect(worker.deleteLater)
        self._set_actions()
        worker.start()
        return True

    def _passphrase(self, label):
        password, ok = QInputDialog.getText(
            self, "WAM Fusion · REGTEST wallet", label, QLineEdit.EchoMode.Password)
        return password.encode("utf-8") if ok and password else None

    def _unlock_prompt(self):
        # In-session reauthentication of the SAME original owned REGTEST
        # profile. The backend revalidates owner identity, native Keychain,
        # anchored checkpoint and backup acknowledgement on the live Core.
        # No retry, mining, rebroadcast, reservation release or Core adoption.
        if self._worker is not None or self.executor.busy or self._quit_requested:
            return
        password = self._passphrase(
            "Wallet password to unlock this original WAM REGTEST BIP39 profile")
        if password is None:
            return
        self.status.setText("Unlocking original owned WAM REGTEST wallet…")
        self._command("unlock", password, False)

    def _remember_profile(self, folder):
        # Remember ONLY the wallet profile PATH. Never password, mnemonic,
        # private keys or native anchor secrets cross this boundary.
        try:
            from PySide6.QtCore import QSettings
            if folder:
                QSettings("WAM Privacy Wallet", "REGTEST").setValue(
                    "last_shared_bip39_profile" if getattr(self,'shared_profile',None) else "last_bip39_profile", str(folder))
        except Exception:
            pass

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
        dialog = Bip39RecoveryVerifyDialog(self)
        dialog.verify_requested.connect(self._on_recovery_verify_requested)
        dialog.cancelled.connect(self._on_recovery_verify_cancelled)
        self._recovery_dialog = dialog
        dialog.exec()

    def _on_recovery_verify_requested(self, phrase):
        self._recovery_dialog = None
        self.status.setText("Independently rescanning original REGTEST chain…")
        self._command("recovery_verify", phrase)

    def _on_recovery_verify_cancelled(self):
        self._recovery_dialog = None

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

    def _on_ready(self, action, result):
        if action in ('open', 'lock', 'quit'):
            self._recovered_unsigned_cancel = False
        elif action in ('snapshot', 'activate', 'unlock') and isinstance(result, dict):
            self._recovered_unsigned_cancel = result.get('recovered_unsigned_cancel_available') is True
        if action=="open":
            self._backup_unacked=False
            # Start from a locked UI state; the backup flow (if required) will
            # promote to ready via _backup_flow_completed.
            self._ready=False
            self.receive.clear()
            self.account.setText("Account: locked")
            self.balance.setText("Balance: unverified")
            self.tip.setText("Chain: unverified")
            backup_status = result.get("backup_status", "verified")
            seed_folder = result.get("seed_folder")
            if backup_status in ("required", "deferred"):
                if backup_status == "required" and seed_folder:
                    try:
                        self.executor.request(
                            "acknowledge_create_pending", seed_folder, timeout=30)
                    except Exception as error:
                        self.status.setText(
                            "Backup acknowledgement state unavailable — "
                            "wallet preserved locked: " + operation_error(
                                "acknowledge_create_pending", error))
                        self._backup_unacked=True
                        self._set_actions()
                        return
                self._backup_result = result
                self._backup_flow_active = True
                self._present_backup_ack(result)
                return
            self._ready=True
            self.receive.setText(result["receive_code"])
            self.account.setText("BIP39 account: "+result["account_id"])
            self.balance.setText("Balance: not yet synced against Core")
            self.tip.setText("Chain: not yet verified")
            self.status.setText("BIP39 native seed opened. Activate Send after checkpoint verification.")
            self._pending_action = None if result.get('checkpoint_present') else ("snapshot",)
            if result.get('checkpoint_present'):
                self.status.setText('Original checkpoint retained. Enable sending to authenticate and reconcile it.')
            self._remember_profile(result.get("seed_folder"))
        elif action=="mine":
            self._test_funded=True
            self.status.setText("Public REGTEST receive confirmed at block {} — click Sync real Core".format(result["height"]))
        elif action in ("snapshot","activate"):
            if result.get("signer_allowed") is True:
                self._spend_enabled=True
            if 'payment_review' in result:
                review = result['payment_review']
                self._approved_commitment = review.commitment if review is not None else None
                self._signed_ready = result.get('payment_signed') is True
                pending = result.get('pending_confirm_txid')
                # A post-broadcast snapshot must not erase the GUI's exact TXID
                # when the session has not yet published pending_confirm_txid.
                # Confirm/lock still clear this field explicitly.
                if pending is not None:
                    self._pending_confirm_txid = pending
                if hasattr(self, '_last_review'):
                    self._last_review = review
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
            if self._recovered_unsigned_cancel:
                self.status.setText(
                    "An unsigned draft remains from this original wallet. Use Cancel unsigned draft "
                    "explicitly before reviewing a new payment. Signed/uncertain locks are never released.")
            elif (self._spend_enabled and result.get("reservation_count",0)>0
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
            self.last_txid.setText(result)
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
            if result["status"]=="Q06_CONFIRMED_IN_VERIFIED_HISTORY":
                self.status.setText("TXID is in complete verified confirmed history.")
            elif result.get("in_mempool") is True:
                self.status.setText(
                    "TXID is pending in this Core mempool and not yet confirmed. "
                    "Do NOT retry, remine or release coin reservations.")
            else:
                self.status.setText(
                    "TXID NOT in complete verified confirmed history; status uncertain. "
                    "Do NOT retry, remine or release coin reservations.")
        elif action=="cancel":
            self._recovered_unsigned_cancel=False
            if isinstance(result, dict) and result.get('recovered_unsigned_cancelled') is True:
                self._pending_action=('snapshot',)  # Read only, never a write retry.
            self._approved_commitment=None
            self._signed_ready=False
            self.status.setText("Unsigned draft cancelled")
        elif action=="lock":
            self._backup_unacked=False
            self._backup_flow_active=False
            self._backup_result=None
            self._ready=False
            self._unlock_allowed=True
            self._spend_enabled=False
            self._signed_ready=False
            self._approved_commitment=None
            self._pending_confirm_txid=None
            self.last_txid.clear()
            self.receive.clear()
            self.account.setText("Account: locked")
            self.balance.setText("Balance: unverified")
            self.tip.setText("Chain: unverified")
            self.history.clear()
            self.status.setText("Q06 wallet locked. Use Unlock wallet to reauthenticate "
                                "in this session; Stop owned Core and quit to close.")
        elif action=="unlock":
            # In-session reauthentication of the SAME original owned REGTEST
            # BIP39 profile. Only a genuinely verified acknowledgement promotes
            # the wallet back to a usable (ready) session; deferred or refused
            # backups return to the fail-closed backup flow.
            backup_status = result.get("backup_status", "verified") if isinstance(result, dict) else None
            if backup_status == "verified":
                self._unlock_allowed = True
                self._ready = True
                self.receive.setText(result["receive_code"])
                self.account.setText("BIP39 account: " + result["account_id"])
                self.balance.setText("Balance: not yet synced against Core")
                self.tip.setText("Chain: not yet verified")
                self.status.setText(
                    "BIP39 native seed unlocked. Activate Send after checkpoint verification.")
                # Seed authentication alone cannot scan over an existing
                # native checkpoint. Match the normal Open route: retain
                # explicit Enable sending/reconciliation consent first.
                self._pending_action = (
                    ("snapshot",) if not result.get('checkpoint_present')
                    or result.get('signer_allowed') is True else None)
                if result.get('signer_allowed') is True:
                    self._spend_enabled = True
            elif backup_status == "deferred":
                self._backup_unacked = False
                self._backup_flow_active = True
                self._backup_result = result
                self._unlock_allowed = False
                self._present_backup_ack(result)
            else:
                self._backup_unacked = True
                self._backup_flow_active = False
                self._backup_result = None
                self._unlock_allowed = False
                self.status.setText(
                    "Wallet unlock refused — backup acknowledgement state is "
                    "not verified. Custody is preserved and the wallet stays locked.")
        elif action=="quit":
            self._ready=False
            self._closed=True
        self._set_actions()

    def _present_backup_ack(self, result):
        """Subclasses override to show the production backup UI.

        The base implementation has no UI, so it fails closed: the wallet is
        deferred/locked and the flow completes as unsuccessful."""
        self._defer_active_backup()

    def _backup_flow_completed(self, success):
        """Called by the subclass UI when backup is acknowledged or deferred."""
        self._backup_flow_active = False
        result = self._backup_result
        self._backup_result = None
        if not success or result is None:
            self._backup_unacked = True
            self._unlock_allowed = False
            self.status.setText(
                "Backup not acknowledged — the created wallet stops "
                "locked and custody is preserved. Reopen with your "
                "password after recording your 12 words; they are "
                "never displayed again.")
            self._set_actions()
            self._check_quit()
            return
        self._ready = True
        self._unlock_allowed = True
        self.receive.setText(result["receive_code"])
        self.account.setText("BIP39 account: " + result["account_id"])
        self.balance.setText("Balance: not yet synced against Core")
        self.tip.setText("Chain: not yet verified")
        self.status.setText(
            "BIP39 native seed opened. Activate Send after checkpoint verification.")
        self._set_actions()
        if self._quit_requested:
            self._check_quit()
            return
        self._pending_action = ("snapshot",)
        self._finished()

    def _defer_active_backup(self):
        """Fail-safe helper used on quit/close when the backup UI is open."""
        if not self._backup_flow_active:
            return
        self._backup_flow_active = False
        try:
            self.executor.request("backup_defer", timeout=30)
        except Exception:
            pass
        self._backup_flow_completed(False)

    def _on_denied(self, code):
        code = public_code(code)
        self._last_error_code = code
        if (code == 'WALLET_UNLOCK_REFUSED' and self.executor.state.locked
                and not self.executor.state.faulted
                and not self.executor.state.reauthentication_required
                and self.executor.state.core_alive is True):
            # A failed initial Open has no earlier Lock event to expose this
            # existing control. Allow another EXPLICIT password attempt on
            # the same owner; this grants neither keys nor spending scope.
            self._unlock_allowed = True
            self._ready = False
        if self.executor.state.faulted:
            self._signed_ready=False
        self.status.setText(
            "Wallet faulted — stop spending; original state preserved for review."
            if self.executor.state.faulted else
            "Operation refused safely: " + error_text(code))
        self._set_actions()

    def _receive_result(self, action, result):
        self._completed_result = (action, result)

    def _receive_denial(self, code):
        self._completed_result = (None, code)

    def _finished(self):
        self._worker=None
        # Deliver only AFTER thread completion. A signature approval runs a
        # nested Qt event loop; finished must not drain the next command before
        # the operator has decided. No operation is retried or resubmitted.
        completed, self._completed_result = self._completed_result, None
        if completed is not None:
            self._delivering_result = True
            try:
                action, result = completed
                if action is None:
                    self._on_denied(result)
                else:
                    self._on_ready(action, result)
            finally:
                self._delivering_result = False
                completed = None
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
        elif (self._quit_requested and self._worker is None and not self.executor.busy
              and not self._delivering_result):
            self._command("quit")

    def request_quit(self):
        self._quit_requested=True
        self._defer_active_backup()
        self.status.setText("Stopping only this original owned REGTEST Core…")
        self._check_quit()

    def closeEvent(self,event):
        if self.executor.closed:
            event.accept()
        else:
            event.ignore()
            self.request_quit()


def _last_remembered_profile():
    # Remember ONLY the last successfully opened wallet profile PATH. Never
    # password, mnemonic, private keys or native anchor secrets cross here.
    from PySide6.QtCore import QSettings
    try:
        value = QSettings("WAM Privacy Wallet", "REGTEST").value("last_bip39_profile", type=str)
        return str(value) if value else ""
    except Exception:
        return ""


def _onboarding_password(parent, mode):
    """Recoverable input validation before any executor request creates custody."""
    while True:
        password, ok = QInputDialog.getText(
            parent, "Q06 BIP39 wallet (REGTEST only)",
            "Disposable encrypted-seed password (12–1024 UTF-8 bytes)",
            QLineEdit.EchoMode.Password)
        if not ok:
            return "", False
        if not 12 <= len(password.encode("utf-8")) <= 1024:
            password = ""
            QMessageBox.warning(parent, "Q06 password",
                                "Use a disposable password of 12–1024 UTF-8 bytes.")
            continue
        if mode in ("create", "restore"):
            confirmation, confirmed = QInputDialog.getText(
                parent, "Confirm wallet password", "Enter the same password again.",
                QLineEdit.EchoMode.Password)
            if not confirmed:
                password = confirmation = ""
                return "", False
            matches = password == confirmation
            confirmation = ""
            if not matches:
                password = ""
                QMessageBox.warning(parent, "Q06 password",
                                    "Passwords do not match. Please try again.")
                continue
        return password, True


def launch_bip39_trial(root,core,source,*,mode,authorized=False,shared_profile=None):
    if authorized is not True or mode not in ("create","restore","reopen"):
        raise ValueError("Q06_GUI_EXPLICIT_REGTEST_CONSENT_REQUIRED")
    # The caller already obtained explicit selection of the supervisor root.
    # A remembered seed-container path is only a GUI hint, never authority to
    # redirect Core or select a different profile after the user's choice.
    app=qt_application()
    app.setQuitOnLastWindowClosed(False)
    executor=WalletExecutor(lambda:Bip39ReadOnlyBackend(root,core,source,shared_profile=shared_profile))
    # Normal application: use the pre-existing WAM Fusion navigation,
    # Overview, QR Receive, History, Send and Security components. Frozen
    # diagnostic Q06 probes retain their independent owner/spend contracts.
    from .bip39_fusion_gui import Bip39FusionWindow
    window=Bip39FusionWindow(executor,shared_profile=shared_profile)
    window.show()
    password, ok = _onboarding_password(window, mode)
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
