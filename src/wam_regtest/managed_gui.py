"""T05 Fusion GUI for the *owned* persistent REGTEST Core supervisor.

This is the actual Fusion Qt shell, not a synthetic console/status mock.
Only the independently authenticated supervisor's status is displayed.
No WSP wallet is created, adopted, unlocked, signed or broadcast here.
Q05 wallet continuity is a separate, still mandatory integration gate.
"""
from __future__ import annotations

from pathlib import Path
import re

from PySide6.QtCore import QThread, Signal, QTimer
from PySide6.QtWidgets import QMessageBox, QInputDialog, QLineEdit

from .desktop import RegtestWalletWindow, qt_application
from .fusion_ui import action
from .supervisor_client import control
from .supervisor_protocol import public_status

VISIBLE_STATES = {
    "stopped": "STOPPED",
    "starting": "STARTING",
    "syncing": "SYNCING",
    "busy": "BUSY · retry later",
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

    def __init__(self,root,core_dir,wsp_source,password):
        super().__init__()
        self.root,self.core_dir,self.wsp_source=root,core_dir,wsp_source
        self.password=password

    def run(self):
        try:
            from .managed_wallet_create import create_managed_wallet
            value=create_managed_wallet(
                self.root,self.core_dir,self.wsp_source,self.password,
                authorized=True)
            self.ready.emit(value)
        except Exception:
            self.denied.emit("MANAGED_WALLET_CREATE_UNVERIFIED")
        finally:
            self.password=None


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
        self.view_wallet_button=action("View verified wallet · read only", "sync")
        toolbar.addWidget(self.view_wallet_button)
        self.view_wallet_button.clicked.connect(
            lambda: self._view_wallet(persist_checkpoint=False))
        self.sync_wallet_button=action("Sync + save encrypted checkpoint", "sync")
        toolbar.addWidget(self.sync_wallet_button)
        self.sync_wallet_button.clicked.connect(
            lambda: self._view_wallet(persist_checkpoint=True))
        self.create_wallet_button=action("Create REGTEST WSP wallet", "security")
        toolbar.addWidget(self.create_wallet_button)
        self.create_wallet_button.clicked.connect(self._create_wallet)
        self.start_core.clicked.connect(lambda: self._execute("start"))
        self.stop_core.clicked.connect(self._confirm_stop)
        # A short timer makes transitions visible without polling from Qt's
        # UI thread or creating an unbounded Core RPC request queue.
        self._sync_timer.setInterval(5_000)
        self._update_controls()

    def _update_controls(self):
        if not hasattr(self, "start_core"):
            return
        idle = self._worker is None
        self.start_core.setEnabled(
            idle and self._managed_authenticated and
            self._managed_state in ("stopped", "recovery-needed")
        )
        self.stop_core.setEnabled(
            idle and self._managed_authenticated and
            self._managed_state in ("ready", "syncing", "busy")
        )
        self.refresh_button.setEnabled(idle)
        can_read=(idle and self._managed_authenticated
                  and self._managed_state=="ready" and self._managed_height is not None
                  and self._wallet_core_dir is not None
                  and self._wallet_wsp_source is not None)
        self.verify_wallet_button.setEnabled(can_read)
        self.view_wallet_button.setEnabled(can_read)
        self.sync_wallet_button.setEnabled(can_read)
        self.create_wallet_button.setEnabled(
            can_read and not (self._managed_root/"chain"/"wallet-vault").exists())

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
        self._sync_timer.setInterval(5_000)
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
        # RegtestWalletWindow prevents deleting in-flight QThreads. It never
        # sends Core stop on window close. Our managed subclass preserves that.
        super().closeEvent(event)


def launch_managed_gui(root: Path, *, core_dir=None, wsp_source=None) -> int:
    from .supervisor_store import _root
    _root(root)
    app = qt_application()
    window = ManagedCoreWindow(root,core_dir=core_dir,wsp_source=wsp_source)
    window.show()
    QTimer.singleShot(0, window.request_sync)
    return app.exec()
