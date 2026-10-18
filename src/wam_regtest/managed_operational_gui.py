"""Native Fusion Send UI on the original, encrypted REGTEST WSP wallet.

Reuse the existing exact-intent/PSBTv2 modal approval UI and WalletSession
state machine. No private-key or transaction construction ever occurs in Core
supervisor. Unlike disposable developer-mode, managed mode may not mine,
replace native backup identity or connect to any foreign Core.
"""
from PySide6.QtCore import Signal
from .operational_gui import OperationalWalletWindow
from .managed_spend_session import ManagedWalletSession


class ManagedOperationalWalletWindow(OperationalWalletWindow):
    closed=Signal()

    def __init__(self,session):
        if type(session) is not ManagedWalletSession:
            raise ValueError("MANAGED_OPERATIONAL_SESSION_REQUIRED")
        super().__init__(session)
        self.setWindowTitle("WAM Fusion · Original WSP REGTEST Wallet")
        self.warning.setText(
            "REGTEST ONLY · ORIGINAL ENCRYPTED WSP WALLET · "
            "EXPLICIT SIGN + BROADCAST CONSENT")
        self.navigation.item(6).setHidden(True)
        self.mine_button.setVisible(False)
        self.recover_button.setVisible(False)
        self._update_controls()

    def _update_controls(self):
        super()._update_controls()
        if hasattr(self,"mine_button"):
            self.mine_button.setEnabled(False)
            self.recover_button.setEnabled(False)

    def closeEvent(self,event):
        super().closeEvent(event)
        if event.isAccepted():
            self.closed.emit()
