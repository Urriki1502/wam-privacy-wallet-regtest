"""Q06 presentation inside the EXISTING Fusion visual system.

No new wallet manager or signing authority: this is a Qt skin for the
unchanged Bip39TrialWindow/WalletExecutor and its fail-closed native custody.
The reusable Q05 Fusion Overview/Receive/History/PaymentSteps are real widgets,
not a painted mockup or a separate demo account.
"""
import os
import re
from PySide6.QtCore import Qt, QSize, QEasingCurve, QPropertyAnimation
from PySide6.QtGui import QFontDatabase, QIcon, QPixmap
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QFrame, QLabel, QLineEdit,
    QListWidget, QStackedWidget, QMessageBox, QDialog, QToolButton,
    QButtonGroup, QGraphicsOpacityEffect, QCheckBox, QApplication, QSizePolicy,
)

from .bip39_owner_gui import Bip39TrialWindow
from .bip39_locale import t
from .desktop import resolve_theme
from .gui_errors import operation_error
from .fusion_ui import (
    FusionOverview, fusion_stylesheet, fusion_palette, page, panel,
    label, ResponsiveRow, vector_icon, fusion_nav_icons,
    StateSwitch,
)
from .fusion_pages import ReceivePage, HistoryPage, PaymentSteps, PaymentApproval, WalletConsent
from .bip39_backup_page import Bip39BackupPage
from .wallet_read import WalletReadSnapshot
from .amounts import parse_amount, _parse_atoms
from .branding import brand_image


class _WrappingStatusLabel(QLabel):
    def setText(self, text):
        # QLabel WordWrap does not break long identifiers. Optional line breaks
        # affect presentation only; retain the exact message in the tooltip.
        self.setToolTip(text)
        super().setText(re.sub(r"\S{33,}", lambda match: "\u200b".join(
            match[0][i:i + 24] for i in range(0, len(match[0]), 24)), text))


class _AdvancedControlsToggle(QToolButton):
    def minimumSizeHint(self):
        # Keep the native styled text + padding, including font/DPI changes.
        return self.sizeHint()

    def _sync_minimum(self):
        self.setMinimumSize(self.sizeHint())
        self.updateGeometry()

    def setText(self, text):
        super().setText(text)
        self._sync_minimum()

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_minimum()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (event.Type.FontChange, event.Type.StyleChange):
            self._sync_minimum()


class Bip39FusionWindow(Bip39TrialWindow):
    """The normal BIP39 UI uses the same Fusion navigation, theme and pages.

    The legacy Q06 controls remain bound to the SAME executor. The old
    developer-only layout is parked, its already connected controls are moved
    into the correct Fusion pages. No second Qt worker or owner is started.
    """

    def __init__(self, executor, *, shared_profile=None):
        self.shared_profile = shared_profile
        self._shared_connected = False
        super().__init__(executor)
        legacy = QWidget(self)
        legacy.setLayout(self.layout())
        self._legacy_layout_holder = legacy
        legacy.hide()
        self.setObjectName("WalletRoot")
        self.setWindowTitle("WAM Fusion · Privacy Wallet")
        self.setWindowIcon(QIcon(str(brand_image())))
        self.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont))
        self.resize(1260, 810)
        self.setMinimumSize(900, 630)
        shell = QHBoxLayout(self)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        # Native macOS-style workspace, not a second wallet manager.
        sidebar = QFrame()
        sidebar.setObjectName("FusionSidebar")
        sidebar.setFixedWidth(226)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18, 28, 18, 22)
        side.setSpacing(16)
        brand = QHBoxLayout()
        brand.setSpacing(10)
        logo = QLabel()
        mark = QPixmap(str(brand_image())).scaled(
            42, 42, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation)
        logo.setPixmap(mark)
        logo.setFixedSize(44, 44)
        brand.addWidget(logo)
        name = QVBoxLayout()
        name.setSpacing(0)
        name.addWidget(label("WAM Fusion", "BrandTitle"))
        name.addWidget(label("PRIVATE WALLET", "FusionKicker"))
        brand.addLayout(name, 1)
        side.addLayout(brand)
        side.addSpacing(24)
        side.addWidget(label("WORKSPACE", "FusionKicker"))
        self.navigation = QListWidget()
        self.navigation.setIconSize(QSize(20, 20))
        self.navigation.setSpacing(3)
        self.navigation.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.navigation.setAccessibleName("WAM Fusion wallet navigation")
        self.navigation.addItems(
            ("Overview", "Receive", "History", "Send", "Security", "Settings"))
        side.addWidget(self.navigation, 1)
        side.addWidget(label("SHARED REGTEST" if shared_profile else "REGTEST PREVIEW", "FusionBadge"))
        notice = label('REGTEST only.\nNo real funds or mainnet keys.', 'FusionMuted')
        notice.setMinimumWidth(0)
        side.addWidget(notice)
        shell.addWidget(sidebar)

        main = QWidget()
        main.setObjectName("FusionTransparent")
        content = QVBoxLayout(main)
        content.setContentsMargins(34, 19, 30, 17)
        content.setSpacing(17)

        topbar = QFrame()
        topbar.setObjectName("FusionTopbar")
        top = QHBoxLayout(topbar)
        top.setContentsMargins(0, 0, 0, 18)
        top.setSpacing(12)
        self.page_title = label("Overview", "PageTitle")
        top.addWidget(self.page_title)
        top.addStretch()
        self.connection_pill = label("AWAITING VERIFICATION", "FusionBadge")
        top.addWidget(self.connection_pill)
        self.sync.setText("Refresh")
        self.sync.setObjectName("FusionSecondary")
        self.sync.setToolTip("Verify the latest state with your owned WAM Core")
        self.sync.setAccessibleName("Refresh verified blockchain state")
        top.addWidget(self.sync)
        content.addWidget(topbar)

        self.stack = QStackedWidget()
        content.addWidget(self.stack, 1)
        original_status = self.status
        self.status = _WrappingStatusLabel()
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setText(original_status.text())
        original_status.deleteLater()
        self.status.setObjectName("FusionMuted")
        self.status.setWordWrap(True)
        self.status.setMinimumWidth(0)
        status_policy = self.status.sizePolicy()
        status_policy.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
        status_policy.setVerticalPolicy(QSizePolicy.Policy.Minimum)
        status_policy.setHeightForWidth(True)
        self.status.setSizePolicy(status_policy)
        content.addWidget(self.status)
        shell.addWidget(main, 1)
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
        self.send.setObjectName("FusionPrimary")
        self.send.setProperty("fusion_icon", "send")
        fl.addWidget(self.send)
        review, rl = panel(
            "Transaction approval",
            "Review → Sign reserves inputs; Broadcast requires separate approval.",
        )
        self.activate.setText("Enable sending")
        self.activate.setObjectName("FusionSecondary")
        self.activate.setProperty("fusion_icon", "security")
        self.broadcast.setText("Approve broadcast")
        self.broadcast.setObjectName("FusionSecondary")
        self.broadcast.setProperty("fusion_icon", "send")
        self.cancel.setText("Cancel unsigned draft")
        self.cancel.setObjectName("FusionSecondary")
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
        self.lock.setText("Lock wallet")
        self.lock.setObjectName("FusionSecondary")
        self.lock.setProperty("fusion_icon", "lock")
        self.lock.hide()
        self.unlock.setText("Unlock wallet")
        self.unlock.setObjectName("FusionSecondary")
        self.unlock.hide()
        self.custody_switch = StateSwitch('Locked')
        self.custody_switch.setAccessibleName('Wallet Lock / Unlock switch')
        self.custody_switch.setToolTip('Unlock requires the original wallet password and verified custody.')
        self.custody_switch.clicked.connect(self._switch_custody)
        wl.addWidget(self.custody_switch)
        # The base developer layout parks lock/unlock/quit in a utility bar;
        # the normal Fusion workspace owns the Security-page placement instead.
        self._legacy_layout_holder.layout().removeWidget(self.unlock)
        self.quit.setText("Stop owned Core and quit")
        self.quit.setObjectName("FusionDestructive")
        wl.addWidget(self.quit)
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

        settings_page, settings_layout = page(
            "Settings",
            "A quieter workspace, tailored to your desktop.",
            "YOUR WALLET / PREFERENCES",
        )
        appearance, appearance_layout = panel(
            "Appearance",
            "Auto follows your Mac's appearance schedule. Choose a fixed theme if preferred.")
        self.appearance_group = QButtonGroup(self)
        self.appearance_group.setExclusive(True)
        self.appearance_buttons = []
        segments = QFrame()
        segments.setObjectName("FusionSegmented")
        segment_layout = QHBoxLayout(segments)
        segment_layout.setContentsMargins(4, 4, 4, 4)
        segment_layout.setSpacing(4)
        for n, title in enumerate(("Automatic", "Light", "Dark")):
            button = QToolButton()
            button.setObjectName("FusionSegment")
            button.setText(title)
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.appearance_group.addButton(button, n)
            self.appearance_buttons.append(button)
            segment_layout.addWidget(button, 1)
        self.appearance_buttons[0].setChecked(True)
        self.appearance_group.idClicked.connect(self._apply_fusion_theme)
        appearance_layout.addWidget(segments)
        self.reduce_motion = QCheckBox("Reduce interface motion")
        self.reduce_motion.setChecked(os.environ.get("QT_REDUCE_MOTION") == "1")
        appearance_layout.addWidget(self.reduce_motion)
        settings_layout.addWidget(appearance)

        about, about_layout = panel(
            "WAM Fusion · REGTEST",
            "Local-first BIP352 silent payments. No remote account or cloud custody.")
        about_layout.addWidget(label("WAM Core v0.1.11 · WSP-1 · BIP39 12 words"))
        about_layout.addWidget(label(
            "This preview is not a mainnet wallet. All test transactions stay on the owned REGTEST chain."))
        settings_layout.addWidget(about)
        if shared_profile is not None:
            from .fusion_ui import action
            network, net_layout = panel('Shared REGTEST',
                'Manual Core P2P · local RPC only · '+('mining coordinator' if shared_profile.coordinator else 'participant; mining disabled'))
            self.network_state = label('Peer not verified. Refresh network before mining or sending.', 'FusionMuted')
            net_layout.addWidget(self.network_state)
            self.reconcile_button=action('Reconcile retained shared-chain state','security')
            self.reconcile_button.clicked.connect(self._reconcile_shared)
            net_layout.addWidget(self.reconcile_button)
            self._last_reconciliation=None
            for title,command in (('Verify peer and chain',('network_status',)),
                                  ('Disconnect Core P2P',('network_active',False)),
                                  ('Reconnect Core P2P',('network_active',True))):
                button = action(title,'sync')
                button.clicked.connect(lambda _checked=False,command=command:self._command(*command))
                net_layout.addWidget(button)
            settings_layout.addWidget(network)

        advanced_card, advanced_layout = panel(
            "Advanced controls",
            "For technical acceptance and test-chain diagnostics only.")
        self.advanced_toggle = _AdvancedControlsToggle()
        self.advanced_toggle.setObjectName("FusionAdvanced")
        self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.setText("Show developer controls  ▾")
        self.advanced_toggle.setAccessibleName("Expand REGTEST developer controls")
        self.advanced_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        # Native macOS minimumSizeHint omits part of the stylesheet padding.
        # Minimum vertical policy keeps the complete styled sizeHint at any DPI.
        self.advanced_toggle.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Minimum)
        advanced_layout.addWidget(self.advanced_toggle)
        self.advanced_container = QWidget()
        self.advanced_container.setObjectName("FusionTransparent")
        advanced_body = QVBoxLayout(self.advanced_container)
        advanced_body.setContentsMargins(0, 6, 0, 0)
        advanced_body.setSpacing(13)
        advanced_body.addWidget(label(
            "Test-only funding and confirmation change this isolated blockchain.",
            "FusionGold"))
        advanced_body.addWidget(self.fund)
        advanced_body.addWidget(self.confirm)
        advanced_body.addWidget(self.inspect)
        advanced_body.addWidget(label("OWNED CORE / SESSION", "FusionKicker"))
        advanced_body.addWidget(self.account)
        advanced_body.addWidget(self.balance)
        advanced_body.addWidget(self.tip)
        for text in (self.account, self.balance, self.tip):
            text.setWordWrap(True)
            text.setMinimumWidth(0)
            policy = text.sizePolicy()
            policy.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
            policy.setVerticalPolicy(QSizePolicy.Policy.Minimum)
            policy.setHeightForWidth(True)
            text.setSizePolicy(policy)
        advanced_body.addWidget(label("LAST BROADCAST TRANSACTION", "FusionKicker"))
        advanced_body.addWidget(self.last_txid)
        advanced_layout.addWidget(self.advanced_container)
        self.advanced_container.hide()
        self.advanced_toggle.toggled.connect(self._toggle_advanced)
        settings_layout.addWidget(advanced_card)
        settings_layout.addStretch()
        self.stack.addWidget(settings_page)

        self.backup_page = Bip39BackupPage()
        self.backup_page.verify_requested.connect(self._on_backup_verify)
        self.backup_page.deferred_requested.connect(self._on_backup_deferred)
        self.backup_page.continue_requested.connect(self._on_backup_continue)
        self.stack.addWidget(self.backup_page)

        self._transition = None
        self._advanced_transition = None
        self.navigation.currentRowChanged.connect(self._navigate)
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
        if hasattr(QApplication.styleHints(), "colorSchemeChanged"):
            QApplication.styleHints().colorSchemeChanged.connect(
                self._native_theme_changed)
        self._set_actions()

    def _native_theme_changed(self, *_):
        if self.appearance_group.checkedId() == 0:
            self._apply_fusion_theme()

    def _apply_fusion_theme(self, *_):
        from datetime import datetime
        selection = self.appearance_group.checkedId()
        if selection == 0:
            # Match macOS System Appearance, not an assumed day/night hour.
            scheme = QApplication.styleHints().colorScheme()
            mode = ("dark" if scheme == Qt.ColorScheme.Dark else
                    "light" if scheme == Qt.ColorScheme.Light else
                    resolve_theme("auto", datetime.now().astimezone()))
        else:
            mode = "light" if selection == 1 else "dark"
        colors = fusion_palette(mode)
        self.setStyleSheet(fusion_stylesheet(mode))
        self.overview.set_theme(mode)
        self.history_page.set_theme(mode)
        for item, icon in zip(
                (self.navigation.item(i) for i in range(self.navigation.count())),
                fusion_nav_icons(colors["accent"])):
            item.setIcon(icon)
        for button in self.findChildren(__import__(
                "PySide6.QtWidgets", fromlist=["QPushButton"]).QPushButton):
            icon = button.property("fusion_icon")
            if icon:
                tone = colors["onaccent"] if button.objectName() == "FusionPrimary" else colors["accent"]
                button.setIcon(vector_icon(icon, tone, max(1, self.devicePixelRatioF())))
        self.sync.setIcon(vector_icon("sync", colors["accent"], max(1, self.devicePixelRatioF())))

    def _navigate(self, index):
        if not 0 <= index < 6:
            return
        self.page_title.setText(
            ("Overview", "Receive", "History", "Send", "Security", "Settings")[index])
        self.stack.setCurrentIndex(index)
        if (self.reduce_motion.isChecked()
                or os.environ.get("GITHUB_ACTIONS") == "true"):
            return
        # Short, non-blocking, presentation-only transition. Never run Core
        # operations or change wallet state in the animation callback.
        if self._transition is not None:
            self._transition.stop()
        for page_index in range(self.stack.count()):
            widget = self.stack.widget(page_index)
            if widget.graphicsEffect() is not None:
                widget.setGraphicsEffect(None)
        current = self.stack.currentWidget()
        effect = QGraphicsOpacityEffect(current)
        current.setGraphicsEffect(effect)
        effect.setOpacity(0.82)
        self._transition = QPropertyAnimation(effect, b"opacity", self)
        self._transition.setDuration(150)
        self._transition.setStartValue(0.82)
        self._transition.setEndValue(1.0)
        self._transition.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._transition.finished.connect(
            lambda widget=current: widget.setGraphicsEffect(None))
        self._transition.start()

    def _toggle_advanced(self, expanded):
        self.advanced_toggle.setText(
            "Hide developer controls  ▴" if expanded
            else "Show developer controls  ▾")
        self.advanced_container.setVisible(expanded)
        if (not expanded or self.reduce_motion.isChecked()
                or os.environ.get("GITHUB_ACTIONS") == "true"):
            return
        effect = QGraphicsOpacityEffect(self.advanced_container)
        self.advanced_container.setGraphicsEffect(effect)
        self._advanced_transition = QPropertyAnimation(effect, b"opacity", self)
        self._advanced_transition.setDuration(170)
        self._advanced_transition.setStartValue(0.5)
        self._advanced_transition.setEndValue(1.0)
        self._advanced_transition.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._advanced_transition.start()

    def _select_transaction(self, txid):
        self.navigation.setCurrentRow(2)
        self.history_page.select_txid(txid)

    def _set_actions(self):
        super()._set_actions()
        if getattr(self,'shared_profile',None) is not None:
            if not self.shared_profile.coordinator:
                self.fund.setEnabled(False)
                self.confirm.setEnabled(False)
            if not self._shared_connected:
                for control in (self.fund,self.confirm,self.send,self.broadcast):
                    control.setEnabled(False)
        if hasattr(self, "overview"):
            ready = self._ready and not self.executor.state.faulted
            idle = (self._worker is None and not self.executor.busy
                    and not self._delivering_result)
            if hasattr(self,'reconcile_button'):
                self.reconcile_button.setEnabled(idle and not self._quit_requested and self.executor.state.core_alive is True)
            if hasattr(self, 'custody_switch'):
                unlocked = not self.executor.state.locked and self._ready
                self.custody_switch.setChecked(unlocked)
                self.custody_switch.setText('Unlocked' if unlocked else 'Locked')
                self.custody_switch.setEnabled(idle and not self._quit_requested
                    and (self.lock.isEnabled() or self.unlock.isEnabled()))
            self.overview.go_send.setEnabled(ready and idle and self._spend_enabled
                and (self.shared_profile is None or self._shared_connected))
            self.overview.open_security.setEnabled(not self._quit_requested)
            if hasattr(self, "security_state"):
                self.security_state.setText(
                    "Faulted · original reservations preserved"
                    if self.executor.state.faulted else
                    "Custody verified · peer disconnected · payment state preserved"
                    if self.shared_profile is not None and self._spend_enabled and not self._shared_connected else
                    "Verified native custody · Send enabled" if self._spend_enabled else
                    "Seed open · Send awaits checkpoint" if self._ready else
                    "Locked · use Unlock wallet to reauthenticate this original REGTEST wallet"
                )
            if hasattr(self, "payment_steps"):
                self.payment_steps.set_stage(
                    3 if self._signed_ready else
                    2 if self._approved_commitment is not None else 0
                )

    def _present_backup_ack(self, result):
        self.navigation.setEnabled(False)
        self.page_title.setText('Wallet backup')
        self.connection_pill.setText(t("regtest_preview"))
        if result.get("backup_status") == "required" and result.get("mnemonic_once"):
            self.backup_page.set_phrase(result["mnemonic_once"].split())
        else:
            self.backup_page.set_deferred_mode()
        self.stack.setCurrentWidget(self.backup_page)

    def _switch_custody(self, checked):
        # Reflect only authenticated backend state, never the optimistic click.
        self._set_actions()
        if checked:
            self._unlock_prompt()
        else:
            self._command('lock')

    def _passphrase(self, message):
        dialog = WalletConsent('Unlock original wallet', message, self, password=True)
        try:
            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.password_input.text():
                return dialog.password_input.text().encode('utf-8')
            return None
        finally:
            dialog.password_input.clear()
            dialog.deleteLater()

    def _confirm_activation(self):
        if not self._ready or self._spend_enabled or self.executor.busy:
            return
        dialog = WalletConsent('Enable REGTEST sending',
            'Verify this original Core, native custody and anchored checkpoint before enabling '
            'signing. Signed and uncertain inputs stay reserved. Each payment still needs '
            'separate Sign and Broadcast approval.', self)
        try:
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self._command('activate')
        finally:
            dialog.deleteLater()

    def _reconcile_shared(self):
        if self.shared_profile is None or self.executor.busy or self._worker is not None or self._delivering_result:
            return
        dialog=WalletConsent('Reconcile original Shared REGTEST wallet',
            'Authenticate this original profile and reconstruct observation from its latest native checkpoint. '
            'A competing branch requires greater verified Core work. Signed/unknown reservations and old '
            'runtime evidence stay retained. No payment is retried. Sending requires a separate approval afterwards.',
            self,password=True,accept_text='Reconcile')
        try:
            if dialog.exec()==QDialog.DialogCode.Accepted:
                self._command('reconcile_reorg',dialog.password_input.text().encode('utf-8'))
        finally:
            dialog.password_input.clear();dialog.deleteLater()

    def _confirm_one_block(self):
        txid = self._pending_confirm_txid
        if not self._spend_enabled or txid is None:
            return
        dialog = WalletConsent('Confirm this REGTEST payment',
            'Mine exactly one test block on this original owned Core to confirm '
            'the submitted transaction. An uncertain outcome must not be retried.', self)
        try:
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self._command('confirm', txid)
        finally:
            dialog.deleteLater()

    def _confirm_funding(self):
        if not self._ready or self._spend_enabled or self._test_funded:
            return
        dialog = WalletConsent('Fund disposable REGTEST wallet',
            'On a fresh isolated test chain only: mine mature public fixture funds, '
            'receive one BIP352 payment and confirm it. This changes the test chain. '
            'Never retry an uncertain result.', self)
        try:
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self._command('mine')
        finally:
            dialog.deleteLater()

    def _on_backup_verify(self, positions, answers):
        try:
            ok = self.executor.request("backup_verify", positions, answers, timeout=30)
        except Exception as error:
            self.status.setText(
                "Backup verification unavailable: " + str(operation_error("backup_verify", error)))
            self.backup_page.show_verification_error()
            return
        if ok:
            self.backup_page.show_success()
        else:
            self.backup_page.show_verification_error()

    def _on_backup_deferred(self):
        try:
            self.executor.request("backup_defer", timeout=30)
        except Exception as error:
            self.status.setText(
                "Backup deferral unavailable: " + str(operation_error("backup_defer", error)))
        self._backup_flow_completed(False)

    def _on_backup_continue(self):
        self._backup_flow_completed(True)

    def _backup_flow_completed(self, success):
        self.navigation.setEnabled(True)
        self.stack.setCurrentIndex(0)
        self.navigation.setCurrentRow(0)
        self.page_title.setText("Overview")
        if success:
            self.connection_pill.setText("AWAITING VERIFICATION")
        super()._backup_flow_completed(success)

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
            self.status.setText('Enter a complete REGTEST silent-payment recipient and valid amount/fee.')
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
        self.connection_pill.setText("●  VERIFIED REGTEST")
        self.overview.go_send.setEnabled(self._spend_enabled and
                                         not self.executor.state.faulted)

    def _clear_visuals(self):
        self._last_verified = None
        self.connection_pill.setText("●  NOT VERIFIED")
        self.overview.render_snapshot(None, locked=True)
        self.receive_page.render_snapshot(None)
        self.history_page.render_snapshot(None)

    def _on_ready(self, action, result):
        if action=='reconcile_reorg':
            self._last_reconciliation=result['reconciliation']
            self._spend_enabled=self._signed_ready=False
            self._approved_commitment=self._pending_confirm_txid=None
            self._last_review=None
            self._clear_visuals()
            super()._on_ready('open',result)
            self.status.setText('Original Shared profile reconciled. Evidence and reservations retained. Approve Enable sending to verify custody again.')
            self._set_actions()
            return
        if isinstance(result,dict) and 'shared_network' in result:
            self._shared_connected = result['shared_network']['connected']
        if action in ('network_status','network_active'):
            self._shared_connected = result['connected']
            self.network_state.setText(('Connected' if result['connected'] else 'Disconnected')
                +f" · {result['peer_count']} peer(s) · height {result['height']}\nTip: {result['tip']}")
            self.status.setText('Shared chain verified; refresh wallet to reconcile history.'
                                if result['connected'] else 'Peer disconnected. Signed and pending payments remain preserved.')
            self._set_actions()
            return
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
            # Same owner, bounded read-only chain sync only after the explicit
            # backup acknowledgement; a refused create above stops with lock.
            if (not self._backup_flow_active and not self._backup_unacked
                    and not result.get('checkpoint_present')):
                self._pending_action = ("snapshot",)
        elif action == "mine":
            self._pending_action = ("snapshot",)
        elif action in ("lock", "quit"):
            self._clear_visuals()
        elif action == 'unlock':
            self._clear_visuals()
            if result.get('fusion_snapshot') is not None:
                self._render_verified(result)
        self._set_actions()

    def _on_denied(self, code):
        super()._on_denied(code)
        if code == 'SHARED_CONFIRMED_PEER_REQUIRED':
            self._shared_connected=False
            self.status.setText('Peer disconnected. Reconnect and verify the chain; signed and pending payments remain preserved.')
            self._set_actions()
        if self.executor.state.faulted:
            self._clear_visuals()
            self.connection_pill.setText("●  CORE ERROR")
        elif self._last_verified is not None:
            self.overview.live_badge.setText("Last verified · refresh required")
        self._set_actions()
