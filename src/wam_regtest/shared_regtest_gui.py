"""Manual immutable Core P2P profile selection; no networking in the GUI."""
from .shared_regtest import SharedRegtestProfile, SharedRegtestError


def configure(parent=None):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QDialog, QVBoxLayout, QFormLayout, QLineEdit, QSpinBox, QCheckBox, QDialogButtonBox
    from .fusion_ui import label, fusion_stylesheet
    dialog = QDialog(parent)
    dialog.setWindowTitle('Shared REGTEST · manual peer')
    dialog.setMinimumWidth(530)
    mode='dark' if QApplication.styleHints().colorScheme()==Qt.ColorScheme.Dark else 'light'
    dialog.setStyleSheet(fusion_stylesheet(mode))
    layout = QVBoxLayout(dialog)
    layout.addWidget(label('Use a NEW separate profile. Reopen requires these exact settings. '
                           'Only the designated coordinator mines. Connect both nodes before mining. '
                           'RPC remains 127.0.0.1; only Core P2P is shared.'))
    form = QFormLayout()
    fields = {}
    for key,title,default in (('peer_host','Peer private/LAN/VPN IP',''),
                              ('bind_host','This computer’s P2P interface IP','127.0.0.1')):
        field = QLineEdit(default)
        field.setAccessibleName(title)
        fields[key] = field
        form.addRow(title,field)
    for key,title,default in (('rpc_port','Local RPC port',29554),('p2p_port','Local P2P port',29555),
                              ('peer_port','Peer P2P port',29555)):
        field = QSpinBox()
        field.setRange(1024,65535)
        field.setValue(default)
        field.setAccessibleName(title)
        fields[key] = field
        form.addRow(title,field)
    role = QCheckBox('I authorize this node as the sole mining coordinator')
    form.addRow(role)
    layout.addLayout(form)
    message = label('', 'FusionMuted')
    layout.addWidget(message)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
    layout.addWidget(buttons)
    result = None
    def accept():
        nonlocal result
        try:
            result = SharedRegtestProfile(**{k:(v.text().strip() if isinstance(v,QLineEdit) else v.value())
                                               for k,v in fields.items()},coordinator=role.isChecked())
        except SharedRegtestError:
            message.setText('Use literal private IP addresses, separate local ports and a different peer endpoint.')
            return
        dialog.accept()
    buttons.accepted.connect(accept)
    buttons.rejected.connect(dialog.reject)
    try:
        return result if dialog.exec() == QDialog.DialogCode.Accepted else None
    finally:
        dialog.deleteLater()
