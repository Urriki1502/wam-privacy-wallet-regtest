"""Native disposable test-wallet Send/Sign/Broadcast and Security/Settings UI."""
import sys
from . import custody
from decimal import Decimal, InvalidOperation
from pathlib import Path
import secrets
import re
from PySide6.QtCore import QThread, Signal, QTimer, Qt
from PySide6.QtWidgets import (
    QApplication,QFrame,QVBoxLayout,QLabel,QLineEdit,QPushButton,QHBoxLayout,QDialog,
    QFileDialog,QMessageBox,QInputDialog,QComboBox,QCheckBox,QScrollArea,
)
from wam_regtest.desktop import RegtestWalletWindow, qt_application
from wam_regtest.wallet_session import WalletSession, PaymentReview
from wam_regtest.wallet_read import format_wam
from .fusion_ui import panel,page,label,action,ResponsiveRow,ReadableText
from .fusion_pages import PaymentSteps,PaymentApproval
from .amounts import _parse_atoms,parse_amount
from .gui_errors import operation_error,error_text,public_code,INPUT_ERRORS


class OperationWorker(QThread):
    ready=Signal(str,object)
    denied=Signal(str)
    def __init__(self, session, action, args):
        super().__init__()
        self.session,self.action,self.args=session,action,args
    def disclose(self,txid,fields,password):
        return self.session.disclose_record(txid,fields,password,approved=True)
    def run(self):
        try:
            methods={"prepare":self.session.prepare,"sign":self.session.sign,
                     "broadcast":self.session.broadcast,"cancel":self.session.cancel,
                     "lock":self.session.lock,"unlock":self.session.unlock,
                     "backup":self.session.backup,"recover":self.session.recover_backup,
                     "mine":self.session.mine,"network":self.session.network_diagnostics,"disclose":self.disclose}
            result=methods[self.action](*self.args)
            self.ready.emit(self.action,result)
        except Exception as error:
            self.denied.emit(operation_error(self.action,error))
        finally:
            self.args=()  # Release temporary GUI passphrase copies, best effort.


class OperationalWalletWindow(RegtestWalletWindow):
    operation_completed=Signal(str,object)
    operation_failed=Signal(str)
    def __init__(self,session):
        self.session=session
        self.review=None
        self.signed=False
        self._submitted_txid=None
        self._approval_open=False
        super().__init__(session.core_dir,session.datadir,session.source,session=session)
        self.setWindowTitle("WAM Privacy Wallet · Disposable REGTEST")
        self.warning.setText("REGTEST ONLY · DISPOSABLE TEST KEYS · NO REAL FUNDS")
        self.navigation.addItems(["Send","Security","Settings"])
        send,layout=page('Send a silent payment','Prepare an exact recipient, amount and fee. Signing and broadcast require separate approval.','TRANSACTIONS / SEND')
        self.steps=PaymentSteps();layout.addWidget(self.steps)
        form,fl=panel('Payment details','BIP352 · disposable REGTEST funds only')
        self.recipient=QLineEdit();self.recipient.setMaxLength(256);self.recipient.setPlaceholderText('wamrtsp1… full silent-payment code');self.recipient.setAccessibleName('Silent payment recipient')
        self.amount=QLineEdit();self.amount.setMaxLength(32);self.amount.setPlaceholderText('0.00000000');self.amount.setAccessibleName('Payment amount in WAM')
        self.fee=QLineEdit('0.00010000');self.fee.setMaxLength(32);self.fee.setAccessibleName('Fee in WAM')
        fl.addWidget(label('Recipient payment code','FusionKicker'));fl.addWidget(self.recipient)
        numbers=QHBoxLayout()
        for title,widget in (('AMOUNT / WAM',self.amount),('FEE / WAM',self.fee)):
            col=QVBoxLayout();col.addWidget(label(title,'FusionKicker'));col.addWidget(widget);numbers.addLayout(col,1)
        fl.addLayout(numbers);fl.addWidget(label('Exact atom arithmetic · fee limit 0.01 WAM. No market-price conversion.'))
        self.prepare_button=action('Prepare payment','send',True);fl.addWidget(self.prepare_button)
        review,rl=panel('Review before approval','The recipient, amount, fee and change are bound to the prepared commitment.')
        self.review_text=ReadableText('No active payment review. Prepare a payment to inspect its exact details.');rl.addWidget(self.review_text,1)
        self.sign_button=action('Approve & Sign','security',True);self.broadcast_button=action('Broadcast','send');self.cancel_button=action('Cancel unsigned draft','history');rl.addWidget(self.sign_button);rl.addWidget(self.broadcast_button);rl.addWidget(self.cancel_button)
        layout.addWidget(ResponsiveRow(form,review,weights=[3,2]));layout.addWidget(label('Signing retains irreversible input reservations. An uncertain broadcast result must be recovered, never silently retried.','FusionGold'));layout.addStretch();self.stack.addWidget(send)
        self.prepare_button.clicked.connect(self.prepare_payment);self.sign_button.clicked.connect(lambda:self.approve_payment('sign'));self.broadcast_button.clicked.connect(lambda:self.approve_payment('broadcast'));self.cancel_button.clicked.connect(lambda:self.start_operation('cancel'))

        security,layout=page('Wallet security','Understand the actual custody boundaries. No invented score or production guarantee.','CUSTODY / SECURITY')
        vault,vl=panel('Encrypted wallet','WSP-1 AES-GCM / scrypt · native private storage')
        self.vault_state=label('Awaiting wallet state','FusionCardValue');vl.addWidget(self.vault_state);vl.addWidget(label('SQLite is plaintext in the private runtime while unlocked. Secret memory clearing is best effort.'))
        row=QHBoxLayout();self.lock_button=action('Lock wallet','lock');self.lock_button.setObjectName('FusionDestructive');self.unlock_button=action('Unlock','unlock',True);row.addWidget(self.lock_button);row.addWidget(self.unlock_button);vl.addLayout(row)
        anchor,al=panel('Checkpoint anchor',custody.anchor_label())
        self.anchor_state=label('Not attested','FusionCardValue');al.addWidget(self.anchor_state);al.addWidget(label('Generation and ciphertext digest guard file rollback and stale writers. Loss, replacement or OS profile rollback require explicit recovery handling.'))
        layout.addWidget(ResponsiveRow(vault,anchor))
        backup,bl=panel('Encrypted backup','Save the latest anchored generation after each payment.')
        self.backup_button=action('Save encrypted backup','backup',True);bl.addWidget(self.backup_button);bl.addWidget(label('Backup contains encrypted test keys and reservations. Preserve the passphrase separately.'))
        recovery,rl=panel('Verified recovery','Unlock only after live chain verification and rescan.')
        self.recover_button=action('Recover latest backup','sync');rl.addWidget(self.recover_button);rl.addWidget(label('Older generations are rejected. Original test keys and irreversible reservations are preserved.'))
        layout.addWidget(ResponsiveRow(backup,recovery))
        disclosure,dl=panel('Local selective disclosure','Choose exact verified fields, then approve and re-authenticate. Nothing is sent to a network.')
        self.disclosure_record=QComboBox();self.disclosure_record.setAccessibleName('Select local confirmed record');dl.addWidget(self.disclosure_record)
        self.disclosure_fields={};fields_row=QHBoxLayout()
        for field in ('txid','block_height','credit_atoms','debit_atoms'):
            check=QCheckBox(field.replace('_',' ').title());fields_row.addWidget(check);self.disclosure_fields[field]=check
        dl.addLayout(fields_row);self.disclosure_button=action('Review disclosure scope','security');dl.addWidget(self.disclosure_button);self.disclosure_text=label('No verified local disclosure. This is not an ownership proof.','FusionMuted',True);dl.addWidget(self.disclosure_text);layout.addWidget(disclosure);layout.addStretch();self.stack.addWidget(security)
        self.lock_button.clicked.connect(lambda:self.start_operation('lock'));self.unlock_button.clicked.connect(self.unlock_wallet);self.backup_button.clicked.connect(self.backup_wallet);self.recover_button.clicked.connect(self.recover_wallet);self.disclosure_button.clicked.connect(self.disclose_selected)

        settings,layout=page('Settings','Native appearance and the actual local REGTEST environment.','PREFERENCES / SETTINGS')
        appearance,apl=panel('Appearance','Signature Dark, Signature Light or native system Auto.')
        self.settings_appearance=QComboBox()
        for text,value in (('Auto · system','auto'),('Signature Light','light'),('Signature Dark','dark')):self.settings_appearance.addItem(text,value)
        self.settings_appearance.currentIndexChanged.connect(self.appearance.setCurrentIndex)
        self.appearance.currentIndexChanged.connect(self.settings_appearance.setCurrentIndex)
        apl.addWidget(self.settings_appearance);apl.addWidget(label('Auto responds to native Qt operating-system appearance events without a restart.'))
        build,bl=panel('Application','Experimental REGTEST · WAM Fusion 2.0')
        import PySide6
        bl.addWidget(label({'darwin':'macOS ARM64','win32':'Windows x64','linux':'Linux x86_64 experimental'}.get(sys.platform,'Unsupported platform')+' / Qt '+PySide6.__version__))
        bl.addWidget(label('Linux experimental · PayJoin validation only. No production or real-fund operations.'))
        layout.addWidget(ResponsiveRow(appearance,build))
        node,nl=panel('Developer WAM Core' if sys.platform=='linux' else 'Official WAM Core',
            'Pinned upstream source build · not a signed release' if sys.platform=='linux' else 'v0.1.11 · independent binary identity checks')
        self.core_identity=label('No verified Core identity in this session','ReceiveCode',True);nl.addWidget(self.core_identity);layout.addWidget(node)
        privacy,pl=panel('Local network policy','Scan and broadcast use the same isolated local REGTEST node.')
        self.network_button=action('Verify node privacy','security');pl.addWidget(self.network_button);self.network_text=label('Remote/proxy routes and fallback are unavailable. Zero peers must be verified; there is no anonymity guarantee.');pl.addWidget(self.network_text);layout.addWidget(privacy)
        sync,sl=panel('Synchronization & test blocks','Background sync every 30 seconds. Manual sync re-verifies the live chain.')
        self.settings_sync=action('Sync verified chain','sync');self.settings_sync.clicked.connect(self.request_sync);sl.addWidget(self.settings_sync)
        self.mine_button=action('Mine one REGTEST block','core');sl.addWidget(self.mine_button);sl.addWidget(label('Mining confirms disposable test transactions only. The test chain is removed when this developer session closes.','FusionGold'));layout.addWidget(sync);layout.addStretch();self.stack.addWidget(settings)
        self.mine_button.clicked.connect(lambda:self.start_operation('mine'));self.network_button.clicked.connect(lambda:self.start_operation('network'))
        self.appearance.setItemText(0,'Auto · '+{'win32':'Windows','darwin':'macOS','linux':'Linux desktop'}.get(sys.platform,'system'))
        self.dashboard.go_send.clicked.connect(lambda:self.navigation.setCurrentRow(3));self.dashboard.open_security.clicked.connect(lambda:self.navigation.setCurrentRow(4))
        self._actions=(self.prepare_button,self.sign_button,self.broadcast_button,self.cancel_button,self.lock_button,self.unlock_button,self.backup_button,self.recover_button,self.mine_button,self.network_button,self.disclosure_button)
        self._update_controls();self.apply_theme()

    def approve_payment(self,kind):
        if self._approval_open or self.review is None or self._worker is not None or self.session.locked or self.session.faulted:return
        if kind=='sign' and self.signed or kind=='broadcast' and not self.signed:return
        review=self.review
        dialog=PaymentApproval(review,kind,self)
        self._approval_open=True
        self._update_controls()
        try:
            approved=dialog.exec()==QDialog.DialogCode.Accepted
        finally:
            self._approval_open=False
            dialog.deleteLater()
            self._update_controls()
        if approved and self.review is review:self.start_operation(kind,review.commitment)

    def _update_controls(self):
        if not hasattr(self,"_actions"):
            return
        busy=self._worker is not None or self._approval_open
        unlocked=not self.session.locked and not self.session.faulted
        self.dashboard.go_send.setEnabled(not busy and unlocked)
        # A locked user must still be able to reach recovery/security.
        self.dashboard.open_security.setEnabled(not busy)
        for button in self._actions:
            button.setEnabled(not busy and unlocked)
        self.prepare_button.setEnabled(not busy and unlocked and self.review is None)
        self.sign_button.setEnabled(not busy and unlocked and self.review is not None and not self.signed)
        self.broadcast_button.setEnabled(not busy and unlocked and self.review is not None and self.signed)
        self.cancel_button.setEnabled(not busy and unlocked and self.review is not None and not self.signed)
        self.unlock_button.setEnabled(not busy and self.session.locked)
        self.recover_button.setEnabled(not busy and self.session.locked)
        self.lock_button.setEnabled(not busy and not self.session.locked)
        self.disclosure_record.setEnabled(not busy and unlocked)
        for field in self.disclosure_fields.values(): field.setEnabled(not busy and unlocked)
        self.disclosure_button.setEnabled(not busy and unlocked and self.disclosure_record.count()>0)
        if hasattr(self,"vault_state"):
            self.vault_state.setText("Locked" if self.session.locked else "Faulted · reservations retained" if self.session.faulted else "Unlocked test wallet")
            self.anchor_state.setText("Checked on latest wallet snapshot" if self._snapshot is not None and unlocked else "Re-verify on next wallet operation")
            self.settings_sync.setEnabled(not busy and unlocked)
            self.steps.set_stage(2 if busy and getattr(self._worker,"action",None)=="sign" else 3 if self.signed else 1 if self.review is not None else 0)
        editable=not busy and unlocked and self.review is None
        for field in (self.recipient,self.amount,self.fee):
            field.setEnabled(editable)

    def start_operation(self,action,*args):
        if self._worker is not None:
            return
        worker=OperationWorker(self.session,action,args)
        self._worker=worker
        self.refresh_button.setEnabled(False)
        labels={"prepare":"Preparing payment review", "sign":"Signing approved payment",
                "broadcast":"Submitting approved transaction", "cancel":"Canceling unsigned draft",
                "lock":"Locking wallet", "unlock":"Verifying passphrase and live chain",
                "backup":"Saving latest encrypted backup", "recover":"Verifying anchored recovery",
                "mine":"Mining one REGTEST block","network":"Verifying local node privacy","disclose":"Verifying local disclosure consent"}
        self.status.setText(labels[action]+"…")
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
        except (ValueError,InvalidOperation,OverflowError):
            self._operation_denied("WALLET_INPUT_AMOUNT_INVALID")
            return
        try:
            # Fee has a lower dust-independent floor and explicit WSP limit.
            fee=_parse_atoms(self.fee.text(),1,1_000_000)
        except (ValueError,InvalidOperation,OverflowError):
            self._operation_denied("WALLET_INPUT_FEE_INVALID")
            return
        self.start_operation("prepare",self.recipient.text().strip(),atoms,fee)

    def _operation_ready(self,action,result):
        if action in ("prepare","sign"):
            self.review=result
            self.recipient.setCursorPosition(0)
            self.signed=action=="sign"
            self.review_text.setText(
                f"{'SIGNED — ready to broadcast' if self.signed else 'REVIEW BEFORE SIGNING'}\n"
                f"Recipient: {result.code}\nAmount: {format_wam(result.atoms)} WAM ({result.atoms} atoms)\n"
                f"Fee: {format_wam(result.fee)} WAM ({result.fee} atoms)\n"
                f"Change: {format_wam(result.change_atoms)} WAM ({result.change_atoms} atoms)\n"
                f"Inputs: {result.input_count}")
        elif action in ("cancel","broadcast","lock"):
            self.review=None
            self.signed=False
            if action=="broadcast":
                self._submitted_txid=result
            elif action=="lock":
                self._submitted_txid=None
            self.review_text.setText("SUBMITTED · confirmation not yet observed\nTransaction: "+result if action=="broadcast" else "No active payment review")
        if action=="disclose":
            import json
            self.disclosure_text.setText(json.dumps(result,sort_keys=True))
        if action=="network":
            self.network_text.setText("VERIFIED LOCAL REGTEST · zero peers\nScan/broadcast share the private local node.\nNo remote routes, proxy or clearnet fallback; anonymity unqualified.")
        if action=="lock":
            self._clear_balance()
            self.status.setText("LOCKED · encrypted snapshot anchored in "+custody.anchor_label())
        else:
            message = ("BACKUP SAVED · latest anchored generation" if action=="backup" else
                       "BROADCAST SUBMITTED · mine a block and sync to verify confirmation" if action=="broadcast" else
                       "SIGNED · reservations retained; Broadcast requires separate approval" if action=="sign" else
                       "REVIEW READY · verify recipient, amount and fee before Sign" if action=="prepare" else
                       "REGTEST operation completed · sync to refresh confirmed history")
            self.status.setText(message)
            if action in ("unlock","recover","mine"):
                self.apply_snapshot(result)
        self._update_controls()
        self.operation_completed.emit(action,result)

    def apply_snapshot(self,snap):
        super().apply_snapshot(snap)
        if self._snapshot is not None and self._submitted_txid is not None:
            confirmed=next((r for r in snap.history if r.txid==self._submitted_txid and r.confirmations>0),None)
            if confirmed is not None:
                if self.review is None:
                    self.review_text.setText("CONFIRMED · block "+str(confirmed.block_height)+"\nTransaction: "+self._submitted_txid)
                self._submitted_txid=None
            else:
                # This is a local submission receipt, not a synthetic mempool
                # balance or evidence the node still holds the transaction.
                self.status.setText(self.status.text()+" · SUBMITTED: confirmation not yet observed; balance is confirmed only")
        if hasattr(self,"core_identity"):
            self.core_identity.setText("SHA-256 / "+snap.core_sha256 if self._snapshot is not None else "Core identity not verified")
        if hasattr(self,"disclosure_record"):
            self.disclosure_record.clear()
            if self._snapshot is not None:
                for row in snap.history:
                    self.disclosure_record.addItem(row.txid[:16]+"… · block "+str(row.block_height),row.txid)
            self._update_controls()

    def _clear_balance(self):
        super()._clear_balance()
        if hasattr(self,'disclosure_record'):
            self.disclosure_record.clear();self.disclosure_text.setText('No verified local disclosure')
            self.core_identity.setText('No verified Core identity in this session')
            if self.session.locked or self.session.faulted:
                self._submitted_txid=None
                self.recipient.clear();self.amount.clear();self.review_text.setText('Wallet locked or faulted · verify recovery before payment details are displayed.')
            self._update_controls()

    def disclose_selected(self):
        fields=tuple(sorted(k for k,v in self.disclosure_fields.items() if v.isChecked()))
        txid=self.disclosure_record.currentData()
        if not fields or txid is None:
            return
        if QMessageBox.question(self,"Local disclosure approval",
                "Display only "+", ".join(fields)+" for the selected local record?\n"
                "No ownership proof; nothing is sent to a network.",
                QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:
            return
        password=self._passphrase("Wallet passphrase for selected local disclosure")
        if password is not None:
            self.start_operation("disclose",txid,fields,password)

    def _operation_denied(self,reason):
        reason=public_code(reason)
        if (reason in INPUT_ERRORS and self._snapshot is not None
                and not self.session.locked and not self.session.faulted):
            # Only known pre-mutation input/coin-selection refusals retain a
            # previously live-verified snapshot. Never label it fresh/current.
            self.verification_badge.setText("Last verified · "+str(self._snapshot.height))
        else:
            self.network_text.setText("UNVERIFIED · run local node privacy verification again")
            self._clear_balance()
        self.status.setText(error_text(reason))
        self.operation_failed.emit(reason)
        self._update_controls()

    def request_sync(self):
        # Timer/manual refresh must not occupy the worker inside the modal
        # approval loop. The signer still reattests the live chain and intent.
        if self._approval_open:return
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
            approved=self._core_reauthentication_consent()
            if approved is None:return
            self.start_operation("unlock",password,approved)

    def _core_reauthentication_consent(self):
        if not self.session._core_reauthentication_required:return False
        answer=QMessageBox.question(self,'Verify original REGTEST Core',
            'Core authentication or identity previously failed. After the wallet passphrase and custody are verified, '
            'explicitly reauthenticate the SAME owned REGTEST process using its current private credentials?\n'
            'No external node adoption, transaction retry, wallet replacement or custody reset.',
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)
        return True if answer==QMessageBox.StandardButton.Yes else None

    def backup_wallet(self):
        parent=QFileDialog.getExistingDirectory(self,"Select parent for a new private encrypted backup folder")
        if parent:
            directory=Path(parent).resolve()/("wam-regtest-backup-"+secrets.token_hex(6))
            try:
                custody.create_directory(directory)
                self.start_operation("backup",directory,"wallet-backup.enc")
            except (OSError,ValueError):
                self._operation_denied("WALLET_BACKUP_DIRECTORY_DENIED")

    def recover_wallet(self):
        name,_=QFileDialog.getOpenFileName(self,"Latest anchored REGTEST backup",filter="Encrypted backups (*.enc)")
        if name:
            password=self._passphrase("Backup passphrase")
            if password is not None:
                approved=self._core_reauthentication_consent()
                if approved is None:return
                path=Path(name).absolute()
                self.start_operation("recover",path.parent,path.name,password,approved)

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
        ["Create fresh test keys","Recover latest backup on this computer"],0,False)
    if not ok:
        return 0
    backup=None
    if choice=="Recover latest backup on this computer":
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
    encoded=None
    password=""
    window=OperationalWalletWindow(session)
    window.show()
    QTimer.singleShot(0,window.request_sync)
    return app.exec()
