"""Fusion GUI bound to one authenticated persistent REGTEST Core owner.

Operator-initiated onboarding creates exactly one native encrypted WSP wallet.
Separate read-only and explicitly checkpoint-persisting sync actions use the
narrow authenticated WSP IPC scanner. No Core wallet RPC, signer, broadcast,
mainnet or automatic wallet replacement is exposed by this GUI.
"""
from __future__ import annotations

from pathlib import Path
import re

from PySide6.QtCore import QThread, Signal, QTimer
from PySide6.QtWidgets import QMessageBox, QInputDialog, QLineEdit, QFileDialog

from .desktop import RegtestWalletWindow, qt_application
from .fusion_ui import action
from .supervisor_client import control
from .supervisor_protocol import public_status

VISIBLE_STATES = {
    "stopped": "STOPPED",
    "starting": "STARTING",
    "syncing": "SYNCING",
    "busy": "NODE BUSY · RETRYING",
    "ready": "READY",
    "recovery-needed": "RECOVERY NEEDED",
    "error": "ERROR · supervisor refused",
}


class _ManagedStatusWorker(QThread):
    ready = Signal(object)
    denied = Signal(str)

    def __init__(self, root: Path, operation: str):
        super().__init__()
        self.root, self.operation = root, operation

    def run(self):
        try:
            result = control(self.root, self.operation,
                authorized=self.operation != "status", timeout=15 if self.operation != "status" else 3)
            self.ready.emit(result)
        except Exception:
            # Never echo exception text, private paths or RPC credentials.
            self.denied.emit("MANAGED_SUPERVISOR_UNVERIFIED")


class _LockedWalletWorker(QThread):
    ready = Signal(object)
    denied = Signal(str)

    def __init__(self, root, core_dir, wsp_source, password):
        super().__init__()
        self.root,self.core_dir,self.wsp_source=root,core_dir,wsp_source
        self.password=password

    def run(self):
        try:
            from .managed_wallet_binding import verify_locked_wallet
            value=verify_locked_wallet(self.root,self.core_dir,self.wsp_source,
                                       self.password,authorized=True)
            self.ready.emit(value)
        except Exception:
            self.denied.emit("MANAGED_WALLET_CHECKPOINT_UNVERIFIED")
        finally:
            self.password=None



class _CrashPreviewWorker(QThread):
    """Original-owner, non-spending REGTEST crash residue inspection."""
    ready=Signal(object)
    denied=Signal(str)

    def __init__(self,root,core_dir,wsp_source,password,observe_core):
        super().__init__()
        self.root,self.core_dir,self.wsp_source=root,core_dir,wsp_source
        self.password=password
        self.observe_core=observe_core

    def run(self):
        try:
            from .managed_wallet_crash_preview import inspect_managed_crash_preview
            value=inspect_managed_crash_preview(
                self.root,self.core_dir,self.wsp_source,self.password,
                authorized=True,observe_recent_core=self.observe_core)
            self.ready.emit(value)
        except Exception:
            self.denied.emit("K09_GUI_CRASH_PREVIEW_UNVERIFIED")
        finally:
            self.password=None


class _ManagedWalletSnapshotWorker(QThread):
    """Explicit original WSP wallet scan, without signer or broadcast."""
    ready = Signal(object)
    denied = Signal(str)

    def __init__(self, root, core_dir, wsp_source, password, *,
                 persist_checkpoint=False):
        super().__init__()
        self.root,self.core_dir,self.wsp_source=root,core_dir,wsp_source
        self.password=password
        self.persist_checkpoint=persist_checkpoint

    def run(self):
        try:
            from .managed_wallet_snapshot import read_managed_wallet_snapshot
            result=read_managed_wallet_snapshot(
                self.root,self.core_dir,self.wsp_source,self.password,
                authorized_readonly=True,
                authorized_persist_checkpoint=self.persist_checkpoint)
            self.ready.emit(result)
        except Exception:
            self.denied.emit("MANAGED_WALLET_SNAPSHOT_UNVERIFIED")
        finally:
            # Python cannot guarantee zeroization of immutable bytes.
            self.password=None



class _ManagedWalletCreateWorker(QThread):
    """Create exactly one OS-anchored WSP wallet after user opt-in."""
    ready = Signal(object)
    denied = Signal(str)

    def __init__(self,root,core_dir,wsp_source,password,*,
                 bip39_phrase=None,bip39_passphrase=None):
        super().__init__()
        self.root,self.core_dir,self.wsp_source=root,core_dir,wsp_source
        self.password=password
        self.bip39_phrase=bip39_phrase
        self.bip39_passphrase=bip39_passphrase

    def run(self):
        try:
            from .managed_wallet_create import create_managed_wallet
            value=create_managed_wallet(
                self.root,self.core_dir,self.wsp_source,self.password,
                authorized=True,bip39_phrase=self.bip39_phrase,
                bip39_passphrase=self.bip39_passphrase)
            self.ready.emit(value)
        except Exception:
            self.denied.emit("MANAGED_WALLET_CREATE_UNVERIFIED")
        finally:
            self.password=None
            self.bip39_phrase=None
            self.bip39_passphrase=None



class _ManagedSpendSessionWorker(QThread):
    ready=Signal(object)
    denied=Signal(str)

    def __init__(self,root,core_dir,wsp_source,password):
        super().__init__()
        self.root,self.core_dir,self.wsp_source=root,core_dir,wsp_source
        self.password=password

    def run(self):
        try:
            from .managed_spend_session import ManagedWalletSession
            session=ManagedWalletSession.reopen_spending(
                self.root,self.core_dir,self.wsp_source,self.password,
                authorized=True)
            self.ready.emit(session)
        except Exception:
            self.denied.emit("MANAGED_SPEND_SESSION_OPEN_DENIED")
        finally:
            self.password=None


class _CoreSqliteInspectionWorker(QThread):
    """K-04 GUI receives ONLY redacted non-secret file format metadata."""
    ready=Signal(object)
    denied=Signal(str)

    def __init__(self,source):
        super().__init__()
        self.source=source

    def run(self):
        try:
            from .legacy_bdb_refusal import inspect_backup_format
            record=inspect_backup_format(self.source)
            self.ready.emit({
                "format":"sqlite","size":record.byte_count,
                "network":"UNVERIFIED","restored":False,
                "wallet_signer_allowed":False,"mainnet_allowed":False,
            })
        except Exception as error:
            # Only a fixed, non-secret category crosses the Qt boundary.
            from .core_sqlite_import import CoreSqliteImportError
            categories={
                "K05_BDB_DEPRECATED_UNSUPPORTED",
                "K05_FUSION_ENCRYPTED_BACKUP_SEPARATE",
                "K05_MNEMONIC_TEXT_NOT_WALLET_DAT",
                "K05_UNKNOWN_CORE_DAT_DENIED",
                "K05_SQLITE_PRIVATE_CUSTODY_REQUIRED",
            }
            reason=(error.args[0] if type(error) is CoreSqliteImportError
                    and error.args and error.args[0] in categories
                    else "K04_SQLITE_SOURCE_DENIED")
            self.denied.emit(reason)
        finally:
            self.source=None


class ManagedCoreWindow(RegtestWalletWindow):
    """Fusion GUI lifecycle observer; closing this window NEVER stops Core."""

    def __init__(self, root: Path, *, core_dir=None, wsp_source=None):
        if type(root) is not type(Path()) or not root.is_absolute():
            raise ValueError("MANAGED_GUI_ROOT_DENIED")
        if (core_dir is None) is not (wsp_source is None):
            raise ValueError("MANAGED_GUI_WALLET_PATHS_DENIED")
        if core_dir is not None and (
            type(core_dir) is not type(Path()) or not core_dir.is_absolute()
            or type(wsp_source) is not type(Path()) or not wsp_source.is_absolute()
        ):
            raise ValueError("MANAGED_GUI_WALLET_PATHS_DENIED")
        self._managed_root = root
        self._wallet_core_dir,self._wallet_wsp_source=core_dir,wsp_source
        self._wallet_checkpoint_verified=False
        self._wallet_read_authorized=False
        self._managed_height=None
        self._spend_window=None
        # The base Fusion shell is reused; its disposable wallet data loader
        # is never called. A managed WSP session must first be restored safely.
        super().__init__(root / "chain", root / "chain", root / "chain")
        self.setWindowTitle("WAM Fusion · Persistent Core REGTEST")
        self.warning.setText("REGTEST ONLY · MANAGED CORE · WALLET LOCKED / UNVERIFIED")
        self.status.setText("Connecting to authenticated managed Core…")
        self.verification_badge.setText("Core not yet verified")
        self._managed_state = "error"
        self._managed_authenticated = False
        self._clear_balance()
        self.dashboard.go_send.setEnabled(False)
        self.dashboard.manual_sync.setEnabled(True)
        toolbar = self.refresh_button.parentWidget().layout()
        self.start_core = action("Start owned Core", "core")
        self.stop_core = action("Stop owned Core", "core")
        toolbar.addWidget(self.start_core)
        toolbar.addWidget(self.stop_core)
        self.verify_wallet_button=action("Verify locked wallet", "security")
        toolbar.addWidget(self.verify_wallet_button)
        self.verify_wallet_button.clicked.connect(self._verify_wallet)
        self.crash_preview_button=action(
            "Inspect crash recovery · READ ONLY", "security")
        toolbar.addWidget(self.crash_preview_button)
        self.crash_preview_button.clicked.connect(self._inspect_crash_preview)
        self.view_wallet_button=action("View verified wallet · read only", "sync")
        toolbar.addWidget(self.view_wallet_button)
        self.view_wallet_button.clicked.connect(
            lambda: self._view_wallet(persist_checkpoint=False))
        self.sync_wallet_button=action("Sync + save encrypted checkpoint", "sync")
        toolbar.addWidget(self.sync_wallet_button)
        self.sync_wallet_button.clicked.connect(
            lambda: self._view_wallet(persist_checkpoint=True))
        self.create_wallet_button=action(
            "Create legacy WSP wallet (NOT BIP39)", "security")
        toolbar.addWidget(self.create_wallet_button)
        self.create_wallet_button.clicked.connect(self._create_wallet)
        self.create_bip39_wallet_button=action(
            "Create NEW BIP39 WSP wallet (REGTEST)", "security")
        toolbar.addWidget(self.create_bip39_wallet_button)
        self.create_bip39_wallet_button.clicked.connect(
            self._create_bip39_wallet)
        # K-01 is a local, separate, non-persisting BIP39 backup workflow.
        # These words MUST NOT be represented as the legacy WSP wallet seed.
        self.bip39_button=action("BIP39 backup words (not wallet)", "security")
        toolbar.addWidget(self.bip39_button)
        self.bip39_button.clicked.connect(self._create_bip39_phrase)
        self.sqlite_inspect_button=action(
            "Inspect Core .dat / Fusion .enc · NO IMPORT", "security")
        toolbar.addWidget(self.sqlite_inspect_button)
        self.sqlite_inspect_button.clicked.connect(self._choose_core_sqlite)
        # One local file only. A drop/picker NEVER activates Core RPC.
        self.setAcceptDrops(True)
        self.spend_wallet_button=action("Open REGTEST Send / Sign", "send")
        toolbar.addWidget(self.spend_wallet_button)
        self.spend_wallet_button.clicked.connect(self._open_spending_wallet)
        self.start_core.clicked.connect(lambda: self._execute("start"))
        self.stop_core.clicked.connect(self._confirm_stop)
        # F-08: guided welcome is a NAVIGATION view, never a wallet state.
        # Keep prior guarded controls and worker entrypoints unchanged; page
        # buttons delegate to their exact original handlers.
        from .f08_welcome import ManagedWelcomePage
        self.welcome_page=ManagedWelcomePage()
        self.navigation.addItem("Get Started")
        self.stack.addWidget(self.welcome_page)
        pairs=(
            (self.welcome_page.refresh,self.refresh_button),
            (self.welcome_page.start,self.start_core),
            (self.welcome_page.create,self.create_bip39_wallet_button),
            (self.welcome_page.verify,self.verify_wallet_button),
            (self.welcome_page.inspect,self.sqlite_inspect_button),
            (self.welcome_page.view,self.view_wallet_button),
            (self.welcome_page.sync,self.sync_wallet_button),
            (self.welcome_page.send,self.spend_wallet_button),
        )
        self._f08_welcome_sources=pairs
        for page_button,original in pairs:
            page_button.clicked.connect(original.click)
        # F-08: the topbar previously forced >10 buttons onto one row,
        # overflowing small/high-DPI displays. Relocate secondary actions to
        # the scrollable Welcome view without changing their actual policy.
        for button in (
            self.verify_wallet_button,self.crash_preview_button,
            self.view_wallet_button,self.sync_wallet_button,
            self.create_wallet_button,self.create_bip39_wallet_button,
            self.bip39_button,self.sqlite_inspect_button,self.spend_wallet_button,
        ):
            button.hide()
        self.navigation.setCurrentRow(3)
        # A short timer makes transitions visible without polling from Qt's
        # UI thread or creating an unbounded Core RPC request queue.
        self._sync_timer.setInterval(5_000)
        self._update_controls()

    def _update_controls(self):
        if not hasattr(self, "start_core"):
            return
        idle = self._worker is None and self._spend_window is None
        self.start_core.setEnabled(
            idle and self._managed_authenticated and
            self._managed_state in ("stopped", "recovery-needed")
        )
        self.stop_core.setEnabled(
            idle and self._managed_authenticated and
            self._managed_state in ("ready", "syncing", "busy")
        )
        self.refresh_button.setEnabled(idle)
        self.sqlite_inspect_button.setEnabled(idle)
        self.bip39_button.setEnabled(idle)
        can_read=(idle and self._managed_authenticated
                  and self._managed_state=="ready" and self._managed_height is not None
                  and self._wallet_core_dir is not None
                  and self._wallet_wsp_source is not None)
        self.verify_wallet_button.setEnabled(can_read)
        self.crash_preview_button.setEnabled(
            can_read and (self._managed_root/"chain"/"wallet-vault").is_dir())
        self.view_wallet_button.setEnabled(can_read)
        self.sync_wallet_button.setEnabled(can_read)
        self.create_wallet_button.setEnabled(
            can_read and not (self._managed_root/"chain"/"wallet-vault").exists())
        self.create_bip39_wallet_button.setEnabled(
            can_read and not (self._managed_root/"chain"/"wallet-vault").exists())
        self.spend_wallet_button.setEnabled(
            can_read and (self._managed_root/"chain"/"wallet-vault").is_dir())
        if hasattr(self, "welcome_page"):
            # NEVER trust a page-owned boolean for Core or spending policy:
            # each entry point inherits its existing protected handler.
            vault=(self._managed_root/"chain"/"wallet-vault")
            self.welcome_page.render_status(
                state=self._managed_state,
                authenticated=self._managed_authenticated,
                height=self._managed_height,
                wallet_exists=vault.exists())
            for page_button,existing in self._f08_welcome_sources:
                page_button.setEnabled(existing.isEnabled())

    def apply_theme(self, *_):
        super().apply_theme(*_)
        if hasattr(self, "welcome_page"):
            from .fusion_ui import vector_icon,fusion_palette
            self.navigation.item(3).setIcon(
                vector_icon('core',fusion_palette(self._active_theme)['accent'],
                            self.devicePixelRatioF()))

    def _execute(self, operation: str):
        if self._worker is not None:
            return
        if operation not in ("status", "start", "shutdown"):
            raise ValueError("MANAGED_GUI_OPERATION_DENIED")
        if operation != "status" and not self._managed_authenticated:
            return
        if operation == "start":
            if self._managed_state not in ("stopped", "recovery-needed"):
                return
            self.status.setText("STARTING · requesting verified owned Core startup…")
        elif operation == "shutdown":
            if self._managed_state not in ("ready", "syncing", "busy"):
                return
            self.status.setText("Stopping verified Fusion-owned Core…")
        worker = _ManagedStatusWorker(self._managed_root, operation)
        self._worker = worker
        worker.ready.connect(self._apply_managed_status)
        worker.denied.connect(self._managed_denied)
        worker.finished.connect(self._worker_finished)
        worker.finished.connect(worker.deleteLater)
        self._update_controls()
        worker.start()

    def _inspect_crash_preview(self):
        # This action only creates a fixed, redacted report of ORIGINAL
        # sealed REGTEST wallet data. It cannot quarantine, sign or unlock.
        if (self._worker is not None or not self._managed_authenticated
                or self._managed_state!="ready"
                or self._wallet_core_dir is None or self._wallet_wsp_source is None
                or not (self._managed_root/"chain"/"wallet-vault").is_dir()):
            return
        password,ok=QInputDialog.getText(
            self,"K-09 · authenticated crash recovery inspection",
            "Original wallet passphrase · inspection ONLY (no file deletion)",
            QLineEdit.EchoMode.Password)
        if not ok:
            return
        secret=password.encode("utf-8")
        password=None
        if not 12<=len(secret)<=1024:
            self._crash_preview_denied("K09_GUI_PASSWORD_DENIED")
            return
        answer=QMessageBox.question(
            self,"K-09 · optional live REGTEST evidence",
            "Also inspect the latest 8 REGTEST blocks for on-chain spends? "
            "This cannot prove mempool safety or authorize quarantine.",
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No|
            QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.No)
        if answer==QMessageBox.StandardButton.Cancel:
            return
        observe=answer==QMessageBox.StandardButton.Yes
        self._wallet_checkpoint_verified=False
        self._wallet_read_authorized=False
        self._clear_balance()
        worker=_CrashPreviewWorker(
            self._managed_root,self._wallet_core_dir,self._wallet_wsp_source,
            secret,observe)
        secret=None
        self._worker=worker
        worker.ready.connect(self._apply_crash_preview)
        worker.denied.connect(self._crash_preview_denied)
        worker.finished.connect(self._worker_finished)
        worker.finished.connect(worker.deleteLater)
        self.status.setText("K-09 · inspecting locked original wallet; NO cleanup…")
        self._update_controls()
        worker.start()

    def _apply_crash_preview(self, evidence):
        required={
            "status":"K09_OWNER_VERIFIED_READ_ONLY_RESIDUE_PREVIEW",
            "network":"regtest",
            "original_anchor_verified":True,
            "original_owner_envelope_authenticated":True,
            "safe_to_discard_proven":False,
            "operator_discard_available":False,
            "wallet_unlocked":False,
            "signer_allowed":False,
            "broadcast_allowed":False,
            "automatic_cleanup_allowed":False,
        }
        fields=("candidate_count","stage_count","future_snapshot_count",
                "stage_content_authenticated_count",
                "stage_content_unverifiable_count",
                "future_snapshot_irreversible_delta_count",
                "stage_irreversible_delta_count")
        if (type(evidence) is not dict
                or any(evidence.get(k)!=v for k,v in required.items())
                or any(type(evidence.get(k)) is not int
                       or not 0<=evidence[k]<=32 for k in fields)):
            self._crash_preview_denied("K09_GUI_UNTRUSTED_EVIDENCE")
            return
        self._wallet_checkpoint_verified=False
        self._wallet_read_authorized=False
        self._clear_balance()
        counts=(
            f"Candidates: {evidence['candidate_count']}\n"
            f"Stage files: {evidence['stage_count']}\n"
            f"Future snapshots: {evidence['future_snapshot_count']}\n"
            f"Authenticated stage: {evidence['stage_content_authenticated_count']}\n"
            f"Unverifiable stage: {evidence['stage_content_unverifiable_count']}\n"
            f"Future irreversible deltas: {evidence['future_snapshot_irreversible_delta_count']}\n"
            f"Stage irreversible deltas: {evidence['stage_irreversible_delta_count']}"
        )
        observed=evidence.get("onchain_spent_outpoints_observed")
        if observed is not None:
            if type(observed) is not int or not 0<=observed<=2048:
                self._crash_preview_denied("K09_GUI_UNTRUSTED_CHAIN_EVIDENCE")
                return
            counts+=f"\nRecent on-chain spent outpoints: {observed}"
        QMessageBox.information(
            self,"K-09 · READ-ONLY recovery evidence",
            counts+"\n\nLOCKED · no cleanup, no signer, no broadcast. "
                   "Full reservation and mempool safety are NOT proven.")
        self.status.setText(
            "K-09 · redacted evidence inspected · wallet LOCKED / recovery PENDING")
        self._update_controls()

    def _crash_preview_denied(self,_reason):
        self._wallet_checkpoint_verified=False
        self._wallet_read_authorized=False
        self._clear_balance()
        self.status.setText(
            "K-09 · recovery evidence UNVERIFIED · wallet remains LOCKED")
        self._update_controls()

    def _verify_wallet(self):
        if (self._worker is not None or not self._managed_authenticated
                or self._managed_state!="ready"
                or self._wallet_core_dir is None or self._wallet_wsp_source is None):
            return
        password,ok=QInputDialog.getText(
            self,"Verify existing REGTEST wallet",
            "Wallet passphrase (checkpoint verification only; no unlock/signing)",
            QLineEdit.EchoMode.Password)
        if not ok:
            return
        secret=password.encode("utf-8")
        password=None
        if not 12<=len(secret)<=1024:
            self._wallet_preflight_denied("MANAGED_WALLET_PASSWORD_DENIED")
            return
        worker=_LockedWalletWorker(self._managed_root,self._wallet_core_dir,
                                   self._wallet_wsp_source,secret)
        secret=None
        self._wallet_checkpoint_verified=False
        self._worker=worker
        worker.ready.connect(self._apply_wallet_preflight)
        worker.denied.connect(self._wallet_preflight_denied)
        worker.finished.connect(self._worker_finished)
        worker.finished.connect(worker.deleteLater)
        self.status.setText("Checking original encrypted checkpoint and native anchor…")
        self._update_controls()
        worker.start()




    def _open_spending_wallet(self):
        if (self._worker is not None or self._spend_window is not None
                or not self._managed_authenticated or self._managed_state!="ready"
                or self._managed_height is None or self._wallet_core_dir is None
                or self._wallet_wsp_source is None
                or not (self._managed_root/"chain"/"wallet-vault").is_dir()):
            return
        consent=QMessageBox.question(
            self,"Open original WSP wallet for REGTEST spending",
            "Unlock original WSP keys for disposable REGTEST signing? "
            "Prepare, Sign and Broadcast each require separate exact-intent "
            "approval. No mainnet, external node or automatic retries.",
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if consent!=QMessageBox.StandardButton.Yes:return
        password,ok=QInputDialog.getText(
            self,"REGTEST original WSP wallet",
            "Original wallet passphrase · native anchor + Core must verify",
            QLineEdit.EchoMode.Password)
        if not ok:return
        secret=password.encode("utf-8")
        password=None
        if not 12<=len(secret)<=1024:
            self._wallet_snapshot_denied("MANAGED_SPEND_PASSWORD_DENIED")
            return
        self._wallet_checkpoint_verified=False
        self._wallet_read_authorized=False
        self._clear_balance()
        worker=_ManagedSpendSessionWorker(
            self._managed_root,self._wallet_core_dir,self._wallet_wsp_source,secret)
        secret=None
        self._worker=worker
        worker.ready.connect(self._apply_spending_session)
        worker.denied.connect(self._wallet_snapshot_denied)
        worker.finished.connect(self._worker_finished)
        worker.finished.connect(worker.deleteLater)
        self.status.setText("Verifying native original-wallet custody and WSP Core…")
        self._update_controls()
        worker.start()

    def _apply_spending_session(self,session):
        from .managed_spend_session import ManagedWalletSession
        if (type(session) is not ManagedWalletSession
                or not self._managed_authenticated or self._managed_state!="ready"
                or self._spend_window is not None or session.faulted or session.locked):
            try:session.close()
            except Exception:pass
            self._wallet_snapshot_denied("MANAGED_SPEND_SESSION_UNVERIFIED")
            return
        try:
            from .managed_operational_gui import ManagedOperationalWalletWindow
            window=ManagedOperationalWalletWindow(session)
            self._spend_window=window
            window.closed.connect(self._spend_window_closed)
            window.show()
            window.request_sync()
            self.status.setText(
                "REGTEST original WSP spending window open · "
                "exact-intent approvals required · no automatic broadcast")
            self._update_controls()
        except Exception:
            try:session.close()
            except Exception:pass
            self._spend_window=None
            self._wallet_snapshot_denied("MANAGED_SPEND_GUI_DENIED")

    def _spend_window_closed(self):
        self._spend_window=None
        self._wallet_checkpoint_verified=False
        self._wallet_read_authorized=False
        self._clear_balance()
        self.status.setText(
            "REGTEST managed WSP spending locked · rescan to verify original wallet")
        self._update_controls()

    def _inspect_core_sqlite(self,filename):
        if self._worker is not None or self._spend_window is not None:
            return
        from pathlib import Path
        try:
            if type(filename) is not str or not filename:
                raise ValueError
            source=Path(filename)
            if not source.is_absolute():
                raise ValueError
        except ValueError:
            self._core_sqlite_denied("K04_PICKER_PATH_DENIED")
            return
        worker=_CoreSqliteInspectionWorker(source)
        self._worker=worker
        worker.ready.connect(self._core_sqlite_inspected)
        worker.denied.connect(self._core_sqlite_denied)
        worker.finished.connect(self._worker_finished)
        worker.finished.connect(worker.deleteLater)
        self.status.setText(
            "Checking backup type only · BDB is unsupported · "
            "no Core wallet loaded or imported")
        self._update_controls()
        worker.start()

    def _choose_core_sqlite(self):
        if self._worker is not None or self._spend_window is not None:
            return
        name,_=QFileDialog.getOpenFileName(
            self,"Inspect Core-native SQLite backup · REGTEST quarantine ONLY",
            "","Core wallet (*.dat);;Fusion encrypted backup (*.enc);;"
            "Mnemonic text (NOT importable) (*.txt)")
        if name:self._inspect_core_sqlite(name)

    def dragEnterEvent(self,event):
        # Do not import any external data silently. One local .dat at a time.
        urls=event.mimeData().urls() if event.mimeData().hasUrls() else []
        if (len(urls)==1 and urls[0].isLocalFile()
                and urls[0].toLocalFile().lower().endswith((".dat",".enc",".txt"))
                and self._worker is None and self._spend_window is None):
            event.acceptProposedAction()
        else:event.ignore()

    def dropEvent(self,event):
        urls=event.mimeData().urls() if event.mimeData().hasUrls() else []
        if (len(urls)!=1 or not urls[0].isLocalFile()
                or not urls[0].toLocalFile().lower().endswith((".dat",".enc",".txt"))):
            event.ignore()
            return
        self._inspect_core_sqlite(urls[0].toLocalFile())
        event.acceptProposedAction()

    def _core_sqlite_inspected(self,receipt):
        expected={"format":"sqlite","network":"UNVERIFIED",
                  "restored":False,"wallet_signer_allowed":False,
                  "mainnet_allowed":False}
        if (type(receipt) is not dict or set(receipt)!=set(expected)|{"size"}
                or any(receipt.get(k)!=v or type(receipt[k]) is not type(v)
                       for k,v in expected.items())
                or type(receipt["size"]) is not int
                or not 4096<=receipt["size"]<=128*1024*1024):
            self._core_sqlite_denied("K04_INSPECTION_SHAPE_DENIED")
            return
        self.status.setText(
            "Core SQLite header verified · NETWORK/PROVENANCE UNKNOWN · "
            "NO IMPORT / NO RESTORE · signer disabled. "
            "Quarantine Core verification required before any wallet use.")

    def _core_sqlite_denied(self,_reason):
        # Fixed categories only; NEVER echo source filename, Core stderr,
        # descriptor bytes, mnemonic content or exception text.
        messages={
            "K05_BDB_DEPRECATED_UNSUPPORTED":
                "Fusion does NOT import or convert Berkeley DB (BDB) wallets. "
                "WAM Core v0.1.12 wamd/wam-cli on Windows x64 and macOS arm64 "
                "can migrate one using migratewallet; Linux x64 v0.1.12 "
                "node binaries cannot. Keep the original backup safe, "
                "verify the actual Core binary and seek expert guidance. "
                "NO AUTOMATIC IMPORT OR CONVERSION.",
            "K05_FUSION_ENCRYPTED_BACKUP_SEPARATE":
                "Fusion .enc encrypted checkpoint is NOT a Core wallet.dat · "
                "NO IMPORT. Use the original Fusion wallet recovery workflow.",
            "K05_MNEMONIC_TEXT_NOT_WALLET_DAT":
                "BIP39 mnemonic text is NOT a Core .dat or Fusion .enc · "
                "NO IMPORT. Never paste recovery words into Core file import.",
            "K05_UNKNOWN_CORE_DAT_DENIED":
                "Unknown .dat format · may be old BDB, corrupted or foreign · "
                "NO IMPORT / NO CONVERSION. Source preserved.",
            "K05_SQLITE_PRIVATE_CUSTODY_REQUIRED":
                "SQLite .dat inspection denied: file ownership or permissions "
                "are not private. Keep the original safe; use a trustworthy "
                "owner-only copy in a private directory (POSIX mode 0600) "
                "and retry. NO WALLET LOAD OR IMPORT.",
        }
        self.status.setText(messages.get(
            _reason,
            "Core wallet import DENIED · source unverified · "
            "no changes made to active WSP/Core wallet."))

    def _create_bip39_phrase(self):
        # Local CSPRNG wizard with explicit full-phrase confirmation; no
        # Core, RPC, wallet signer, checkpoint, anchor or file write.
        if self._worker is not None or self._spend_window is not None:
            return
        from .bip39_gui import Bip39CreationDialog
        dialog=Bip39CreationDialog(self)
        try:
            accepted=dialog.exec()
            if (accepted==Bip39CreationDialog.DialogCode.Accepted
                    and dialog.confirmed):
                self.status.setText(
                    "BIP39 phrase confirmed locally; NOT linked to the "
                    "existing Fusion WSP wallet. K-02/K-03 pending.")
        finally:
            dialog._clear_sensitive()
            dialog.deleteLater()
            self._update_controls()

    def _create_bip39_wallet(self):
        # This is *not* K-01's offline-only backup phrase action. New BIP39
        # wallet must be created through exactly the existing managed Core
        # native vault+anchor, with explicit original-wallet create-only gate.
        if (self._worker is not None or self._spend_window is not None
                or not self._managed_authenticated
                or self._managed_state!="ready"
                or self._managed_height is None or self._wallet_core_dir is None
                or self._wallet_wsp_source is None
                or (self._managed_root/"chain"/"wallet-vault").exists()):
            return
        approved=QMessageBox.question(
            self,"Create new BIP39 WSP wallet (REGTEST only)",
            "Create ONE NEW native-encrypted BIP39 WSP wallet on this "
            "verified Fusion-owned REGTEST Core? Existing legacy WSP wallets "
            "are never converted or overwritten. The 12/24 recovery words "
            "and optional BIP39 passphrase must be backed up offline. "
            "Signing requires a separate exact-intent approval.",
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if approved!=QMessageBox.StandardButton.Yes:return
        first,ok=QInputDialog.getText(
            self,"Encrypt new BIP39 WSP wallet",
            "New NATIVE vault encryption password (different from BIP39 passphrase)",
            QLineEdit.EchoMode.Password)
        if not ok:return
        second,ok=QInputDialog.getText(
            self,"Confirm native wallet encryption password",
            "Re-enter the EXACT native encryption password",
            QLineEdit.EchoMode.Password)
        if not ok:return
        secret=first.encode("utf8")
        matching=(first==second)
        first=second=None
        if not matching or not 12<=len(secret)<=1024:
            self._wallet_snapshot_denied("MANAGED_WALLET_CREATE_PASSWORD_MISMATCH")
            return
        from .bip39_gui import Bip39CreationDialog
        dialog=Bip39CreationDialog(self,create_wallet=True)
        mnemonic=passphrase=None
        try:
            confirmed=dialog.exec()
            if (confirmed!=Bip39CreationDialog.DialogCode.Accepted
                    or not dialog.confirmed):
                return
            mnemonic,passphrase=dialog.take_wallet_material()
        finally:
            dialog._clear_sensitive()
            dialog.deleteLater()
        self._wallet_read_authorized=False
        self._wallet_checkpoint_verified=False
        self._clear_balance()
        worker=_ManagedWalletCreateWorker(
            self._managed_root,self._wallet_core_dir,self._wallet_wsp_source,
            secret,bip39_phrase=mnemonic,bip39_passphrase=passphrase)
        secret=mnemonic=passphrase=None
        self._worker=worker
        worker.ready.connect(self._apply_wallet_created)
        worker.denied.connect(self._wallet_snapshot_denied)
        worker.finished.connect(self._worker_finished)
        worker.finished.connect(worker.deleteLater)
        self.status.setText(
            "Creating NEW BIP39 WSP wallet · encrypted native checkpoint · REGTEST")
        self._update_controls()
        worker.start()

    def _create_wallet(self):
        if (self._worker is not None or not self._managed_authenticated
                or self._managed_state!="ready" or self._managed_height is None
                or self._wallet_core_dir is None or self._wallet_wsp_source is None
                or (self._managed_root/"chain"/"wallet-vault").exists()):
            return
        answer=QMessageBox.question(
            self,"Create original REGTEST WSP wallet",
            "Create one new encrypted WSP wallet attached to this Fusion-owned "
            "REGTEST Core? Existing wallets will never be replaced. "
            "This legacy WSP 32-byte seed is NOT BIP39 and CANNOT be restored "
            "using the separate BIP39 backup-words wizard. "
            "This action does not enable signing or mainnet.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer!=QMessageBox.StandardButton.Yes:
            return
        first,ok=QInputDialog.getText(
            self,"New REGTEST WSP wallet",
            "New encryption passphrase (12–1024 UTF-8 bytes)",
            QLineEdit.EchoMode.Password)
        if not ok:return
        second,ok=QInputDialog.getText(
            self,"Confirm new REGTEST wallet",
            "Re-enter the exact encryption passphrase",
            QLineEdit.EchoMode.Password)
        if not ok:return
        secret=first.encode("utf-8")
        matching=(first==second)
        first=second=None
        if not matching or not 12<=len(secret)<=1024:
            self._wallet_snapshot_denied("MANAGED_WALLET_CREATE_PASSWORD_MISMATCH")
            return
        self._wallet_read_authorized=False
        self._wallet_checkpoint_verified=False
        self._clear_balance()
        worker=_ManagedWalletCreateWorker(
            self._managed_root,self._wallet_core_dir,self._wallet_wsp_source,secret)
        secret=None
        self._worker=worker
        worker.ready.connect(self._apply_wallet_created)
        worker.denied.connect(self._wallet_snapshot_denied)
        worker.finished.connect(self._worker_finished)
        worker.finished.connect(worker.deleteLater)
        self.status.setText("Creating native-encrypted REGTEST WSP wallet…")
        self._update_controls()
        worker.start()

    def _apply_wallet_created(self,proof):
        expected={"status":"MANAGED_REGTEST_WSP_WALLET_CREATED_LOCKED",
                  "network":"regtest","wallet_locked":True,
                  "signer_allowed":False,"broadcast_allowed":False,
                  "mainnet_allowed":False}
        if (type(proof) is not dict or proof!=expected
                or not self._managed_authenticated or self._managed_state!="ready"):
            self._wallet_snapshot_denied("MANAGED_WALLET_CREATION_NOT_VERIFIED")
            return
        self._wallet_read_authorized=False
        self._wallet_checkpoint_verified=False
        self._clear_balance()
        self.status.setText(
            "REGTEST · ORIGINAL WSP WALLET CREATED AND ENCRYPTED · "
            "use Sync and save to display your verified receive address · no signing")
        self._update_controls()

    def _view_wallet(self, *, persist_checkpoint=False):
        if (self._worker is not None or not self._managed_authenticated
                or self._managed_state!="ready" or self._managed_height is None
                or self._wallet_core_dir is None or self._wallet_wsp_source is None
                or type(persist_checkpoint) is not bool):
            return
        password,approved=QInputDialog.getText(
            self,"Sync original REGTEST wallet",
            ("Passphrase · live WSP scan and SAVE encrypted checkpoint"
             if persist_checkpoint else
             "Passphrase · view live REGTEST wallet without checkpoint write"),
            QLineEdit.EchoMode.Password)
        if not approved:
            return
        secret=password.encode("utf-8")
        password=None
        if not 12<=len(secret)<=1024:
            self._wallet_snapshot_denied("MANAGED_WALLET_PASSWORD_DENIED")
            return
        self._wallet_checkpoint_verified=False
        self._wallet_read_authorized=True
        self._clear_balance()
        worker=_ManagedWalletSnapshotWorker(
            self._managed_root,self._wallet_core_dir,self._wallet_wsp_source,
            secret,persist_checkpoint=persist_checkpoint)
        secret=None
        self._worker=worker
        worker.ready.connect(self._apply_wallet_snapshot)
        worker.denied.connect(self._wallet_snapshot_denied)
        worker.finished.connect(self._worker_finished)
        worker.finished.connect(worker.deleteLater)
        self.status.setText(
            "REGTEST · syncing WSP and sealing native checkpoint…"
            if persist_checkpoint else
            "REGTEST · reading original WSP wallet against live Core…")
        self._update_controls()
        worker.start()

    def _apply_wallet_snapshot(self, snap):
        from .wallet_read import WalletReadSnapshot,HistoryRow
        # Managed original-wallet snapshots must not weaken the separate
        # legacy demo-only window's input policy.
        verified=(
            self._wallet_read_authorized
            and self._managed_authenticated and self._managed_state=="ready"
            and type(self._managed_height) is int
            and type(snap) is WalletReadSnapshot
            and snap.chain=="regtest" and snap.height==self._managed_height
            and type(snap.tip) is str and re.fullmatch(r"[0-9a-f]{64}",snap.tip)
            and type(snap.core_sha256) is str
            and re.fullmatch(r"[0-9a-f]{64}",snap.core_sha256)
            and type(snap.receive_code) is str
            and snap.receive_code.startswith("wamrtsp1")
            and 10<=len(snap.receive_code)<=256
            and type(snap.confirmed_atoms) is int and snap.confirmed_atoms>=0
            and type(snap.confirmed_utxos) is int and 0<=snap.confirmed_utxos<=1_000_000
            and type(snap.history) is tuple
            and all(type(item) is HistoryRow for item in snap.history)
            and snap.demo_account_only is False and snap.synthetic_rpc is False
            and snap.signer_allowed is False and snap.broadcast_allowed is False
            and snap.mainnet_allowed is False
        )
        self._wallet_read_authorized=False
        if not verified:
            self._wallet_snapshot_denied("MANAGED_WALLET_UNTRUSTED_SNAPSHOT")
            return
        try:
            self.receive_page.render_snapshot(snap)
            self.history_page.render_snapshot(snap)
            self.dashboard.render_snapshot(snap,operational=False)
        except Exception:
            self._wallet_snapshot_denied("MANAGED_WALLET_UNTRUSTED_RENDER")
            return
        self._snapshot=snap
        self._wallet_checkpoint_verified=True
        self.dashboard.go_send.setEnabled(False)
        self.verification_badge.setText("WSP read-only · "+str(snap.height))
        self.status.setText(
            "REGTEST · ORIGINAL WSP WALLET VERIFIED · height "+
            str(snap.height)+" · signing/broadcast DISABLED · refresh re-authenticates")
        self.snapshot_updated.emit(snap)
        # Auto-clear by the next authenticated status cycle; no cached
        # passphrase, unverified background rescan or indefinite stale balance.
        self._sync_timer.setInterval(30_000)
        self._update_controls()

    def _wallet_snapshot_denied(self, _reason):
        self._wallet_read_authorized=False
        self._wallet_checkpoint_verified=False
        self._clear_balance()
        self._sync_timer.setInterval(5_000)
        self.status.setText(
            "REGTEST · ORIGINAL WALLET READ UNVERIFIED · no balance/history adopted")
        self.snapshot_failed.emit("MANAGED_WALLET_SNAPSHOT_UNVERIFIED")
        self._update_controls()

    def apply_snapshot(self, snap):
        # In particular, never adopt old public-demo snapshots on managed GUI.
        self._wallet_snapshot_denied("MANAGED_GUI_DEMO_SNAPSHOT_DENIED")

    def _apply_wallet_preflight(self, proof):
        required={
            "status":"MANAGED_WALLET_ORIGINAL_CHECKPOINT_VERIFIED_LOCKED",
            "network":"regtest","wallet_locked":True,
            "signer_allowed":False,"broadcast_allowed":False,
            "balance_verified":False,"original_native_anchor_verified":True,
            "original_encrypted_checkpoint_verified":True,
            "mainnet_allowed":False,"supervisor_authenticated":True,
            "supervisor_core_identity_verified":True,
        }
        if (type(proof) is not dict or proof!=required
                or not self._managed_authenticated or self._managed_state!="ready"):
            self._wallet_preflight_denied("MANAGED_WALLET_CHECKPOINT_UNVERIFIED")
            return
        self._wallet_checkpoint_verified=True
        self._clear_balance()
        self.status.setText(
            "REGTEST · ORIGINAL CHECKPOINT VERIFIED · WALLET STILL LOCKED · "
            "Balance/history/signing NOT verified · no broadcast")
        self._update_controls()

    def _wallet_preflight_denied(self, _reason):
        self._wallet_checkpoint_verified=False
        self._clear_balance()
        self.status.setText(
            "REGTEST · WALLET CHECKPOINT UNVERIFIED · no signer/balance adoption")
        self._update_controls()

    def request_sync(self):
        self._execute("status")

    def _confirm_stop(self):
        if self._managed_state not in ("ready", "syncing", "busy"):
            return
        answer = QMessageBox.question(
            self, "Stop managed REGTEST Core",
            "Stop only the verified Fusion-owned REGTEST Core?\n"
            "Blockchain datadir will be preserved; unrelated Core/miners will not be stopped.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._execute("shutdown")

    def _apply_managed_status(self, status):
        # Double-check caller-supplied state without accepting inferred,
        # fabricated or wrong-chain status, even in UI signal delivery.
        try:
            if type(status) is not dict:
                raise ValueError
            expected = public_status(state=status["state"],
                chain_height=status["height"], owned=status["core_process_owned"])
            if status != expected:
                raise ValueError
            state = expected["state"]
            if state in ("ready", "syncing", "busy") and not expected["core_process_owned"]:
                raise ValueError
            if state == "ready" and expected["height"] is None:
                raise ValueError
        except (ValueError, KeyError, TypeError):
            self._managed_denied("MANAGED_GUI_INVALID_STATUS")
            return
        self._managed_state = state
        self._managed_authenticated = True
        self._managed_height=expected["height"] if state=="ready" else None
        self._wallet_read_authorized=False
        self._wallet_checkpoint_verified=False
        # Back pressure on the GUI's periodic status polling: after the
        # supervisor reports a genuine busy RPC queue, do not re-poll every
        # five seconds. Manual refresh still requires a free GUI worker.
        self._sync_timer.setInterval(15_000 if state=="busy" else 5_000)
        # A supervisor attestation is NOT a scanner/history attestation.
        self._clear_balance()
        height = expected["height"]
        label = VISIBLE_STATES[state]
        self.verification_badge.setText("Managed Core · " + label)
        self.status.setText(
            "REGTEST · " + label +
            (" · height " + str(height) if height is not None else "") +
            " · WSP wallet locked/unverified · no automatic broadcast"
        )
        self._update_controls()

    def _managed_denied(self, _reason):
        self._managed_state = "error"
        self._managed_authenticated = False
        self._managed_height=None
        self._wallet_read_authorized=False
        self._sync_timer.setInterval(5_000)
        self._wallet_checkpoint_verified=False
        self._clear_balance()
        self.verification_badge.setText("Managed Core · UNVERIFIED")
        self.status.setText(
            "RECOVERY NEEDED · authenticated supervisor unavailable; "
            "no data or wallet state adopted"
        )
        self._update_controls()

    def _worker_finished(self):
        super()._worker_finished()
        self._update_controls()

    def closeEvent(self, event):
        # A GUI close cannot leave an unlocked separate spending window
        # unowned. Require explicit closing/locking of that window first.
        if self._spend_window is not None:
            event.ignore()
            self.status.setText(
                "Close and lock the REGTEST spending window before exiting Fusion")
            return
        super().closeEvent(event)


def launch_managed_gui(root: Path, *, core_dir=None, wsp_source=None) -> int:
    from .supervisor_store import _root
    _root(root)
    app = qt_application()
    window = ManagedCoreWindow(root,core_dir=core_dir,wsp_source=wsp_source)
    window.show()
    QTimer.singleShot(0, window.request_sync)
    return app.exec()
