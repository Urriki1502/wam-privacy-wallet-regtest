"""Q06 presentation inside the EXISTING Fusion visual system.

No new wallet manager or signing authority: this is a Qt skin for the
unchanged Bip39TrialWindow/WalletExecutor and its fail-closed native custody.
The reusable Q05 Fusion Overview/Receive/History/PaymentSteps are real widgets,
not a painted mockup or a separate demo account.
"""
import os
import re
from PySide6.QtCore import Qt, QSize, QSettings, QTimer
from PySide6.QtGui import QFontDatabase, QIcon, QPixmap
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QFrame, QLabel, QLineEdit,
    QListWidget, QMessageBox, QDialog, QToolButton,
    QCheckBox, QApplication, QSizePolicy,
)

from .bip39_owner_gui import Bip39TrialWindow
from .bip39_locale import t
from .desktop import resolve_theme
from .gui_errors import operation_error
from .fusion_ui import (
    FusionOverview, fusion_stylesheet, fusion_palette, page, panel,
    label, ResponsiveRow, vector_icon, nav_icon_for, FUSION_NAV_PAGES,
    StateSwitch, action, ThemeSlider,
)
from .fusion_motion import fade_widget, PressFeedback, TransitionHost, STAGGER_MS, STANDARD_MS, motion_reduced
from .fusion_status import classify
from .fusion_pages import ReceivePage, HistoryPage, PaymentSteps, PaymentApproval, WalletConsent, NetworkPage, describe_broadcast_result
from .bip39_backup_page import Bip39BackupPage
from .wallet_read import WalletReadSnapshot, format_wam
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
        self.setWindowTitle("WAM Fusion Wallet — REGTEST" + (" (V1-NET)" if shared_profile else ""))
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
        sidebar.setFixedWidth(232)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18, 24, 18, 18)
        side.setSpacing(14)
        brand = QVBoxLayout()
        brand.setSpacing(8)
        logo = QLabel()
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark = QPixmap(str(brand_image())).scaled(
            58, 58, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation)
        logo.setPixmap(mark)
        logo.setFixedHeight(62)
        brand.addWidget(logo)
        title = label("WAM Fusion Wallet", "BrandTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.addWidget(title)
        side.addLayout(brand)
        side.addWidget(label("SHARED REGTEST" if shared_profile else "REGTEST", "FusionBadge"),
                       0, Qt.AlignmentFlag.AlignHCenter)
        self.navigation = QListWidget()
        self.navigation.setIconSize(QSize(18, 18))
        self.navigation.setSpacing(2)
        self.navigation.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.navigation.setAccessibleName("WAM Fusion wallet navigation")
        self.navigation.addItems(tuple(title for title, _icon in FUSION_NAV_PAGES))
        side.addWidget(self.navigation, 1)
        notice = label('WAM Fusion  ·  Qt  ·  WAM Core (REGTEST)\nNo real funds or mainnet keys.', 'FusionMuted')
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
        self.page_title.hide()
        top.addWidget(self.page_title)
        top.addStretch()
        self.connection_pill = label("Snapshot not verified", "FusionBadge")
        top.addWidget(self.connection_pill)
        self.sync.setText("Refresh")
        self.sync.setObjectName("FusionSecondary")
        self.sync.setToolTip("Verify the latest state with your owned WAM Core")
        self.sync.setAccessibleName("Refresh verified blockchain state")
        top.addWidget(self.sync)
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setFixedWidth(1)
        divider.setStyleSheet("color: palette(mid);")
        top.addWidget(divider)
        top.addWidget(label("Theme", "FusionMuted"))
        self.header_theme = ThemeSlider(compact=True)
        self.header_theme.setAccessibleName("Compact appearance selector")
        top.addWidget(self.header_theme)
        content.addWidget(topbar)

        self.stack = TransitionHost()
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
            "Send",
            "Prepare, review, approve signature and broadcast as separate actions.",
            "TRANSACTIONS / SEND",
        )
        self.payment_steps = PaymentSteps()
        send_layout.addWidget(self.payment_steps)
        form, fl = panel("Prepare payment", "BIP352 · owned Core · native checkpoint")
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
            "Review, sign and broadcast",
            "Signing reserves inputs. Broadcast is a separate explicit approval.",
        )
        self.review_summary = label("No prepared payment. Recipient, amount, fee and change appear here after Review.")
        self.review_summary.setMinimumWidth(0)
        rl.addWidget(self.review_summary)
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
        self.send_result = label("No broadcast result yet. An uncertain outcome is never hidden or retried.")
        self.send_result.setMinimumWidth(0)
        rl.addWidget(self.send_result)
        rl.addWidget(label("Unknown broadcast status never triggers an automatic retry.", "FusionGold"))
        send_layout.addWidget(ResponsiveRow(form, review, weights=[3, 2]))
        send_layout.addStretch()
        self.stack.addWidget(send_page)

        security_page, security_layout = page(
            "Security",
            "Wallet protection, backup status and advanced custody controls stay separate.",
            "CUSTODY / SECURITY",
        )
        wallet_card, wl = panel("Wallet protection", "Lock and unlock reflect authenticated backend custody only.")
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
        backup_card, bl = panel("Backup status", "12-word creation and three-word verification remain required.")
        bl.addWidget(label("Recovery words are shown only at creation. Never send them to a support agent."))
        self.backup_review = action('Review backup requirements', 'backup')
        self.backup_review.setAccessibleName('Review backup requirements')
        self.backup_review.clicked.connect(self._quick_backup)
        bl.addWidget(self.backup_review)
        security_layout.addWidget(ResponsiveRow(wallet_card, recovery_card))
        security_layout.addWidget(backup_card)
        security_layout.addStretch()
        self.stack.addWidget(security_page)

        self.network_page = NetworkPage()
        self.stack.addWidget(self.network_page)

        settings_page, settings_layout = page(
            "Settings",
            "Appearance, ordinary preferences and separate developer diagnostics.",
            "YOUR WALLET / PREFERENCES",
        )
        appearance, appearance_layout = panel(
            "Appearance",
            "Automatic follows macOS appearance. Light and Dark apply immediately.")
        self.settings_theme = ThemeSlider(compact=False)
        appearance_layout.addWidget(self.settings_theme, 0, Qt.AlignmentFlag.AlignLeft)
        self.appearance_group = self.header_theme.group
        self.appearance_buttons = self.header_theme.buttons
        self.reduce_motion = QCheckBox("Reduce interface motion")
        stored = QSettings("WAM Privacy Wallet", "REGTEST")
        self.reduce_motion.setChecked(
            os.environ.get("QT_REDUCE_MOTION") == "1"
            or stored.value("fusion_reduce_motion", False, type=bool))
        self.reduce_motion.toggled.connect(self._set_reduce_motion)
        appearance_layout.addWidget(self.reduce_motion)
        settings_layout.addWidget(appearance)

        about, about_layout = panel(
            "WAM Fusion · REGTEST",
            "Local-first BIP352 silent payments. No remote account or cloud custody.")
        about_layout.addWidget(label("WAM Core v0.1.11 · WSP-1 · BIP39 12 words"))
        about_layout.addWidget(label(
            "This preview is not a mainnet wallet. All test transactions stay on the owned REGTEST chain."))
        settings_layout.addWidget(about)
        self.network_state = self.network_page.connection_value
        if shared_profile is not None:
            self.reconcile_button = action('Reconcile retained shared-chain state', 'security')
            self.reconcile_button.clicked.connect(self._reconcile_shared)
            self.network_page.controls_host.addWidget(self.reconcile_button)
            self._last_reconciliation = None
            for title, command in (('Verify peer and chain', ('network_status',)),
                                   ('Disconnect Core P2P', ('network_active', False)),
                                   ('Reconnect Core P2P', ('network_active', True))):
                button = action(title, 'sync')
                button.clicked.connect(lambda _checked=False, command=command: self._command(*command))
                self.network_page.controls_host.addWidget(button)

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
        self._press_feedback = PressFeedback(self)
        self._theme_sync = False
        self.header_theme.currentChanged.connect(self._theme_chosen)
        self.settings_theme.currentChanged.connect(self._theme_chosen)
        saved = QSettings("WAM Privacy Wallet", "REGTEST").value("fusion_appearance", 0, type=int)
        if saved in (0, 1, 2):
            self.header_theme.setCurrentIndex(saved, animate=False)
            self.settings_theme.setCurrentIndex(saved, animate=False)
        self._set_reduce_motion(self.reduce_motion.isChecked())
        self._overview_intro = False
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
        self.overview.custody_switch.clicked.connect(self._switch_custody)
        self._last_verified = None
        self._last_review = None
        self._last_network = None
        self._broadcast_complete = False
        self._apply_fusion_theme()
        self._press_feedback.attach(self)
        self.overview.render_snapshot(
            None, locked=True, network=self._network_view(None),
            faulted=self.executor.state.faulted,
            core_alive=self.executor.state.core_alive)
        if hasattr(QApplication.styleHints(), "colorSchemeChanged"):
            QApplication.styleHints().colorSchemeChanged.connect(
                self._native_theme_changed)
        self._set_actions()

    def _set_reduce_motion(self, checked):
        self.setProperty("fusion_reduce_motion", bool(checked))
        QSettings("WAM Privacy Wallet", "REGTEST").setValue("fusion_reduce_motion", bool(checked))
        self.style().unpolish(self)
        self.style().polish(self)

    def _theme_chosen(self, index):
        if index not in (0, 1, 2) or self._theme_sync:
            return
        self._theme_sync = True
        try:
            for slider in (self.header_theme, self.settings_theme):
                if slider.currentIndex() != index:
                    slider.setCurrentIndex(index, animate=slider is not self.sender())
            QSettings("WAM Privacy Wallet", "REGTEST").setValue("fusion_appearance", index)
            self._apply_fusion_theme()
        finally:
            self._theme_sync = False

    def _native_theme_changed(self, *_):
        if self.header_theme.currentIndex() == 0:
            self._apply_fusion_theme()

    def _apply_fusion_theme(self, *_):
        from datetime import datetime
        selection = self.header_theme.currentIndex()
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
        selected = self.navigation.currentRow()
        for index in range(self.navigation.count()):
            item = self.navigation.item(index)
            tone = colors["onaccent"] if index == selected else colors["muted"]
            item.setIcon(nav_icon_for(item.text(), tone, max(1, self.devicePixelRatioF())))
        for button in self.findChildren(__import__(
                "PySide6.QtWidgets", fromlist=["QPushButton"]).QPushButton):
            icon = button.property("fusion_icon")
            if icon:
                tone = colors["onaccent"] if button.objectName() == "FusionPrimary" else colors["accent"]
                button.setIcon(vector_icon(icon, tone, max(1, self.devicePixelRatioF())))
        from PySide6.QtWidgets import QToolButton, QLabel
        dpr = max(1, self.devicePixelRatioF())
        for button in self.findChildren(QToolButton):
            icon = button.property("fusion_icon")
            if icon:
                on_thumb = (button.objectName() == "FusionSegment" and button.isChecked())
                button.setIcon(vector_icon(
                    icon, colors["onaccent"] if on_thumb else colors["accent"], dpr))
        for icon_label in self.findChildren(QLabel):
            name = icon_label.property("fusion_icon_label")
            if name:
                icon_label.setPixmap(vector_icon(name, colors["accent"], max(1, self.devicePixelRatioF())).pixmap(24, 24))
        self.sync.setIcon(vector_icon("sync", colors["accent"], max(1, self.devicePixelRatioF())))
        self.custody_switch.setProperty("fusion_mode", mode)
        self.overview.custody_switch.setProperty("fusion_mode", mode)
        self.custody_switch.update()
        self.overview.custody_switch.update()

    def _navigate(self, index):
        if not 0 <= index < len(FUSION_NAV_PAGES):
            return
        self.page_title.setText(FUSION_NAV_PAGES[index][0])
        reduced = self.reduce_motion.isChecked() or motion_reduced(self)
        self.stack.set_current(index, reduced=reduced)
        self._apply_fusion_theme()
        if index == 0:
            self._play_overview_intro()

    def _toggle_advanced(self, expanded):
        self.advanced_toggle.setText(
            "Hide developer controls  ▴" if expanded
            else "Show developer controls  ▾")
        self.advanced_container.setVisible(expanded)
        if not expanded:
            return
        self._advanced_transition = fade_widget(
            self.advanced_container, start=0.5, end=1.0, duration=180, parent=self)

    def _quick_backup(self):
        dialog = WalletConsent(
            'Backup this REGTEST wallet',
            'Recovery words are shown only at wallet creation. This action does not '
            'display the seed. Use Verify Recovery to check words you already wrote down.',
            self, accept_text='Verify recovery words')
        try:
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.recovery.click()
        finally:
            dialog.deleteLater()

    def _play_overview_intro(self):
        if getattr(self, '_overview_intro', False) or motion_reduced(self) or self.reduce_motion.isChecked():
            return
        self._overview_intro = True
        groups = (
            self.overview.hero,
            self.overview.status_board,
            self.overview.activity_panel,
        )
        for delay, widget in enumerate(groups):
            QTimer.singleShot(
                STAGGER_MS * delay,
                lambda widget=widget: fade_widget(
                    widget, start=0.35, end=1.0, duration=STANDARD_MS, parent=self))

    def _select_transaction(self, txid):
        self.navigation.setCurrentRow(2)
        self.history_page.select_txid(txid)

    def _network_view(self, snap):
        shared = self.shared_profile is not None
        view = {
            'shared': shared,
            'mode': 'Shared REGTEST' if shared else 'Isolated REGTEST',
        }
        net = getattr(self, '_last_network', None)
        if isinstance(net, dict):
            if type(net.get('peer_count')) is int:
                view['peer_count'] = net['peer_count']
            if 'connected' in net:
                view['connected'] = net['connected']
        lines = [view['mode']]
        if 'peer_count' in view:
            lines.append(str(view['peer_count']) + ' peer(s)')
        elif not shared:
            lines.append('Zero-peer isolated profile')
        if snap is not None:
            lines.append('Height ' + str(snap.height))
        view['summary'] = '\n'.join(lines)
        return view

    def _render_network(self, snap=None):
        net = getattr(self, '_last_network', None) or {}
        snap = self._last_verified if snap is None and hasattr(self, '_last_verified') else snap
        self.network_page.render(
            shared=self.shared_profile is not None,
            connected=net.get('connected') if isinstance(net, dict) else None,
            peer_count=net.get('peer_count') if isinstance(net, dict) else None,
            height=(snap.height if snap is not None else
                    (net.get('height') if isinstance(net, dict) else None)),
            tip=(snap.tip if snap is not None else
                 (net.get('tip') if isinstance(net, dict) else None)),
            coordinator=None if self.shared_profile is None else self.shared_profile.coordinator,
            core_alive=self.executor.state.core_alive,
        )

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
                for switch in (self.custody_switch, self.overview.custody_switch):
                    switch.blockSignals(True)
                    switch.setChecked(unlocked)
                    switch.setText('Unlocked' if unlocked else 'Locked')
                    switch.setEnabled(idle and not self._quit_requested
                        and (self.lock.isEnabled() or self.unlock.isEnabled()))
                    switch.blockSignals(False)
                self.overview.security_card.apply(*classify(
                    'security',
                    snap=self._last_verified,
                    locked=not unlocked,
                    operational=unlocked,
                    faulted=self.executor.state.faulted,
                    core_alive=self.executor.state.core_alive,
                    busy=not idle,
                    network=self._network_view(self._last_verified),
                ), animate=False)
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
                    4 if getattr(self, '_broadcast_complete', False) else
                    3 if self._signed_ready else
                    2 if self._approved_commitment is not None else 0
                )
            self._render_network()

    def _present_backup_ack(self, result):
        self.navigation.setEnabled(False)
        self.page_title.setText('Wallet backup')
        self.page_title.show()
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
        self.page_title.hide()
        if success:
            self.connection_pill.setText(classify(
                'snapshot', snap=None, locked=True,
                core_alive=self.executor.state.core_alive)[1])
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
            self.overview.render_snapshot(
                snap, operational=True, network=self._network_view(snap),
                available_atoms=result.get("available_atoms"),
                reservation_count=result.get("reservation_count"),
                core_alive=self.executor.state.core_alive,
                busy=False)
            self.connection_pill.setText(classify(
                'snapshot', snap=snap, operational=True,
                faulted=self.executor.state.faulted,
                core_alive=self.executor.state.core_alive,
                network=self._network_view(snap))[1])
            self.receive_page.render_snapshot(snap)
            self.history_page.render_snapshot(snap)
            self._render_network(snap)
        except (ValueError, TypeError):
            self._clear_visuals()
            self.status.setText("Q06_FUSION_PRESENTATION_DENIED")
            return
        self._last_verified = snap
        self.overview.go_send.setEnabled(self._spend_enabled and
                                         not self.executor.state.faulted)

    def _clear_visuals(self):
        self._last_verified = None
        self.connection_pill.setText(classify(
            'snapshot', snap=None, locked=True,
            faulted=self.executor.state.faulted,
            core_alive=self.executor.state.core_alive)[1])
        self.overview.render_snapshot(
            None, locked=True, faulted=self.executor.state.faulted,
            network=self._network_view(None),
            core_alive=self.executor.state.core_alive)
        self.receive_page.render_snapshot(None)
        self.history_page.render_snapshot(None)
        self._render_network(None)
        if hasattr(self, 'review_summary'):
            self.review_summary.setText('No prepared payment. Recipient, amount, fee and change appear here after Review.')

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
            self._last_network = result['shared_network']
        if action in ('network_status','network_active'):
            self._shared_connected = result['connected']
            self._last_network = result
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
            self._broadcast_complete = False
            self.review_summary.setText(
                f'Recipient  {result.code}\nAmount  {format_wam(result.atoms)} WAM\n'
                f'Fee  {format_wam(result.fee)} WAM\nChange  {format_wam(result.change_atoms)} WAM')
            self.payment_steps.set_stage(1)
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
        if action == "broadcast":
            txid = self.last_txid.text().strip()
            if txid and 'uncertain' not in txid.lower():
                self.send_result.setText(describe_broadcast_result(txid))
                self._broadcast_complete = True
            else:
                self.send_result.setText(describe_broadcast_result(None))
                self._broadcast_complete = False
        if action == "inspect_confirmed":
            txid = result.get("txid") if type(result) is dict else None
            self.send_result.setText(describe_broadcast_result(txid, result))
            if type(result) is dict and result.get("status") == "Q06_CONFIRMED_IN_VERIFIED_HISTORY":
                self._broadcast_complete = True
                self.payment_steps.set_stage(4)
            elif type(result) is dict and result.get("in_mempool") is True:
                self._broadcast_complete = True
                self.payment_steps.set_stage(4)
        if action == "sign":
            self.payment_steps.set_stage(3)
        if action in ("snapshot", "activate"):
            self._render_verified(result)
            txid = self._pending_confirm_txid or self.last_txid.text().strip()
            if (action == "snapshot" and self._broadcast_complete
                    and type(txid) is str and len(txid) == 64):
                self._pending_action = ("inspect_confirmed", txid)
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
            self._broadcast_complete = False
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
            self.connection_pill.setText(classify(
                'snapshot', snap=None, locked=True, faulted=True,
                core_alive=self.executor.state.core_alive)[1])
        elif self._last_verified is not None:
            self.overview.live_badge.setText("Last verified · refresh required")
        self._set_actions()
