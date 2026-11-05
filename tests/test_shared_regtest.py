"""Policy negatives; these tests do NOT certify a real P2P network."""
import unittest
import sys
from wam_regtest.shared_regtest import SharedRegtestProfile, SharedRegtestError, validate_peers
from wam_regtest.network_policy import parse_local_config, NetworkPolicyError
from wam_regtest.cli_rpc import validate, CliRpcError


class SharedPolicyContracts(unittest.TestCase):
    def profile(self, **kwargs):
        return SharedRegtestProfile('127.0.0.1', peer_port=29557, **kwargs)

    def config(self, profile):
        settings = profile.settings()
        settings.update(rpcuser='disposable_'+'a'*16, rpcpassword='b'*64)
        return ('regtest=1\nserver=1\n[regtest]\n'+''.join(
            f'{key}={value}\n' for key,value in settings.items())).encode()

    def test_shared_config_requires_explicit_matching_profile(self):
        profile = self.profile(coordinator=True)
        raw = self.config(profile)
        self.assertEqual(parse_local_config(raw,shared_profile=profile),29554)
        with self.assertRaises(NetworkPolicyError):
            parse_local_config(raw)
        with self.assertRaises(NetworkPolicyError):
            parse_local_config(raw,shared_profile=self.profile())

    def test_remote_rpc_or_unknown_config_option_is_refused(self):
        profile = self.profile()
        raw = self.config(profile)
        for altered in (raw.replace(b'rpcbind=127.0.0.1',b'rpcbind=0.0.0.0'),
                        raw+b'proxy=127.0.0.1:9050\n', raw+b'addnode=10.1.1.2:29555\n'):
            with self.assertRaises(NetworkPolicyError):
                parse_local_config(altered,shared_profile=profile)

    def test_injection_public_self_and_port_collision_endpoints_are_denied(self):
        for host in ('8.8.8.8','0.0.0.0','224.0.0.1','127.0.0.1\nserver=0','https://localhost','localhost'):
            with self.assertRaises(SharedRegtestError):
                SharedRegtestProfile(host)
        with self.assertRaises(SharedRegtestError):
            SharedRegtestProfile('127.0.0.1')
        with self.assertRaises(SharedRegtestError):
            self.profile(rpc_port=29555)

    def test_only_prescribed_peer_and_completed_core_handshake_allow_mining(self):
        profile = self.profile()
        with self.assertRaises(SharedRegtestError):
            validate_peers([],profile,require_connected=True)
        row = dict(addr='127.0.0.1:29557',inbound=False,version=70016,subver='/WAM:0.1.11/')
        self.assertTrue(validate_peers([row],profile,require_connected=True)['connected'])
        for altered in (dict(row,addr='10.0.0.9:29557'),dict(row,version=70015),
                        dict(row,addr='127.0.0.1:9555'),dict(row,subver='/untrusted/')):
            with self.assertRaises(SharedRegtestError):
                validate_peers([altered],profile,require_connected=True)

    def test_network_control_is_finite_not_arbitrary_rpc(self):
        self.assertEqual(validate(['setnetworkactive','false']),('setnetworkactive',['false']))
        for args in (['setnetworkactive','true','extra'],['addnode','arbitrary','add'],['getpeerinfo','extra']):
            with self.assertRaises(CliRpcError):validate(args)

    def test_participant_mining_denied_before_core_or_wallet_access(self):
        from pathlib import Path
        from wam_regtest.bip39_owner_backend import Bip39ReadOnlyBackend, Q06ReadOnlyError
        backend = Bip39ReadOnlyBackend(Path('/unused'),Path('/unused'),Path('/unused'),shared_profile=self.profile())
        for action in ('mine','confirm','ci_confirm'):
            with self.assertRaisesRegex(Q06ReadOnlyError,'SHARED_SINGLE_COORDINATOR_REQUIRED'):
                backend.execute(action,(),{})
        self.assertIsNone(backend.owner)

    def test_reorg_fixture_retained_runtime_cannot_skip_original_owner_shutdown(self):
        from unittest.mock import Mock,patch
        from wam_regtest.shared_network_probe import close_reorg_owners
        session=Mock()
        session.lock.side_effect=ValueError('Q06_SPEND_RUNTIME_PRESERVED')
        owner=Mock(_faulted=False)
        with patch('wam_regtest.rpc_scope.identity',return_value=None):
            self.assertEqual(close_reorg_owners([session],[owner]),[])
        owner.shutdown.assert_called_once_with()
        owner.release.assert_called_once_with()
        owner.close.assert_called_once_with()
        owner.recover_stop.assert_not_called()

    def test_reorg_stop_failure_retains_original_owner_instead_of_losing_handle(self):
        from unittest.mock import Mock,patch
        from wam_regtest.shared_network_probe import close_reorg_owners
        owner=Mock(_faulted=False)
        owner.shutdown.side_effect=ValueError('MANAGED_SHUTDOWN_UNCERTAIN')
        with patch('wam_regtest.rpc_scope.identity',return_value=None), \
                patch('wam_regtest.shared_network_probe.retain_original_owner') as retain:
            self.assertEqual(close_reorg_owners([],[owner]),['ORIGINAL_OWNER_STOP_DENIED'])
        retain.assert_called_once_with(owner)
        owner.release.assert_not_called()

    @unittest.skipUnless(sys.platform=='darwin','Native Qt configuration checked on macOS')
    def test_manual_configuration_requires_private_endpoint_and_explicit_role(self):
        from wam_regtest.desktop import qt_application
        from wam_regtest.shared_regtest_gui import configure
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QDialog,QLineEdit,QSpinBox,QCheckBox,QDialogButtonBox
        app=qt_application()
        timer=QTimer()
        timer.setInterval(30)
        guard=QTimer()
        guard.setSingleShot(True)
        guard.timeout.connect(lambda:app.activeModalWidget().reject() if isinstance(app.activeModalWidget(),QDialog) else None)
        steps=[]
        def interact():
            dialog=app.activeModalWidget()
            if not isinstance(dialog,QDialog):return
            edits=dialog.findChildren(QLineEdit)
            peer=next(e for e in edits if e.accessibleName()=='Peer private/LAN/VPN IP')
            box=dialog.findChild(QDialogButtonBox)
            if not steps:
                peer.setText('8.8.8.8')
                box.button(QDialogButtonBox.StandardButton.Ok).click()
                steps.append('public_endpoint_refused' if dialog.result()!=QDialog.DialogCode.Accepted else 'UNSAFE')
                return
            peer.setText('127.0.0.1')
            port=next(p for p in dialog.findChildren(QSpinBox) if p.accessibleName()=='Peer P2P port')
            port.setValue(29557)
            dialog.findChild(QCheckBox).setChecked(True)
            timer.stop()
            box.button(QDialogButtonBox.StandardButton.Ok).click()
        timer.timeout.connect(interact)
        timer.start()
        guard.start(5000)
        try:profile=configure()
        finally:timer.stop();guard.stop()
        self.assertEqual(steps,['public_endpoint_refused'])
        self.assertEqual(profile,SharedRegtestProfile('127.0.0.1',peer_port=29557,coordinator=True))

    @unittest.skipUnless(sys.platform=='darwin','Native Qt configuration checked on macOS')
    def test_two_window_sign_approval_is_clicked_without_active_modal(self):
        from wam_regtest.desktop import qt_application
        from wam_regtest.shared_network_probe import click_visible_approval
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QDialog, QPushButton, QWidget
        app = qt_application()
        first, second = QWidget(), QWidget()
        first.setWindowTitle('node-a'); second.setWindowTitle('node-b')
        first.show(); second.show()
        dialog = QDialog(first)
        dialog.setWindowTitle('Approve signature')
        approve = QPushButton('Approve Sign', dialog)
        approve.clicked.connect(dialog.accept)
        dialog.show()
        second.raise_()
        second.activateWindow()
        app.processEvents()
        self.assertTrue(click_visible_approval(app, 'Approve Sign'))
        deadline = QTimer()
        deadline.setSingleShot(True)
        deadline.timeout.connect(dialog.reject)
        deadline.start(1000)
        try:
            self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        finally:
            deadline.stop(); dialog.close(); first.close(); second.close()

    def test_xor_block_magic_is_checked_and_symlinks_refused(self):
        from pathlib import Path
        import tempfile
        from wam_regtest.shared_regtest import block_magic, MAGIC
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp).resolve()
            blocks=directory/'regtest'/'blocks'
            blocks.mkdir(mode=0o700,parents=True)
            mask=bytes(range(8))
            (blocks/'xor.dat').write_bytes(mask)
            (blocks/'blk00000.dat').write_bytes(bytes(v^mask[i] for i,v in enumerate(MAGIC)))
            self.assertEqual(block_magic(directory),'57414d52')
            (blocks/'blk00000.dat').write_bytes(b'bad!')
            with self.assertRaisesRegex(SharedRegtestError,'SHARED_NETWORK_MAGIC_DENIED'):block_magic(directory)
            (blocks/'blk00000.dat').unlink()
            (blocks/'blk00000.dat').symlink_to(blocks/'xor.dat')
            with self.assertRaises(OSError):block_magic(directory)


if __name__ == '__main__':unittest.main()
