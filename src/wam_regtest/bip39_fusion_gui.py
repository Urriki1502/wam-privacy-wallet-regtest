"""Q06 presentation inside the EXISTING Fusion visual system.

No new wallet manager or signing authority: this is a Qt skin for the
unchanged Bip39TrialWindow/WalletExecutor and its fail-closed native custody.
The reusable Q05 Fusion Overview/Receive/History/PaymentSteps are real widgets,
not a painted mockup or a separate demo account.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QFrame, QLabel, QLineEdit,
    QListWidget, QStackedWidget, QComboBox, QMessageBox, QDialog,
)

from .bip39_owner_gui import Bip39TrialWindow
from .desktop import resolve_theme
from .fusion_ui import (
    FusionOverview, fusion_stylesheet, fusion_palette, page, panel,
    label, ResponsiveRow,
)
from .fusion_pages import ReceivePage, HistoryPage, PaymentSteps, PaymentApproval
from .wallet_read import WalletReadSnapshot
from .amounts import parse_amount, _parse_atoms


class Bip39FusionWindow(Bip39TrialWindow):
    """The normal BIP39 UI uses the same Fusion navigation, theme and pages.

    The legacy Q06 controls remain bound to the SAME executor. The old
    developer-only layout is parked, its already connected controls are moved
    into the correct Fusion pages. No second Qt worker or owner is started.
    """

    def __init__(self, executor):
        super().__init__(executor)
        legacy = QWidget()
        legacy.setLayout(self.layout())
        self._legacy_layout_holder = legacy
        legacy.hide()
        self.setObjectName("WalletRoot")
        self.setWindowTitle("WAM Fusion · BIP39 REGTEST")
        self.resize(1220, 790)
        self.setMinimumSize(870, 610)
        shell = QHBoxLayout(self)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("FusionSidebar")
        sidebar.setFixedWidth(214)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18, 26, 18, 20)
        side.setSpacing(18)
        side.addWidget(label("WAM FUSION", "BrandTitle"))
        side.addWidget(label("BIP39 · REGTEST", "FusionBadge"))
        side.addWidget(label("WALLET WORKSPACE", "FusionKicker"))
        self.navigation = QListWidget()
        self.navigation.addItems(("Overview", "Receive", "History", "Send", "Security", "Advanced"))
        side.addWidget(self.navigation, 1)
        side.addWidget(label("Disposable REGTEST only\\nNo real funds or mainnet.", "FusionGold"))
        shell.addWidget(sidebar)

        main = QWidget()
        main.setObjectName("FusionTransparent")
        content = QVBoxLayout(main)
        content.setContentsMargins(24, 16, 24, 15)
        content.setSpacing(12)
        top = QHBoxLayout()
        self.page_title = label("Overview", "FusionCardTitle")
        top.addWidget(self.page_title)
        top.addStretch()
        self.theme_select = QComboBox()
        self.theme_select.addItems(("Auto", "Signature Dark", "Signature Light"))
        self.theme_select.currentIndexChanged.connect(self._apply_fusion_theme)
        top.addWidget(self.theme_select)
        top.addWidget(self.sync)
        content.addLayout(top)

        self.stack = QStackedWidget()
        content.addWidget(self.stack, 1)
        shell.addWidget(main, 1)
        content.addWidget(self.status)

        self.overview = FusionOverview()
        self.stack.addWidget(self.overview)
        self.receive_page = ReceivePage()
        self.stack.addWidget(self.receive_page)
        self.history_page = HistoryPage()
        self.stack.addWidget(self.history_page)

        send_page, send_layout = page(
            "Send a silent payment",
            "Review an exact REGTEST transfer; signing and broadcast have separate consent.",
            "TRANSACTIONS / SEND",
        )
        self.payment_steps = PaymentSteps()
        send_layout.addWidget(self.payment_steps)
        form, fl = panel("Payment details", "BIP352 · owned Core · native checkpoint")
        self.recipient_input = QLineEdit()
        self.recipient_input.setMaxLength(256)
        self.recipient_input.setPlaceholderText("wamrtsp1… full recipient code")
        self.amount_input = QLineEdit()
        self.amount_input.setMaxLength(32)
        self.amount_input.setPlaceholderText("0.00000000")
        self.fee_input = QLineEdit("0.00010000")
        self.fee_input.setMaxLength(32)
        fl.addWidget(label("RECIPIENT / BIP352", "FusionKicker"))
        fl.addWidget(self.recipient_input)
        amounts = QHBoxLayout()
        for name, widget in (("AMOUNT / WAM", self.amount_input),
                             ("FEE / WAM", self.fee_input)):
            group = QVBoxLayout()
            group.addWidget(label(name, "FusionKicker"))
            group.addWidget(widget)
            amounts.addLayout(group, 1)
        fl.addLayout(amounts)
        self.send.setText("Review payment")
        fl.addWidget(self.send)
        review, rl = panel(
            "Transaction approval",
            "Review → Sign reserves inputs; Broadcast requires separate approval.",
        )
        rl.addWidget(self.activate)
        rl.addWidget(self.broadcast)
        rl.addWidget(self.cancel)
        rl.addWidget(label("Unknown broadcast status never triggers an automatic retry.", "FusionGold"))
        send_layout.addWidget(ResponsiveRow(form, review, weights=[3, 2]))
        send_layout.addStretch()
        self.stack.addWidget(send_page)

        security_page, security_layout = page(
            "Wallet security",
            "12-word encrypted seed, native custody and conservative recovery.",
            "CUSTODY / SECURITY",
        )
        wallet_card, wl = panel("Encrypted BIP39 wallet", "Original owned REGTEST Core")
        self.security_state = label("Locked / awaiting verified wallet", "FusionCardValue")
        wl.addWidget(self.security_state)
        wl.addWidget(self.lock)
        wl.addWidget(label(
            "12 words are shown only at creation; never send seed words to a support agent."
        ))
        recovery_card, rl = panel(
            "Independent recovery",
            "Read-only re-scan on THIS original blockchain; new empty chain has no past transactions.",
        )
        rl.addWidget(self.recovery)
        rl.addWidget(label(
            "Signed and uncertain native reservations are never imported or discarded.",
            "FusionGold",
        ))
        security_layout.addWidget(ResponsiveRow(wallet_card, recovery_card))
        security_layout.addStretch()
        self.stack.addWidget(security_page)

        advanced, al = page(
            "Developer / REGTEST tools",
            "Explicit test-only block generation and native-Core inspection.",
            "ADVANCED / VERIFIED CORE",
        )
        controls, cl = panel("REGTEST chain", "Funding and mining mutate this disposable test chain.")
        cl.addWidget(self.fund)
        cl.addWidget(self.confirm)
        cl.addWidget(self.inspect)
        advanced.addWidget(controls)
        details, dl = panel("Original session / TXID", "Read-only technical identifiers.")
        dl.addWidget(self.account)
        dl.addWidget(self.balance)
        dl.addWidget(self.tip)
        dl.addWidget(label("Last broadcast TXID (copy before closing)", "FusionKicker"))
        dl.addWidget(self.last_txid)
        details_row = ResponsiveRow(details)
        advanced.addWidget(details_row)
        advanced.addWidget(self.quit)
        advanced.addStretch()
        self.stack.addWidget(advanced)

        self.navigation.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.navigation.currentRowChanged.connect(
            lambda i: self.page_title.setText(
                ("Overview", "Receive", "History", "Send", "Security", "Advanced")[i]
                if 0 <= i < 6 else "WAM Fusion"
            )
        )
        self.navigation.setCurrentRow(0)
        self.overview.go_receive.clicked.connect(
            lambda: self.navigation.setCurrentRow(1))
        self.overview.go_send.clicked.connect(
            lambda: self.navigation.setCurrentRow(3))
        self.overview.open_history.clicked.connect(
            lambda: self.navigation.setCurrentRow(2))
        self.overview.open_security.clicked.connect(
            lambda: self.navigation.setCurrentRow(4))
        self.overview.manual_sync.clicked.connect(
            lambda: self._command("snapshot"))
        self.overview.transaction_selected.connect(self._select_transaction)
        self._last_verified = None
        self._last_review = None
        self._apply_fusion_theme()
        self._set_actions()

    def _apply_fusion_theme(self, *_):
        from datetime import datetime
        choice = self.theme_select.currentIndex()
        # User-selected Dark/Light must override the system clock.
        mode = (resolve_theme("auto", datetime.now().astimezone())
                if choice == 0 else "dark" if choice == 1 else "light")
        self.setStyleSheet(fusion_stylesheet(mode))
        self.overview.set_theme(mode)
        self.history_page.set_theme(mode)

    def _select_transaction(self, txid):
        self.navigation.setCurrentRow(2)
        self.history_page.select_txid(txid)

    def _set_actions(self):
        super()._set_actions()
        if hasattr(self, "overview"):
            ready = self._ready and not self.executor.state.faulted
            idle = self._worker is None and not self.executor.busy
            self.overview.go_send.setEnabled(ready and idle and self._spend_enabled)
            self.overview.open_security.setEnabled(not self._quit_requested)
            if hasattr(self, "security_state"):
                self.security_state.setText(
                    "Faulted · original reservations preserved"
                    if self.executor.state.faulted else
                    "Verified native custody · Send enabled" if self._spend_enabled else
                    "Seed open · Send awaits checkpoint" if self._ready else
                    "Locked / awaiting verified wallet"
                )
            if hasattr(self, "payment_steps"):
                self.payment_steps.set_stage(
                    3 if self._signed_ready else
                    2 if self._approved_commitment is not None else 0
                )

    def _prepare_send(self):
        if (not self._spend_enabled or self._approved_commitment is not None
                or self.executor.state.faulted or self.executor.busy):
            return
        try:
            atoms = parse_amount(self.amount_input.text())
            fee = _parse_atoms(self.fee_input.text(), 1, 1_000_000)
            code = self.recipient_input.text().strip()
            if not code.startswith("wamrtsp1") or len(code) > 256:
                raise ValueError("Q06_FUSION_RECIPIENT_DENIED")
        except (ValueError, ArithmeticError):
            QMessageBox.warning(
                self, "Invalid REGTEST payment",
                "Enter a full wamrtsp1 recipient and valid WAM amount/fee."
            )
            return
        self._command("prepare", code, atoms, fee)

    def _confirm_broadcast(self):
        if (not self._signed_ready or self._approved_commitment is None
                or self._last_review is None or self.executor.state.faulted
                or self.executor.busy or self._quit_requested):
            return
        review = self._last_review
        if review.commitment != self._approved_commitment:
            return
        dialog = PaymentApproval(review, "broadcast", self)
        try:
            accepted = dialog.exec() == QDialog.DialogCode.Accepted
        finally:
            dialog.deleteLater()
        if accepted and review.commitment == self._approved_commitment:
            self._command("broadcast", review.commitment)

    def _render_verified(self, result):
        snap = result.get("fusion_snapshot")
        if (type(snap) is not WalletReadSnapshot
                or snap.chain != "regtest"
                or snap.synthetic_rpc or snap.mainnet_allowed
                or snap.receive_code != result.get("receive_code")
                or snap.confirmed_atoms != result.get("confirmed_atoms")
                or snap.signer_allowed is not result.get("signer_allowed")
                or snap.broadcast_allowed is not result.get("broadcast_allowed")
                or self.executor.state.faulted):
            self._clear_visuals()
            self.status.setText("Q06_FUSION_VERIFIED_SNAPSHOT_DENIED")
            return
        try:
            self.overview.render_snapshot(snap, operational=True)
            self.receive_page.render_snapshot(snap)
            self.history_page.render_snapshot(snap)
        except (ValueError, TypeError):
            self._clear_visuals()
            self.status.setText("Q06_FUSION_PRESENTATION_DENIED")
            return
        self._last_verified = snap
        self.overview.go_send.setEnabled(self._spend_enabled and
                                         not self.executor.state.faulted)

    def _clear_visuals(self):
        self._last_verified = None
        self.overview.render_snapshot(None, locked=True)
        self.receive_page.render_snapshot(None)
        self.history_page.render_snapshot(None)

    def _on_ready(self, action, result):
        if action == "prepare":
            # Existing Q05 Fusion exact-transaction approval, not the old
            # developer QMessageBox. Signing still requires explicit consent
            # and retains its native-anchored irreversible reservation.
            self._approved_commitment = result.commitment
            self._last_review = result
            self._signed_ready = False
            dialog = PaymentApproval(result, "sign", self)
            try:
                accepted = dialog.exec() == QDialog.DialogCode.Accepted
            finally:
                dialog.deleteLater()
            self._pending_action = (
                ("sign", result.commitment) if accepted else ("cancel",)
            )
            self.status.setText(
                "Transaction approved; signing owned REGTEST inputs"
                if accepted else "Transaction not approved; canceling unsigned draft"
            )
            self._set_actions()
            return
        super()._on_ready(action, result)
        if action in ("cancel", "broadcast", "lock", "quit"):
            self._last_review = None
        if action in ("snapshot", "activate"):
            self._render_verified(result)
        elif action == "open":
            self._clear_visuals()
            # Same owner, bounded read-only chain sync after seed confirmation.
            self._pending_action = ("snapshot",)
        elif action == "mine":
            self._pending_action = ("snapshot",)
        elif action in ("lock", "quit"):
            self._clear_visuals()
        self._set_actions()

    def _on_denied(self, code):
        super()._on_denied(code)
        if self.executor.state.faulted:
            self._clear_visuals()
        elif self._last_verified is not None:
            self.overview.live_badge.setText("Last verified · refresh required")
        self._set_actions()
