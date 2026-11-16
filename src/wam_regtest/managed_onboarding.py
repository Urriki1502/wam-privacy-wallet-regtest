"""Single normal WAM Fusion entry for REGTEST BIP39, retaining legacy Q05.

No new wallet owner, seed conversion, backup import, Core/GUI signing authority
or automatic recovery. The welcome screen only chooses an explicit route.
Every actual profile is authenticated by its existing native owner.
"""
from pathlib import Path
import re
import secrets


def selected_profile(directory, create):
    if (type(create) is not bool or not directory.is_absolute()
            or directory.is_symlink() or not directory.is_dir()):
        raise ValueError("MANAGED_PROFILE_SELECTION_DENIED")
    if create:
        root = directory / ("wam-fusion-core-" + secrets.token_hex(8))
        if root.exists() or root.is_symlink():
            raise ValueError("MANAGED_PROFILE_SELECTION_DENIED")
        return root
    if not re.fullmatch(r"wam-fusion-core-[0-9a-f]{16}", directory.name):
        raise ValueError("MANAGED_PROFILE_SELECTION_DENIED")
    # Opening an old folder must never silently create/repair/replace it.
    if not (directory / "supervisor.profile").is_file():
        raise ValueError("MANAGED_PROFILE_SELECTION_DENIED")
    return directory


# (uses BIP39, seed open mode, selects NEW disposable Core profile)
_ROUTES = {
    "create": (True, "create", True),
    "open": (True, "reopen", False),
    "restore": (True, "restore", True),
    "legacy_open": (False, None, False),
    "legacy_create": (False, None, True),
}


def wallet_route(choice):
    """Pure routing contract; never migrate Q05 keys/anchors into Q06."""
    if type(choice) is not str or choice not in _ROUTES:
        raise ValueError("WAM_FUSION_WELCOME_CHOICE_DENIED")
    return _ROUTES[choice]


def welcome_dialog():
    """One native Qt welcome screen; no Core, seed or credential is opened."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QApplication, QDialog, QFrame, QHBoxLayout, QToolButton, QVBoxLayout, QCheckBox,
        QScrollArea, QWidget,
    )
    from .fusion_ui import action, label, panel, fusion_palette, fusion_stylesheet, vector_icon

    dialog = QDialog()
    dialog.setObjectName("WAMFusionWelcome")
    dialog.setWindowTitle("WAM Fusion · Privacy Wallet")
    dialog.setMinimumSize(540, 550)
    dialog.setModal(True)
    dialog.selection = None
    dialog.buttons = {}
    hint = QApplication.styleHints()
    mode = "dark" if hint.colorScheme() == Qt.ColorScheme.Dark else "light"
    dialog.setStyleSheet(fusion_stylesheet(mode))
    palette = fusion_palette(mode)

    outer = QVBoxLayout(dialog)
    outer.setContentsMargins(0, 0, 0, 0)
    scroll = QScrollArea(dialog)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    content = QWidget()
    scroll.setWidget(content)
    outer.addWidget(scroll)
    root = QVBoxLayout(content)
    root.setContentsMargins(28, 28, 28, 24)
    root.setSpacing(18)
    root.addWidget(label("WAM FUSION", "FusionKicker"))
    root.addWidget(label("Welcome to your wallet", "PageTitle"))
    root.addWidget(label(
        "Choose how to begin. Your keys stay on this device; "
        "no account or cloud connection is required."
    ))
    root.addWidget(label("REGTEST PREVIEW · NO REAL FUNDS", "FusionBadge"))
    dialog.shared_mode = QCheckBox('Shared REGTEST · manual Core P2P')
    dialog.shared_mode.setToolTip('Explicit separate profile. RPC stays on this computer. No automatic peer discovery.')
    root.addWidget(dialog.shared_mode)

    choices, layout = panel(
        "Your wallet",
        "One wallet experience · BIP39 12-word recovery",
    )
    for key, title, detail, icon_name, primary in (
        ("create", "Create a new wallet",
         "Generate a new 12-word recovery phrase", "overview", True),
        ("open", "Open existing wallet",
         "Unlock a wallet on this device", "unlock", False),
        ("restore", "Restore from 12 words",
         "Start a new profile from your existing recovery phrase", "backup", False),
    ):
        button = action(title, icon_name, primary)
        button.setAccessibleName(title)
        button.setMinimumHeight(48)
        button.setIcon(vector_icon(
            icon_name, palette["onaccent"] if primary else palette["accent"]))
        dialog.buttons[key] = button
        layout.addWidget(button)
        layout.addWidget(label(detail, "FusionMuted"))
    root.addWidget(choices)

    legacy = QToolButton()
    legacy.setText("Legacy wallet compatibility  ▾")
    legacy.setObjectName("FusionAdvanced")
    legacy.setAccessibleName("Show legacy Q05 wallet options")
    legacy.setCheckable(True)
    root.addWidget(legacy)

    older = QFrame()
    older.setObjectName("FusionInset")
    older_layout = QVBoxLayout(older)
    older_layout.addWidget(label(
        "For existing Q05 test profiles only. Legacy files are never "
        "converted or used as BIP39 seed material."
    ))
    for key, title in (
        ("legacy_open", "Open legacy wallet"),
        ("legacy_create", "Create legacy test wallet"),
    ):
        button = action(title, "lock")
        dialog.buttons[key] = button
        older_layout.addWidget(button)
    older.hide()
    root.addWidget(older)
    legacy.toggled.connect(older.setVisible)
    root.addStretch()

    def select(key):
        dialog.selection = key
        dialog.accept()

    for key, button in dialog.buttons.items():
        button.clicked.connect(
            lambda _checked=False, selected=key: select(selected))
    dialog.legacy_toggle = legacy
    dialog.legacy_panel = older
    return dialog


def assert_unified_welcome_qt():
    """Live Qt source/packaged smoke. Never creates keys or starts a Core."""
    from PySide6.QtWidgets import QDialog
    for choice in ("create", "open", "restore"):
        dialog = welcome_dialog()
        if (dialog.selection is not None or dialog.legacy_panel.isVisible()
                or not all(k in dialog.buttons for k in _ROUTES)):
            raise ValueError("WAM_FUSION_WELCOME_LAYOUT_DENIED")
        dialog.buttons[choice].click()
        if (dialog.result() != QDialog.DialogCode.Accepted
                or dialog.selection != choice or not wallet_route(choice)[0]):
            raise ValueError("WAM_FUSION_WELCOME_BIP39_ROUTE_DENIED")
        dialog.deleteLater()
    dialog = welcome_dialog()
    dialog.legacy_toggle.click()
    if not dialog.legacy_toggle.isChecked():
        raise ValueError("WAM_FUSION_LEGACY_NOT_AVAILABLE")
    dialog.buttons["legacy_open"].click()
    if (dialog.selection != "legacy_open"
            or wallet_route(dialog.selection)[0]):
        raise ValueError("WAM_FUSION_LEGACY_ROUTE_DENIED")
    dialog.deleteLater()

    # Also executed by genuine native/frozen Q06 probes before any owner exists.
    from .onboarding_probe import qualify_password_dialogs
    qualify_password_dialogs()


def launch(core, source):
    from .desktop import qt_application
    from PySide6.QtWidgets import QFileDialog, QDialog, QMessageBox
    qt_application()
    while True:
        dialog = welcome_dialog()
        try:
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return 0
            choice = dialog.selection
            shared = dialog.shared_mode.isChecked()
        finally:
            dialog.deleteLater()
        q06, mode, create = wallet_route(choice)
        shared_profile = None
        if shared:
            if not q06:
                QMessageBox.warning(None, 'Shared REGTEST', 'Shared mode requires a BIP39 wallet profile.')
                continue
            from .shared_regtest_gui import configure
            shared_profile = configure()
            if shared_profile is None:
                continue
        selected = QFileDialog.getExistingDirectory(
            None,
            ("Choose a parent folder for the NEW REGTEST wallet profile"
             if create else
             "Choose the exact EXISTING REGTEST wallet profile"),
        )
        if not selected:
            continue
        try:
            root = selected_profile(Path(selected).absolute(), create)
        except ValueError:
            QMessageBox.warning(
                None, "Wallet folder not accepted",
                "Choose an existing wallet profile or a safe parent folder "
                "for a new one. No wallet files were changed.",
            )
            continue
        if q06:
            from .bip39_owner_gui import launch_bip39_trial
            return launch_bip39_trial(
                root, core, source, mode=mode, authorized=True, shared_profile=shared_profile)
        # Preserve the established Q05 engine and separate legacy format.
        from .managed_gui import launch_managed
        return launch_managed(
            root, core, source, authorized=True, create=create)
