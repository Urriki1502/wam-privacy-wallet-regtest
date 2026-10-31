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
    action,ok=QInputDialog.getItem(None,'Managed REGTEST profile','Wallet profile',
        ['Open existing wallet','Create new isolated wallet'],0,False)
    if not ok:return 0
    create=action=='Create new isolated wallet'
    selected=QFileDialog.getExistingDirectory(None,
        'Select parent folder for a NEW profile' if create else 'Select existing managed profile')
    if not selected:return 0
    root=selected_profile(Path(selected).absolute(),create)
    return launch_managed(root,core,source,authorized=True,create=create)
