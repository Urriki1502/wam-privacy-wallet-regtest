"""Normal packaged managed-wallet selection. No funding or demo wallet.

Profile selection never creates/repairs a wallet. Native owner, private storage,
signed Core, anchor and checkpoint authentication still gate the actual open.
"""
from pathlib import Path
import re
import secrets


def selected_profile(directory,create):
    if type(create) is not bool or not directory.is_absolute() or directory.is_symlink() or not directory.is_dir():
        raise ValueError('MANAGED_PROFILE_SELECTION_DENIED')
    if create:
        root=directory/('wam-fusion-core-'+secrets.token_hex(8))
        if root.exists() or root.is_symlink():raise ValueError('MANAGED_PROFILE_SELECTION_DENIED')
        return root
    if not re.fullmatch('wam-fusion-core-[0-9a-f]{16}',directory.name):
        raise ValueError('MANAGED_PROFILE_SELECTION_DENIED')
    # Missing/dirty state is not turned into a new wallet by opening it.
    if not (directory/'supervisor.profile').is_file():
        raise ValueError('MANAGED_PROFILE_SELECTION_DENIED')
    return directory


def launch(core,source):
    from .desktop import qt_application
    from .managed_gui import launch_managed
    from PySide6.QtWidgets import QFileDialog,QInputDialog,QMessageBox
    qt_application()
    if QMessageBox.question(None,'Managed REGTEST wallet',
            'Open or create a persistent local REGTEST wallet?\nNo mainnet or real funds. '
            'Closing the wallet locks it and keeps its owned Core running; '
            'use Stop managed Core and quit to exit.',
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return 0
    entries=(
        'Open existing managed wallet (Q05)',
        'Create new managed wallet (Q05)',
        'Create NEW BIP39 12-word wallet (Q06 · read-only)',
        'Restore BIP39 12 words in NEW isolated profile (Q06 · read-only)',
        'Open existing BIP39 12-word profile (Q06 · read-only)',
    )
    action,ok=QInputDialog.getItem(None,'Managed REGTEST profile',
        'Choose the wallet engine (Q06 is read-only)',list(entries),0,False)
    if not ok:return 0
    q06=action in entries[2:]
    create=action in (entries[1], entries[2], entries[3])
    selected=QFileDialog.getExistingDirectory(None,
        'Select an empty parent folder for a NEW isolated REGTEST profile'
        if create else 'Select the exact existing managed REGTEST profile')
    if not selected:return 0
    root=selected_profile(Path(selected).absolute(),create)
    if q06:
        # Q06 does not use Q05 Keyring, GUI signing or backup format.
        from .bip39_owner_gui import launch_bip39_trial
        mode='create' if action==entries[2] else 'restore' if action==entries[3] else 'reopen'
        return launch_bip39_trial(root,core,source,mode=mode,authorized=True)
    return launch_managed(root,core,source,authorized=True,create=create)
