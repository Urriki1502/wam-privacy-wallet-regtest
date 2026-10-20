"""Fusion managed-Core widget contracts. Not Q05 real-Core/frozen evidence."""
from pathlib import Path
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QMessageBox
from wam_regtest.desktop import qt_application
from wam_regtest.managed_gui import ManagedCoreWindow, VISIBLE_STATES
from wam_regtest.supervisor_protocol import public_status


class ManagedFusionWidgetContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The native unittest runner calls shutdown_qt() after ALL suites,
        # before Python interpreter teardown. No atexit QApplication work.
        cls.app = qt_application()

    def setUp(self):
        self.win = ManagedCoreWindow(Path("/tmp/wam-fusion-core-0123456789abcdef")
            if __import__("sys").platform!="win32" else Path("C:/wam-fusion-core-0123456789abcdef"))
        # Deterministically dispose native Qt windows before the interpreter
        # tears down QApplication. Merely closing leaves a QMainWindow object
        # and its native signal connections alive until Python GC at exit.
        self.addCleanup(self._dispose_window)
        # Constructing a GUI cannot start, stop or connect to an unverified Core.
        self.assertEqual(self.win._managed_state, "error")
        self.assertIsNone(self.win.session)
        self.assertIsNone(self.win._snapshot)
        self.assertFalse(self.win.start_core.isEnabled())
        self.assertFalse(self.win.stop_core.isEnabled())

    def _dispose_window(self):
        import gc
        from shiboken6 import delete, isValid
        if self.win is not None:
            window=self.win
            self.assertTrue(window.close())
            # deleteLater() alone depends on the event loop and has left
            # native Qt wrappers alive at Python interpreter finalization.
            delete(window)
            self.assertFalse(isValid(window))
            self.win=None
            del window
            gc.collect()
            self.app.processEvents()

    def test_f08_welcome_scroll_navigation_and_zero_wallet_adoption(self):
        from PySide6.QtWidgets import QScrollArea
        self.assertEqual(self.win.navigation.count(),4)
        self.assertEqual(
            [self.win.navigation.item(i).text() for i in range(4)],
            ['Overview','Receive','History','Get Started'])
        self.assertEqual(self.win.stack.count(),4)
        self.assertEqual(self.win.navigation.currentRow(),3)
        self.assertIs(self.win.stack.currentWidget(),self.win.welcome_page)
        self.assertEqual(self.win.workspace_title.text(),'Get Started')
        self.assertIsInstance(self.win.welcome_page.scroll,QScrollArea)
        self.assertTrue(self.win.welcome_page.scroll.widgetResizable())
        self.assertEqual(self.win.welcome_page.core_state.text(),'Core: Unverified')
        self.assertIsNone(self.win._snapshot)
        self.assertIsNone(self.win.session)

    def test_f08_unverified_gui_cannot_start_wallet_or_sign(self):
        page=self.win.welcome_page
        for guide,original in self.win._f08_welcome_sources:
            self.assertEqual(guide.isEnabled(),original.isEnabled())
        for attr in ('start','create','verify','view','sync','send'):
            self.assertFalse(getattr(page,attr).isEnabled())
        page.start.click();page.create.click();page.send.click()
        self.assertIsNone(self.win._worker)
        self.assertIsNone(self.win.session)
        self.assertIsNone(self.win._snapshot)
        self.assertFalse(self.win.dashboard.go_send.isEnabled())

    def test_f08_verified_core_is_not_wallet_custody_authority(self):
        self.win._apply_managed_status(
            public_status(state='ready',owned=True,chain_height=101))
        p=self.win.welcome_page
        self.assertIn('Ready',p.core_state.text())
        self.assertIn('101',p.height_state.text())
        self.assertTrue(p.refresh.isEnabled())
        self.assertFalse(p.start.isEnabled())
        self.assertFalse(p.create.isEnabled())
        self.assertFalse(p.verify.isEnabled())
        self.assertFalse(p.send.isEnabled())
        self.assertFalse(self.win.dashboard.go_send.isEnabled())
        self.assertIsNone(self.win._snapshot)

    def test_f08_original_guarded_controls_only_allow_create_or_verify(self):
        import tempfile
        with tempfile.TemporaryDirectory(prefix='f08-public-test-') as directory:
            root=Path(directory).resolve()
            self.win._managed_root=root
            self.win._wallet_core_dir=root/'qualified-core'
            self.win._wallet_wsp_source=root/'wsp-source'
            self.win._apply_managed_status(
                public_status(state='ready',owned=True,chain_height=101))
            p=self.win.welcome_page
            self.assertTrue(p.create.isEnabled())
            # Existing guarded verification may request an explicit
            # passphrase before determining whether a vault exists.
            # Guided UI must mirror that original control, not invent
            # a new trust/authorization rule.
            self.assertEqual(
                p.verify.isEnabled(),self.win.verify_wallet_button.isEnabled())
            self.assertFalse(p.send.isEnabled())
            (root/'chain'/'wallet-vault').mkdir(parents=True)
            self.win._update_controls()
            self.assertFalse(p.create.isEnabled())
            self.assertTrue(p.verify.isEnabled())
            self.assertTrue(p.send.isEnabled())
            self.assertIsNone(self.win.session)
            self.assertFalse(self.win.dashboard.go_send.isEnabled())
            self.win._apply_managed_status(
                public_status(state='busy',owned=True))
            self.assertFalse(p.create.isEnabled())
            self.assertFalse(p.verify.isEnabled())
            self.assertFalse(p.send.isEnabled())
            self.assertIn('unavailable',p.height_state.text().lower())

    def test_f08_busy_worker_cannot_bypass_guarded_creation(self):
        import tempfile
        with tempfile.TemporaryDirectory(prefix='f08-public-test-') as directory:
            root=Path(directory).resolve()
            self.win._managed_root=root
            self.win._wallet_core_dir=root/'qualified-core'
            self.win._wallet_wsp_source=root/'wsp-source'
            self.win._apply_managed_status(
                public_status(state='ready',owned=True,chain_height=101))
            self.assertTrue(self.win.welcome_page.create.isEnabled())
            self.win._worker=object()
            try:
                self.win._update_controls()
                self.assertFalse(self.win.welcome_page.create.isEnabled())
                self.assertFalse(self.win.welcome_page.refresh.isEnabled())
                self.assertFalse(self.win.welcome_page.inspect.isEnabled())
            finally:
                self.win._worker=None
            self.win._update_controls()
            self.assertTrue(self.win.welcome_page.create.isEnabled())

    def test_f08_status_rejects_hostile_or_fabricated_fields(self):
        p=self.win.welcome_page
        for bad in (
            dict(state='mainnet',authenticated=True,height=1,wallet_exists=False),
            dict(state='ready',authenticated=1,height=1,wallet_exists=False),
            dict(state='ready',authenticated=True,height=True,wallet_exists=False),
            dict(state='ready',authenticated=True,height=-1,wallet_exists=False),
            dict(state='ready',authenticated=True,height=1,wallet_exists='yes'),
        ):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                p.render_status(**bad)
        p.render_status(
            state='ready',authenticated=False,height=101,wallet_exists=True)
        self.assertEqual(p.core_state.text(),'Core: Unverified')
        self.assertIn('unavailable',p.height_state.text().lower())
        self.assertIn('verification required',p.wallet_state.text())

    def test_f08_original_readonly_navigation_remains_unmodified(self):
        for i in range(3):
            self.win.navigation.setCurrentRow(i)
            self.assertIs(self.win.stack.currentWidget(),
                          (self.win.dashboard,self.win.receive_page,
                           self.win.history_page)[i])
            self.assertIsNone(self.win._snapshot)
        self.win.navigation.setCurrentRow(3)
        self.assertIs(self.win.stack.currentWidget(),self.win.welcome_page)
        self.assertEqual(self.win.workspace_title.text(),'Get Started')

    def test_all_allowed_supervisor_states_are_rendered_without_wallet_adoption(self):
        for state in VISIBLE_STATES:
            with self.subTest(state=state):
                running = state in ("ready","syncing","busy")
                height = 103 if running else None
                result = public_status(state=state,owned=running,chain_height=height)
                self.win._apply_managed_status(result)
                self.assertEqual(self.win._managed_state,state)
                self.assertIn(VISIBLE_STATES[state],self.win.status.text())
                self.assertIsNone(self.win._snapshot)
                self.assertFalse(self.win.dashboard.go_send.isEnabled())
                self.assertFalse(self.win.stop_core.isEnabled() if not running else self.win.start_core.isEnabled())

    def test_t07_busy_state_increases_refresh_interval_without_unlocking_wallet(self):
        ready=public_status(state="ready",owned=True,chain_height=101)
        busy=public_status(state="busy",owned=True)
        self.win._apply_managed_status(ready)
        self.assertEqual(self.win._sync_timer.interval(),5_000)
        self.win._apply_managed_status(busy)
        self.assertEqual(self.win._sync_timer.interval(),15_000)
        self.assertIn("NODE BUSY",self.win.status.text())
        self.assertIn("RETRYING",self.win.status.text())
        self.assertFalse(self.win._wallet_checkpoint_verified)
        self.assertIsNone(self.win._snapshot)
        self.assertIsNone(self.win._managed_height)
        self.assertFalse(self.win.dashboard.go_send.isEnabled())
        self.win._apply_managed_status(ready)
        self.assertEqual(self.win._sync_timer.interval(),5_000)
        self.assertEqual(self.win._managed_height,101)

    def test_k01_bip39_wizard_is_separate_from_locked_managed_wallet(self):
        from PySide6.QtWidgets import QDialog
        self.assertTrue(self.win.bip39_button.isEnabled())
        self.assertFalse(self.win.create_wallet_button.isEnabled())
        self.assertIn("NOT BIP39",self.win.create_wallet_button.text())
        self.assertIn("not wallet",self.win.bip39_button.text())
        before=self.win.status.text()
        # A local BIP39 dialog must not touch the Core, wallet vault or
        # generate an original 32-byte WSP keyring on cancelled flow.
        with (patch("wam_regtest.bip39_gui.Bip39CreationDialog.exec",
                    return_value=QDialog.DialogCode.Rejected) as wizard,
              patch("wam_regtest.managed_gui.control",
                    side_effect=AssertionError("K01_MUST_NOT_CONTACT_CORE"))):
            self.win.bip39_button.click()
            wizard.assert_called_once()
        self.assertEqual(self.win.status.text(),before)
        self.assertFalse(self.win._managed_authenticated)
        self.assertFalse(self.win.create_wallet_button.isEnabled())
        self.assertIsNone(self.win.session)

    def test_k04_core_dat_picker_is_inspection_only_without_wallet_rpc(self):
        import tempfile
        import sqlite3
        from pathlib import Path
        from unittest.mock import patch
        from wam_regtest.managed_gui import _CoreSqliteInspectionWorker
        self.assertTrue(self.win.sqlite_inspect_button.isEnabled())
        self.assertIn("NO IMPORT",self.win.sqlite_inspect_button.text())
        with tempfile.TemporaryDirectory(prefix="k04-gui-public-") as d:
            path=Path(d)/"fixture.dat"
            sql=sqlite3.connect(path)
            try:
                sql.execute("CREATE TABLE public_test(value INT)")
                sql.commit()
            finally:sql.close()
            if __import__("os").name!="nt":path.chmod(0o600)
            # The native Qt worker emits non-secret FORMAT ONLY. No
            # Core/managed wallet RPC may be contacted.
            worker=_CoreSqliteInspectionWorker(path)
            good=[]
            worker.ready.connect(lambda proof:good.append(proof))
            with patch("wam_regtest.managed_gui.control",
                       side_effect=AssertionError("K04_NO_CORE_RPC")):
                worker.run()
            self.assertEqual(len(good),1)
            self.win._core_sqlite_inspected(good[0])
            self.assertIn("NO IMPORT",self.win.status.text())
            self.assertIn("NETWORK/PROVENANCE UNKNOWN",self.win.status.text())
            self.assertFalse(self.win.dashboard.go_send.isEnabled())
        self.win._core_sqlite_inspected({"network":"mainnet"})
        self.assertIn("DENIED",self.win.status.text())
        self.assertIsNone(self.win.session)

    def test_k04_file_picker_cancel_does_not_touch_core_or_wallet(self):
        with (patch("wam_regtest.managed_gui.QFileDialog.getOpenFileName",
                    return_value=("","")) as picker,
              patch("wam_regtest.managed_gui.control",
                    side_effect=AssertionError("K04_NO_CORE_ACTION"))):
            self.win.sqlite_inspect_button.click()
            picker.assert_called_once()
        self.assertIsNone(self.win._worker)
        self.assertIsNone(self.win.session)

    def test_k05_bdb_ui_refusal_explains_no_conversion_or_core_access(self):
        import tempfile
        from hashlib import sha256
        from wam_regtest.managed_gui import _CoreSqliteInspectionWorker
        with tempfile.TemporaryDirectory(prefix="k05-bdb-public-") as temp:
            source=Path(temp)/"wallet.dat"
            body=bytearray(8192)
            body[12:16]=(0x00053162).to_bytes(4,"little")
            source.write_bytes(body)
            # DEV WAM regression: ZIP/USB legacy backup frequently has
            # mode 0644; format denial must run BEFORE SQLite custody gate.
            if os.name!="nt":source.chmod(0o644)
            original=sha256(source.read_bytes()).hexdigest()
            reason=[]
            accepted=[]
            worker=_CoreSqliteInspectionWorker(source)
            worker.denied.connect(reason.append)
            worker.ready.connect(accepted.append)
            with patch("wam_regtest.managed_gui.control",
                       side_effect=AssertionError("K05_NO_CORE_RPC")):
                worker.run()
            self.assertEqual(reason,["K05_BDB_DEPRECATED_UNSUPPORTED"])
            self.assertEqual(accepted,[])
            self.win._core_sqlite_denied(reason[0])
            self.assertIn("Berkeley DB",self.win.status.text())
            self.assertIn("does NOT import",self.win.status.text())
            self.assertIn("migratewallet",self.win.status.text())
            self.assertIn("Linux",self.win.status.text())
            self.assertIn("NO AUTOMATIC IMPORT OR CONVERSION",
                          self.win.status.text())
            self.assertEqual(original,sha256(source.read_bytes()).hexdigest())
            self.assertFalse(self.win.dashboard.go_send.isEnabled())
            self.assertIsNone(self.win.session)
            self.assertIsNone(self.win._snapshot)

    def test_k05_sqlite_0644_reports_owner_custody_fix_without_import(self):
        if os.name=="nt":self.skipTest("POSIX file mode gate")
        import tempfile
        import sqlite3
        from wam_regtest.managed_gui import _CoreSqliteInspectionWorker
        with tempfile.TemporaryDirectory(prefix="k05-public-sqlite-") as d:
            path=Path(d)/"public-fixture.dat"
            db=sqlite3.connect(path)
            try:
                db.execute("CREATE TABLE public_dummy(x INT)")
                db.commit()
            finally:db.close()
            path.chmod(0o644)
            denied=[]
            w=_CoreSqliteInspectionWorker(path)
            w.denied.connect(denied.append)
            with patch("wam_regtest.managed_gui.control",
                       side_effect=AssertionError("K05_NEVER_CORE")):
                w.run()
            self.assertEqual(denied,["K05_SQLITE_PRIVATE_CUSTODY_REQUIRED"])
            self.win._core_sqlite_denied(denied[0])
            self.assertIn("0600",self.win.status.text())
            self.assertIn("NO WALLET LOAD OR IMPORT",self.win.status.text())
            self.assertIsNone(self.win.session)

    def test_k05_fusion_enc_and_bip39_text_never_become_core_dat(self):
        from wam_regtest.managed_gui import _CoreSqliteInspectionWorker
        for ext,expected,notice in (
                (".enc","K05_FUSION_ENCRYPTED_BACKUP_SEPARATE","Fusion .enc"),
                (".txt","K05_MNEMONIC_TEXT_NOT_WALLET_DAT","BIP39 mnemonic")):
            with self.subTest(ext=ext):
                reason=[]
                worker=_CoreSqliteInspectionWorker(
                    Path.cwd()/("nonexistent-private-test"+ext))
                worker.denied.connect(reason.append)
                with (patch("wam_regtest.managed_gui.control",
                            side_effect=AssertionError("K05_NO_RPC")),
                      patch("wam_regtest.legacy_bdb_refusal.os.open",
                            side_effect=AssertionError("K05_NO_FILE_OPEN"))):
                    worker.run()
                self.assertEqual(reason,[expected])
                self.win._core_sqlite_denied(reason[0])
                self.assertIn(notice,self.win.status.text())
                self.assertIn("NO IMPORT",self.win.status.text())
                self.assertFalse(self.win.dashboard.go_send.isEnabled())

    def test_wrong_network_and_fabricated_ready_are_rejected_before_wallet(self):
        good = public_status(state="ready",owned=True,chain_height=105)
        for update in ({"chain":"mainnet"},{"mainnet_allowed":True},
                       {"core_process_owned":False},{"height":None},
                       {"height":-1},{"state":"unknown"}):
            with self.subTest(update=update):
                self.win._apply_managed_status({**good,**update})
                self.assertFalse(self.win._managed_authenticated)
                self.assertIsNone(self.win._snapshot)
                self.assertIn("RECOVERY NEEDED",self.win.status.text())

    def test_close_does_not_invoke_core_shutdown_or_create_wallet(self):
        self.win._apply_managed_status(public_status(state="ready",owned=True,chain_height=101))
        with patch("wam_regtest.managed_gui.control",side_effect=AssertionError("Core touched")):
            self.assertTrue(self.win.close())
        self.assertEqual(self.win._managed_state,"ready")

    def test_stop_requires_explicit_confirmation(self):
        self.win._apply_managed_status(public_status(state="ready",owned=True,chain_height=101))
        with patch.object(QMessageBox,"question",return_value=QMessageBox.StandardButton.No):
            with patch.object(self.win,"_execute",side_effect=AssertionError("unapproved stop")):
                self.win._confirm_stop()

    def test_no_start_on_unverified_status(self):
        with patch.object(self.win,"_execute") as command:
            self.win._managed_denied("never display secret")
            self.win.start_core.click()
            command.assert_not_called()

    def test_verify_wallet_requires_opt_in_resources_and_ready_supervisor(self):
        self.win._apply_managed_status(public_status(
            state="ready",owned=True,chain_height=101))
        self.assertFalse(self.win.verify_wallet_button.isEnabled())
        self.win._wallet_core_dir=Path.cwd()/"pinned-core"
        self.win._wallet_wsp_source=Path.cwd()/"pinned-wsp"
        self.win._update_controls()
        self.assertTrue(self.win.verify_wallet_button.isEnabled())
        with patch("wam_regtest.managed_gui.QInputDialog.getText",
                   return_value=("test-only-regtest-password",False)) as dialog:
            self.win.verify_wallet_button.click()
            self.assertEqual(dialog.call_count,1)
            self.assertIsNone(self.win._worker)
        self.win._managed_denied("untrusted")
        self.assertFalse(self.win.verify_wallet_button.isEnabled())
        self.assertFalse(self.win._wallet_checkpoint_verified)

    def test_locked_wallet_verification_never_grants_balance_or_spending(self):
        proof={
            "status":"MANAGED_WALLET_ORIGINAL_CHECKPOINT_VERIFIED_LOCKED",
            "network":"regtest","wallet_locked":True,
            "signer_allowed":False,"broadcast_allowed":False,
            "balance_verified":False,"original_native_anchor_verified":True,
            "original_encrypted_checkpoint_verified":True,
            "mainnet_allowed":False,"supervisor_authenticated":True,
            "supervisor_core_identity_verified":True,
        }
        self.win._apply_managed_status(public_status(
            state="ready",owned=True,chain_height=101))
        self.win._apply_wallet_preflight(proof)
        self.assertTrue(self.win._wallet_checkpoint_verified)
        self.assertIn("WALLET STILL LOCKED",self.win.status.text())
        self.assertIsNone(self.win.session)
        self.assertIsNone(self.win._snapshot)
        self.assertFalse(self.win.dashboard.go_send.isEnabled())
        for mutation in ({"signer_allowed":True},{"balance_verified":True},
                         {"mainnet_allowed":True},{"wallet_locked":False}):
            with self.subTest(mutation=mutation):
                self.win._apply_wallet_preflight({**proof,**mutation})
                self.assertFalse(self.win._wallet_checkpoint_verified)
                self.assertNotIn("WALLET STILL LOCKED",self.win.status.text())
                self.assertFalse(self.win.dashboard.go_send.isEnabled())
        self.win._apply_wallet_preflight(proof)
        self.win._apply_managed_status(public_status(
            state="busy",owned=True))
        self.assertFalse(self.win._wallet_checkpoint_verified)

    def test_native_worker_verifies_original_checkpoint_only_with_manual_password(self):
        import time
        from PySide6.QtWidgets import QLineEdit
        from PySide6.QtCore import QCoreApplication,QEvent
        from wam_regtest.managed_wallet_binding import verify_locked_wallet
        self.win._wallet_core_dir=Path.cwd()/"pinned-core"
        self.win._wallet_wsp_source=Path.cwd()/"pinned-wsp"
        self.win._apply_managed_status(public_status(
            state="ready",owned=True,chain_height=101))
        proof={
            "status":"MANAGED_WALLET_ORIGINAL_CHECKPOINT_VERIFIED_LOCKED",
            "network":"regtest","wallet_locked":True,
            "signer_allowed":False,"broadcast_allowed":False,
            "balance_verified":False,"original_native_anchor_verified":True,
            "original_encrypted_checkpoint_verified":True,
            "mainnet_allowed":False,"supervisor_authenticated":True,
            "supervisor_core_identity_verified":True,
        }
        with (patch("wam_regtest.managed_gui.QInputDialog.getText",
                    return_value=("public-regtest-password",True)),
              patch("wam_regtest.managed_wallet_binding.verify_locked_wallet",
                    return_value=proof) as locked):
            self.win.verify_wallet_button.click()
            self.assertIsNotNone(self.win._worker)
            self.assertFalse(self.win.close())
            deadline=time.monotonic()+5
            while self.win._worker is not None and time.monotonic()<deadline:
                self.app.processEvents()
                time.sleep(.005)
            self.assertIsNone(self.win._worker)
            QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
            self.assertTrue(self.win._wallet_checkpoint_verified)
            self.assertEqual(locked.call_count,1)
            self.assertEqual(locked.call_args.kwargs,{"authorized":True})
        self.assertIsNone(self.win.session)
        self.assertIsNone(self.win._snapshot)
        self.assertFalse(self.win.dashboard.go_send.isEnabled())


    def _original_wallet_fixture(self):
        from wam_sp.keystore import ScanAccount
        from wam_sp.core import pub
        from wam_regtest.wallet_read import WalletReadSnapshot,HistoryRow
        code=ScanAccount(0,1,pub(2),birthday=1).payment_code()
        return WalletReadSnapshot(
            chain="regtest",height=101,tip="b"*64,receive_code=code,
            confirmed_atoms=27000,confirmed_utxos=1,
            history=(HistoryRow("a"*64,101,1,27000,0),),
            core_sha256="c"*64,synthetic_rpc=False,demo_account_only=False,
            signer_allowed=False,broadcast_allowed=False,mainnet_allowed=False)

    def test_original_wallet_snapshot_never_adopted_without_manual_approval(self):
        snap=self._original_wallet_fixture()
        self.win._apply_managed_status(public_status(
            state="ready",owned=True,chain_height=101))
        self.win._apply_wallet_snapshot(snap)
        self.assertIsNone(self.win._snapshot)
        self.assertFalse(self.win.dashboard.go_send.isEnabled())
        self.assertIn("UNVERIFIED",self.win.status.text())
        self.assertFalse(self.win._wallet_read_authorized)

    def test_valid_original_wallet_renders_real_readonly_pages_no_spending(self):
        snap=self._original_wallet_fixture()
        self.win._apply_managed_status(public_status(
            state="ready",owned=True,chain_height=101))
        self.win._wallet_read_authorized=True
        self.win._apply_wallet_snapshot(snap)
        self.assertIs(self.win._snapshot,snap)
        self.assertTrue(self.win._wallet_checkpoint_verified)
        self.assertEqual(self.win.receive_page.code,snap.receive_code)
        self.assertIsNone(self.win.session)
        self.assertFalse(self.win.dashboard.go_send.isEnabled())
        self.assertIn("signing/broadcast DISABLED",self.win.status.text())
        self.assertEqual(self.win._sync_timer.interval(),30_000)
        # Any authenticated status refresh removes stale verified balances,
        # even when the observed block height is unchanged.
        self.win._apply_managed_status(public_status(
            state="ready",owned=True,chain_height=101))
        self.assertIsNone(self.win._snapshot)
        self.assertFalse(self.win._wallet_checkpoint_verified)
        self.assertFalse(self.win.dashboard.go_send.isEnabled())
        self.assertEqual(self.win._sync_timer.interval(),5_000)

    def test_reject_fabricated_demo_mainnet_signer_or_wrong_height(self):
        from dataclasses import replace
        snap=self._original_wallet_fixture()
        self.win._apply_managed_status(public_status(
            state="ready",owned=True,chain_height=101))
        cases=(
            {"demo_account_only":True},{"synthetic_rpc":True},
            {"signer_allowed":True},{"broadcast_allowed":True},
            {"mainnet_allowed":True},{"height":102},
            {"receive_code":"mainnet-wrong-address"},
            {"core_sha256":"unknown"},
        )
        for change in cases:
            with self.subTest(change=change):
                self.win._wallet_read_authorized=True
                self.win._apply_wallet_snapshot(replace(snap,**change))
                self.assertIsNone(self.win._snapshot)
                self.assertFalse(self.win._wallet_read_authorized)
                self.assertFalse(self.win.dashboard.go_send.isEnabled())
        # Never let the inherited public-demo path show any balance.
        from wam_regtest.wallet_read import WalletReadSnapshot
        self.win.apply_snapshot(replace(snap,demo_account_only=True))
        self.assertIsNone(self.win._snapshot)

    def test_native_manual_gui_wallet_scan_worker_and_clean_qthread_teardown(self):
        import time
        from PySide6.QtCore import QCoreApplication,QEvent
        from PySide6.QtWidgets import QLineEdit
        snap=self._original_wallet_fixture()
        self.win._wallet_core_dir=Path.cwd()/"pinned-core"
        self.win._wallet_wsp_source=Path.cwd()/"pinned-wsp"
        self.win._apply_managed_status(public_status(
            state="ready",owned=True,chain_height=101))
        self.assertTrue(self.win.view_wallet_button.isEnabled())
        with (patch("wam_regtest.managed_gui.QInputDialog.getText",
                    return_value=("public-test-only-regtest-password",True)) as dialog,
              patch("wam_regtest.managed_wallet_snapshot.read_managed_wallet_snapshot",
                    return_value=snap) as source):
            self.win.view_wallet_button.click()
            self.assertIsNotNone(self.win._worker)
            self.assertFalse(self.win.close())  # In-flight native QThread
            deadline=time.monotonic()+8
            while self.win._worker is not None and time.monotonic()<deadline:
                self.app.processEvents()
                time.sleep(.005)
            self.assertIsNone(self.win._worker)
            QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
            self.assertEqual(dialog.call_count,1)
            self.assertEqual(source.call_count,1)
            self.assertTrue(source.call_args.kwargs["authorized_readonly"])
            self.assertFalse(source.call_args.kwargs["authorized_persist_checkpoint"])
            self.assertIs(self.win._snapshot,snap)
            self.assertFalse(self.win.dashboard.go_send.isEnabled())
        self.assertTrue(self.win.close())

    def test_native_gui_wallet_scan_failure_redacts_secret_and_clears_balance(self):
        import time
        self.win._wallet_core_dir=Path.cwd()/"pinned-core"
        self.win._wallet_wsp_source=Path.cwd()/"pinned-wsp"
        self.win._apply_managed_status(public_status(
            state="ready",owned=True,chain_height=101))
        with (patch("wam_regtest.managed_gui.QInputDialog.getText",
                    return_value=("public-test-only-regtest-password",True)),
              patch("wam_regtest.managed_wallet_snapshot.read_managed_wallet_snapshot",
                    side_effect=ValueError("PRIVATE_SECRET_CANARY"))):
            self.win.view_wallet_button.click()
            deadline=time.monotonic()+8
            while self.win._worker is not None and time.monotonic()<deadline:
                self.app.processEvents()
                time.sleep(.005)
            self.assertIsNone(self.win._worker)
            self.assertIsNone(self.win._snapshot)
            self.assertFalse(self.win._wallet_checkpoint_verified)
            self.assertFalse(self.win.dashboard.go_send.isEnabled())
            self.assertNotIn("CANARY",self.win.status.text())
        self.assertTrue(self.win.close())


    def test_manual_create_original_wallet_and_explicit_read_only_gui_state(self):
        import time
        from PySide6.QtCore import QCoreApplication,QEvent
        proof={"status":"MANAGED_REGTEST_WSP_WALLET_CREATED_LOCKED",
               "network":"regtest","wallet_locked":True,
               "signer_allowed":False,"broadcast_allowed":False,
               "mainnet_allowed":False}
        self.win._wallet_core_dir=Path.cwd()/"pinned-core"
        self.win._wallet_wsp_source=Path.cwd()/"pinned-wsp"
        self.win._apply_managed_status(public_status(
            state="ready",owned=True,chain_height=101))
        self.assertTrue(self.win.create_wallet_button.isEnabled())
        with (patch.object(QMessageBox,"question",
                           return_value=QMessageBox.StandardButton.Yes),
              patch("wam_regtest.managed_gui.QInputDialog.getText",
                    side_effect=[("regtest-passphrase-only",True),
                                 ("regtest-passphrase-only",True)]),
              patch("wam_regtest.managed_wallet_create.create_managed_wallet",
                    return_value=proof) as create):
            self.win.create_wallet_button.click()
            self.assertIsNotNone(self.win._worker)
            deadline=time.monotonic()+6
            while self.win._worker is not None and time.monotonic()<deadline:
                self.app.processEvents()
                time.sleep(.005)
            self.assertIsNone(self.win._worker)
            QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
            create.assert_called_once()
            self.assertTrue(create.call_args.kwargs["authorized"])
            self.assertIsNone(self.win._snapshot)
            self.assertIsNone(self.win.session)
            self.assertFalse(self.win.dashboard.go_send.isEnabled())
            self.assertIn("CREATED AND ENCRYPTED",self.win.status.text())

    def test_create_mismatched_password_and_cancel_never_touch_custody(self):
        self.win._wallet_core_dir=Path.cwd()/"pinned-core"
        self.win._wallet_wsp_source=Path.cwd()/"pinned-wsp"
        self.win._apply_managed_status(public_status(
            state="ready",owned=True,chain_height=101))
        with patch("wam_regtest.managed_wallet_create.create_managed_wallet") as create:
            with patch.object(QMessageBox,"question",
                              return_value=QMessageBox.StandardButton.No):
                self.win.create_wallet_button.click()
            create.assert_not_called()
            with (patch.object(QMessageBox,"question",
                               return_value=QMessageBox.StandardButton.Yes),
                  patch("wam_regtest.managed_gui.QInputDialog.getText",
                        side_effect=[("regtest-one-password",True),
                                     ("regtest-other-password",True)])):
                self.win.create_wallet_button.click()
            create.assert_not_called()
        self.assertIsNone(self.win._snapshot)
        self.assertFalse(self.win.dashboard.go_send.isEnabled())

    def test_explicit_sync_saves_checkpoint_but_plain_view_does_not(self):
        import time
        from PySide6.QtCore import QCoreApplication,QEvent
        snap=self._original_wallet_fixture()
        self.win._wallet_core_dir=Path.cwd()/"pinned-core"
        self.win._wallet_wsp_source=Path.cwd()/"pinned-wsp"
        self.win._apply_managed_status(public_status(
            state="ready",owned=True,chain_height=101))
        for button,persist in ((self.win.view_wallet_button,False),
                               (self.win.sync_wallet_button,True)):
            with (patch("wam_regtest.managed_gui.QInputDialog.getText",
                        return_value=("regtest-passphrase-only",True)),
                  patch("wam_regtest.managed_wallet_snapshot.read_managed_wallet_snapshot",
                        return_value=snap) as reader):
                button.click()
                deadline=time.monotonic()+6
                while self.win._worker is not None and time.monotonic()<deadline:
                    self.app.processEvents()
                    time.sleep(.005)
                self.assertIsNone(self.win._worker)
                QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
                self.assertEqual(reader.call_count,1)
                self.assertIs(reader.call_args.kwargs["authorized_persist_checkpoint"],persist)
                self.assertIs(reader.call_args.kwargs["authorized_readonly"],True)
                self.assertIs(self.win._snapshot,snap)
                self.assertFalse(self.win.dashboard.go_send.isEnabled())

    def test_hidden_panels_already_belong_to_window(self):
        # A never-shown window must own every responsive panel immediately;
        # waiting for resizeEvent leaves native widgets outside its lifetime.
        from wam_regtest.fusion_ui import ResponsiveRow
        for row in self.win.findChildren(ResponsiveRow):
            for child in row._children:
                self.assertIs(child.parentWidget(), row)
                self.assertIs(child.window(), self.win)
        self.assertIs(self.win.dashboard.hero.window(), self.win)
        self.assertIs(self.win.receive_page.qr.window(), self.win)

    def test_close_waits_for_worker_then_stops_window_timers(self):
        import threading
        import time
        from PySide6.QtCore import QCoreApplication, QEvent
        from shiboken6 import isValid
        started, release = threading.Event(), threading.Event()
        def status(*args, **kwargs):
            started.set()
            if not release.wait(5):
                raise AssertionError("test worker was not released")
            return public_status(state="ready", owned=True, chain_height=101)
        # Supplemental lifetime fixture only. Genuine Core/IPC acceptance is
        # separately required by issue45_t05_real_core.py --qt-e2e.
        with patch("wam_regtest.managed_gui.control", side_effect=status):
            self.win.request_sync()
            worker = self.win._worker
            try:
                self.assertTrue(started.wait(3))
                self.assertFalse(self.win.close())
                self.assertTrue(worker.isRunning())
                self.assertTrue(self.win._sync_timer.isActive())
            finally:
                release.set()
                self.assertTrue(worker.wait(5000))
            deadline = time.monotonic() + 3
            while self.win._worker is not None and time.monotonic() < deadline:
                self.app.processEvents()
            self.assertIsNone(self.win._worker)
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            self.assertFalse(isValid(worker))
        self.assertTrue(self.win.close())
        self.assertFalse(self.win._sync_timer.isActive())
        self.assertFalse(self.win._theme_timer.isActive())
        self.assertFalse(self.win._appearance_connected)


class NativeQtLifetime(unittest.TestCase):
    def test_repeated_hidden_and_visible_gui_destruction_and_clean_process_exit(self):
        program = r'''
from pathlib import Path
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QWidget
from shiboken6 import delete, isValid
from wam_regtest.desktop import qt_application, shutdown_qt
from wam_regtest.managed_gui import ManagedCoreWindow
app = qt_application()
root = Path("C:/wam-fusion-core-0123456789abcdef" if __import__("sys").platform == "win32"
            else "/tmp/wam-fusion-core-0123456789abcdef")
for visible in (False, True) * 6:
    window = ManagedCoreWindow(root)
    assert qt_application() is app and QApplication.instance() is app
    assert window.dashboard.hero.window() is window
    assert window.receive_page.qr.window() is window
    if visible:
        window.show()
        app.processEvents()
        window.resize(900, 680)
        app.processEvents()
    children = window.findChildren(QWidget)
    assert window.close()
    assert not window._sync_timer.isActive() and not window._theme_timer.isActive()
    delete(window)
    assert not isValid(window) and all(not isValid(child) for child in children)
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
assert not QApplication.topLevelWidgets()
shutdown_qt()
assert not isValid(app) and QApplication.instance() is None
shutdown_qt()  # idempotent: no second native destruction
print("QT_LIFETIME_AND_SHUTDOWN_PASS", flush=True)
'''
        result = subprocess.run([sys.executable, "-X", "faulthandler", "-c", program],
                                env=os.environ.copy(), capture_output=True,
                                text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr[-5000:])
        self.assertIn("QT_LIFETIME_AND_SHUTDOWN_PASS", result.stdout)


# K-01: GUI-only suites are run on Qt-equipped native runners, not the
# Linux non-GUI test_v1 contracts runner.
from PySide6.QtWidgets import QDialog
from mnemonic import Mnemonic
from wam_regtest.bip39_gui import Bip39CreationDialog

PUBLIC_12=Mnemonic("english").to_mnemonic(bytes(16))
PUBLIC_24=Mnemonic("english").to_mnemonic(bytes(32))


class Bip39WizardContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=qt_application()

    def make(self, words=12):
        dialog=Bip39CreationDialog()
        self.addCleanup(self.cleanup_dialog,dialog)
        dialog.word_count.setCurrentIndex(0 if words==12 else 1)
        self.assertFalse(dialog.generate_button.isEnabled())
        dialog.ack.setChecked(True)
        self.assertTrue(dialog.generate_button.isEnabled())
        return dialog

    def cleanup_dialog(self,dialog):
        from shiboken6 import delete,isValid
        if isValid(dialog):
            dialog.reject()
            delete(dialog)
            self.app.processEvents()

    def test_creation_does_not_claim_a_wallet_or_persist_seed(self):
        dialog=self.make(12)
        with patch("wam_regtest.bip39_gui.generate_phrase",
                   return_value=PUBLIC_12) as generate:
            dialog._generate()
        generate.assert_called_once_with(12,authorized_disposable=True)
        self.assertIn("NOT LINKED",dialog.warning.text())
        self.assertIn("NOT A CREATED",dialog.status.text())
        self.assertEqual(dialog._phase,"show")
        self.assertEqual(len(dialog._phrase.split()),12)
        self.assertFalse(dialog.word_count.isEnabled())
        self.assertFalse(dialog.words_view.textInteractionFlags())
        # The same dialog cannot secretly rotate/reissue a new recovery phrase.
        with patch("wam_regtest.bip39_gui.generate_phrase",
                   side_effect=AssertionError("SECRET_ROTATION")) as gen:
            dialog._generate()
            gen.assert_not_called()
        self.assertFalse(dialog.confirmed)
        dialog.reject()
        self.assertIsNone(dialog._phrase)
        self.assertEqual(dialog.words_view.text(),"")
        self.assertEqual(dialog.confirm_text.toPlainText(),"")
        self.assertEqual(dialog.result(),QDialog.DialogCode.Rejected)

    def test_full_24_word_backup_requires_exact_order_and_passphrase(self):
        dialog=self.make(24)
        with patch("wam_regtest.bip39_gui.generate_phrase",return_value=PUBLIC_24):
            dialog._generate()
        dialog._advance()
        self.assertEqual(dialog.words_view.text(),"")
        self.assertIsNotNone(dialog._phrase)
        self.assertEqual(dialog._phase,"confirm")
        # A checksum-valid but different 24-word phrase must not pass.
        dialog.confirm_text.setPlainText(PUBLIC_12)
        dialog._verify()
        self.assertFalse(dialog.confirmed)
        self.assertEqual(dialog.confirm_text.toPlainText(),"")
        # Matching recovery phrase with an unacknowledged optional passphrase
        # must still refuse, never generate/persist a wallet.
        dialog.confirm_text.setPlainText(PUBLIC_24)
        dialog.passphrase.setText("public-TREZOR-passphrase")
        dialog.passphrase_confirmation.setText("public-TREZOR-passphrase")
        dialog._verify()
        self.assertFalse(dialog.confirmed)
        self.assertEqual(dialog.passphrase.text(),"")
        dialog.confirm_text.setPlainText(PUBLIC_24)
        dialog.passphrase.setText("public-TREZOR-passphrase")
        dialog.passphrase_confirmation.setText("different")
        dialog.extra_ack.setChecked(True)
        dialog._verify()
        self.assertFalse(dialog.confirmed)
        dialog.confirm_text.setPlainText(PUBLIC_24)
        dialog.passphrase.setText("public-TREZOR-passphrase")
        dialog.passphrase_confirmation.setText("public-TREZOR-passphrase")
        dialog._verify()
        self.assertTrue(dialog.confirmed)
        self.assertEqual(dialog.result(),QDialog.DialogCode.Accepted)
        self.assertIsNone(dialog._phrase)
        self.assertEqual(dialog.words_view.text(),"")
        self.assertEqual(dialog.confirm_text.toPlainText(),"")
        self.assertEqual(dialog.passphrase.text(),"")
        self.assertEqual(dialog.passphrase_confirmation.text(),"")
        self.assertEqual(repr(dialog),"<Bip39CreationDialog redacted>")

    def test_empty_passphrase_and_unconfirmed_accept_are_distinct(self):
        dialog=self.make(12)
        dialog.accept()
        self.assertNotEqual(dialog.result(),QDialog.DialogCode.Accepted)
        with patch("wam_regtest.bip39_gui.generate_phrase",return_value=PUBLIC_12):
            dialog._generate()
        dialog._advance()
        dialog.confirm_text.setPlainText(PUBLIC_12)
        dialog._verify()
        self.assertTrue(dialog.confirmed)
        self.assertIsNone(dialog._phrase)

    def test_k03_confirmed_mnemonic_handoff_is_one_time_new_wallet_only(self):
        dialog=Bip39CreationDialog(create_wallet=True)
        self.addCleanup(self.cleanup_dialog,dialog)
        dialog.word_count.setCurrentIndex(0)
        dialog.ack.setChecked(True)
        with patch("wam_regtest.bip39_gui.generate_phrase",return_value=PUBLIC_12):
            dialog._generate()
        dialog._advance()
        dialog.confirm_text.setPlainText(PUBLIC_12)
        dialog.passphrase.setText("K03-public-optional-passphrase")
        dialog.passphrase_confirmation.setText("K03-public-optional-passphrase")
        dialog.extra_ack.setChecked(True)
        dialog._verify()
        self.assertTrue(dialog.confirmed)
        self.assertIn("CREATE A NEW",dialog.warning.text())
        self.assertIsNone(dialog._phrase)
        self.assertEqual(dialog.words_view.text(),"")
        self.assertEqual(dialog.confirm_text.toPlainText(),"")
        phrase,passphrase=dialog.take_wallet_material()
        self.assertEqual(phrase,PUBLIC_12)
        self.assertEqual(passphrase,"K03-public-optional-passphrase")
        with self.assertRaises(ValueError):
            dialog.take_wallet_material()
        dialog.reject()
        self.assertIsNone(dialog._wallet_material)
        stand_alone=self.make(12)
        with self.assertRaises(ValueError):
            stand_alone.take_wallet_material()

    def test_k03_native_wsp_wallet_create_handoff_retains_verified_passphrase_once(self):
        dialog=Bip39CreationDialog(create_wallet=True)
        self.addCleanup(self.cleanup_dialog,dialog)
        self.assertIn("CREATE A NEW",dialog.warning.text())
        dialog.ack.setChecked(True)
        dialog.word_count.setCurrentIndex(0)
        with patch("wam_regtest.bip39_gui.generate_phrase",return_value=PUBLIC_12):
            dialog._generate()
        dialog._advance()
        dialog.confirm_text.setPlainText(PUBLIC_12)
        dialog.passphrase.setText("PUBLIC_REGTEST_BIP39_TEST_ONLY")
        dialog.passphrase_confirmation.setText("PUBLIC_REGTEST_BIP39_TEST_ONLY")
        dialog.extra_ack.setChecked(True)
        dialog._verify()
        self.assertTrue(dialog.confirmed)
        phrase,passphrase=dialog.take_wallet_material()
        self.assertEqual(phrase,PUBLIC_12)
        self.assertEqual(passphrase,"PUBLIC_REGTEST_BIP39_TEST_ONLY")
        self.assertIsNone(dialog._phrase)
        self.assertEqual(dialog.passphrase.text(),"")
        with self.assertRaisesRegex(ValueError,"K03_WALLET_MATERIAL_UNVERIFIED"):
            dialog.take_wallet_material()
        # No BIP39 material is returned through a UI status/signal.

    def test_k03_cancel_never_hands_off_bip39_seed_or_passphrase(self):
        dialog=Bip39CreationDialog(create_wallet=True)
        self.addCleanup(self.cleanup_dialog,dialog)
        dialog.ack.setChecked(True)
        with patch("wam_regtest.bip39_gui.generate_phrase",return_value=PUBLIC_24):
            dialog._generate()
        dialog.reject()
        with self.assertRaises(ValueError):
            dialog.take_wallet_material()
        self.assertIsNone(dialog._wallet_material)

    def test_wordlist_failure_clears_ui_without_core_or_fallback(self):
        dialog=self.make()
        with patch("wam_regtest.bip39_gui.generate_phrase",
                   side_effect=ValueError("PRIVATE_INTERNAL_CANARY")):
            dialog._generate()
        self.assertIsNone(dialog._phrase)
        self.assertNotIn("PRIVATE_INTERNAL_CANARY",dialog.status.text())
        self.assertNotIn("PRIVATE_INTERNAL_CANARY",repr(dialog))
        self.assertFalse(dialog.confirmed)
        self.assertEqual(dialog.words_view.text(),"")
