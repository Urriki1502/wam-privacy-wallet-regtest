"""Real-Core native Qt Send/Sign/Broadcast/backup recovery acceptance."""
from pathlib import Path
import subprocess
import secrets
import sys
from . import custody
from PySide6.QtCore import QEventLoop,QTimer,QCoreApplication,QEvent,Qt
from PySide6.QtWidgets import QApplication
from .fusion_pages import PaymentApproval
from .fusion_ui import fusion_palette
from .wallet_session import WalletSession, WalletSessionError, WalletCoreCli
from .operational_gui import OperationalWalletWindow
from .http_session_probe import forbid_core_cli_reads, prove_session_reads


class WalletProbeError(ValueError):
    pass


def _await_gui_idle(app,window):
    # Screenshot/theme events can overlap the real 30-second sync. Wait for
    # native completion instead of clicking a correctly disabled action.
    loop=QEventLoop();poll=QTimer();deadline=QTimer();deadline.setSingleShot(True)
    poll.timeout.connect(lambda:loop.quit() if window._worker is None else None)
    deadline.timeout.connect(loop.quit)
    poll.start(10);deadline.start(90_000)
    if window._worker is not None:loop.exec()
    poll.stop();deadline.stop()
    if window._worker is not None:raise WalletProbeError('WALLET_GUI_IDLE_TIMEOUT')


def _operation(app,window,action,trigger,*,denied=False):
    _await_gui_idle(app,window)
    loop=QEventLoop()
    result={}
    def success(name,value):
        if name==action:
            result['value']=value
            result['success']=True
            loop.quit()
    def failure(_code):
        result['denied']=True
        loop.quit()
    timer=QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    window.operation_completed.connect(success)
    window.operation_failed.connect(failure)
    timer.start(90_000)
    # Parsing failures may emit synchronously; connect and enter the loop first.
    QTimer.singleShot(0,trigger)
    loop.exec()
    timer.stop()
    window.operation_completed.disconnect(success)
    window.operation_failed.disconnect(failure)
    worker=window._worker
    if worker is not None:
        if not worker.wait(15_000):
            raise WalletProbeError("WALLET_GUI_THREAD_STUCK")
        app.processEvents()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    if (denied and not result.get('denied')) or (not denied and not result.get('success')):
        raise WalletProbeError("WALLET_GUI_OPERATION_"+action.upper()+"_DENIED")
    return result.get('value')


@forbid_core_cli_reads()
def background_snapshot(app,window):
    loop=QEventLoop();observed=[];failures=[]
    def ready(snap):
        # Stop at signal delivery, not after the nested loop returns: worker
        # teardown/processEvents may otherwise dispatch another 50ms timeout.
        window._sync_timer.stop()
        observed.append(snap);loop.quit()
    def denied(code):
        from .gui_errors import public_code
        window._sync_timer.stop()
        failures.append(public_code(code));loop.quit()
    deadline=QTimer();deadline.setSingleShot(True);deadline.timeout.connect(loop.quit)
    window.snapshot_updated.connect(ready);window.snapshot_failed.connect(denied)
    try:
        window._sync_timer.setInterval(50);deadline.start(15000);loop.exec()
        window._sync_timer.stop()
        if window._worker is not None:assert window._worker.wait(15000)
        app.processEvents();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        if len(observed)!=1 or window._worker is not None:
            print('QT_BACKGROUND_COUNT='+str(len(observed))+';BUSY='+str(window._worker is not None)+';SAFE_FAILURE='+(','.join(failures) or 'NONE'),flush=True)
        assert len(observed)==1 and window._worker is None
        return observed[0]
    finally:
        deadline.stop();window.snapshot_updated.disconnect(ready);window.snapshot_failed.disconnect(denied)
        window._sync_timer.setInterval(30000);window._sync_timer.start()


def probe_wallet(core_dir,datadir,source,mining_address,*,read_rpc):
    from wam_sp.keystore import Keyring
    from wam_sp.scanner import Scanner
    session=recipient=recipient_scan=window=None
    keychain=datadir/'wallet-acceptance.keychain-db' if sys.platform=='darwin' else None
    created=False
    stage="KEYCHAIN"
    print("WALLET_E2E_STAGE=KEYCHAIN",flush=True)
    password=b"public-disposable-wallet-acceptance"
    try:
        if sys.platform=='darwin':
            status=subprocess.run(['/usr/bin/security','create-keychain','-p','public-test-only',str(keychain)],
                                   capture_output=True,timeout=15,check=False).returncode
            if status:raise WalletProbeError("WALLET_TEST_KEYCHAIN_DENIED")
            created=True
        stage="CREATE"
        print("WALLET_E2E_STAGE=CREATE",flush=True)
        session=WalletSession.create(core_dir,datadir,source,password,mining_address,authorized=True,keychain=keychain,read_rpc=read_rpc)
        stage="OWNED_HTTP_SNAPSHOTS"
        http_proof=prove_session_reads(session)
        initial=session.snapshot()
        assert initial.height==104 and initial.confirmed_utxos==1
        # Genuine same-owned-Core, same-datadir, same native anchor reopen.
        # This is an independently gated wallet/SQLite checkpoint unit; the
        # dedicated supervisor's cross-process RPC bridge remains unqualified.
        stage="MANAGED_WALLET_ORIGINAL_IDENTITY_REOPEN"
        original_accounts=tuple(session.ring.accounts())
        original_history=tuple(initial.history)
        original_anchor_id=session.vault.anchor.wallet_id
        assert session.enable_managed_reopen(authorized=True) is True
        assert (datadir/"wallet-vault"/"managed-reopen.enc").is_file()
        session.close()
        assert not (datadir/"wallet-runtime.sqlite").exists()
        session=WalletSession.reopen_managed(
            core_dir,datadir,source,password,mining_address,authorized=True,
            keychain=keychain,read_rpc=read_rpc)
        same_wallet=session.snapshot()
        assert session.vault.anchor.wallet_id==original_anchor_id
        assert tuple(session.ring.accounts())==original_accounts
        assert same_wallet.receive_code==initial.receive_code
        assert same_wallet.confirmed_atoms==initial.confirmed_atoms
        assert same_wallet.history==original_history
        assert same_wallet.tip==initial.tip
        assert same_wallet.mainnet_allowed is False
        print("WALLET_T05_REAL_CORE_ORIGINAL_IDENTITY_CHECKPOINT_REOPEN_PASS",flush=True)
        recipient=Keyring()
        code=recipient.accounts()[0].payment_code()
        from .desktop import qt_application
        app=qt_application()
        stage="QT_CREATE"
        window=OperationalWalletWindow(session)
        window.show()
        window.apply_snapshot(initial)
        stage="QT_VALIDATION"
        validation_cases=_validation_feedback_probe(app,window,session)
        assert window.navigation.count()==7 and window._sync_timer.isActive()
        assert window.navigation.item(6).text()=='Mining Account'
        assert window.mining_page.values['available_atoms'].text()=='0.00000000 WAM'
        assert 'treasury excluded' in window.mining_page.state.text()
        assert window.navigation.item(0).text()=="Overview"
        assert window.stack.widget(0) is window.dashboard
        assert window.dashboard.balance_value.text()==window.balance_text.text()
        assert window.dashboard.activity_table.rowCount()==min(6,len(initial.history))
        assert "REGTEST VERIFIED" in window.dashboard.live_badge.text()
        assert window.dashboard.go_send.isEnabled() and window.dashboard.open_security.isEnabled()
        assert window._sync_timer.interval()==30_000
        # Actual worker and timer, with CLI/full-Core hash paths forbidden.
        stage="QT_BACKGROUND"
        assert background_snapshot(app,window)==initial
        assert not window.sign_button.isEnabled() and not window.broadcast_button.isEnabled()
        stage='QT_APPEARANCE'
        for index,color in ((2,fusion_palette('dark')['bg']),(1,fusion_palette('light')['bg'])):
            window.appearance.setCurrentIndex(index)
            app.processEvents()
            assert color in window.styleSheet()
        window.appearance.setCurrentIndex(0)
        hints=app.styleHints()
        prior=hints.colorScheme()
        auto_verified=False
        if prior in (Qt.ColorScheme.Light,Qt.ColorScheme.Dark):
            for scheme,color in ((Qt.ColorScheme.Dark,fusion_palette('dark')['bg']),(Qt.ColorScheme.Light,fusion_palette('light')['bg'])):
                hints.setColorScheme(scheme)
                app.processEvents()
                assert hints.colorScheme()==scheme and color in window.styleSheet()
            hints.setColorScheme(prior)
            app.processEvents()
            auto_verified=True
        window.recipient.setText(code)
        window.amount.setText("0.00100000")
        window.fee.setText("0.00010000")
        stage='NETWORK'
        network=_operation(app,window,'network',window.network_button.click)
        assert network['status']=='LOCAL_REGTEST_NETWORK_POLICY_PASS' and network['zero_peers'] is True
        assert network['clearnet_fallback_allowed'] is False
        assert "VERIFIED LOCAL REGTEST" in window.network_text.text()
        # Tamper only with this owned disposable node's config. The genuine
        # node remains alive; the wallet must deny before any CLI/fallback.
        original_config=(datadir/'wam.conf').read_bytes()
        try:
            (datadir/'wam.conf').write_bytes(original_config+b'proxy=127.0.0.1:9050\n')
            _operation(app,window,'network',window.network_button.click,denied=True)
            assert window._snapshot is None and window.balance_text.text()=='—'
        finally:
            (datadir/'wam.conf').write_bytes(original_config)
        network=_operation(app,window,'network',window.network_button.click)
        assert network['zero_peers'] is True
        window.apply_snapshot(session.snapshot())
        assert window.disclosure_record.count()==1 and window.disclosure_button.isEnabled()
        window.disclosure_fields['block_height'].setChecked(True)
        disclosure_txid=window.disclosure_record.currentData()
        _operation(app,window,'disclose',lambda:window.start_operation('disclose',disclosure_txid,('block_height',),b'wrong-test-passphrase'),denied=True)
        window.apply_snapshot(session.snapshot())
        assert window.disclosure_button.isEnabled()
        disclosed=_operation(app,window,'disclose',lambda:window.start_operation('disclose',disclosure_txid,('block_height',),password))
        assert disclosed['facts']=={'block_height':104} and disclosed['ownership_proof'] is False
        assert disclosure_txid not in window.disclosure_text.text() and 'credit_atoms' not in window.disclosure_text.text()
        window.navigation.setCurrentRow(4)
        assert window.grab().save(str(Path('real-regtest-security-preview.png').resolve()))
        window.navigation.setCurrentRow(3)
        stage="PREPARE"
        print("WALLET_E2E_STAGE=PREPARE",flush=True)
        review=_operation(app,window,'prepare',window.prepare_button.click)
        assert review.code==code and review.atoms==100000 and review.fee==10000
        assert str(review.atoms) in window.review_text.text() and code in window.review_text.text()
        assert window.sign_button.isEnabled() and not window.broadcast_button.isEnabled()
        # A rejected native approval must not enter signer or alter reservations.
        _approve_dialog(app,window,window.sign_button,approve=False)
        assert session._signed is None and window.sign_button.isEnabled()
        # Real Core integration: inspect the exact WSP-1 native PSBTv2
        # prepared from LIVE verified coins. BIP352 input-set changes require
        # fresh receiver output/proof derivation, not yet qualified; the
        # validation-only gate MUST fail closed without reserving new inputs,
        # signing, or broadcasting. Normal separately approved Send continues.
        stage="PAYJOIN_SAFETY"
        print("WALLET_E2E_STAGE=PAYJOIN_SAFETY",flush=True)
        from wam_sp.psbt import PSBT
        from .payjoin_safety import validate_live_payjoin_psbt_v2, PayjoinSafetyError
        native = session._prepared.psbt
        assert PSBT.decode(native).version == 2
        before = tuple(session.scanner.store.db.execute(
            "SELECT txid,vout,token,state FROM reservations ORDER BY txid,vout"
        ))
        try:
            validate_live_payjoin_psbt_v2(
                native, native,
                wallet_coins=session.scanner.coins(),
                live_rpc=session._rpc(),
            )
        except PayjoinSafetyError as denied:
            assert str(denied) == "PJ_BIP352_REDERIVATION_UNQUALIFIED"
        else:
            raise WalletProbeError("WALLET_BIP352_PAYJOIN_INCORRECTLY_AUTHORIZED")
        after = tuple(session.scanner.store.db.execute(
            "SELECT txid,vout,token,state FROM reservations ORDER BY txid,vout"
        ))
        assert after == before and session._signed is None
        assert window.sign_button.isEnabled() and not window.broadcast_button.isEnabled()
        stage="APPROVAL"
        print("WALLET_E2E_STAGE=APPROVAL",flush=True)
        try:
            session.sign('0'*64)
        except WalletSessionError:
            pass
        else:
            raise WalletProbeError("WALLET_CHANGED_APPROVAL_ACCEPTED")
        stage="SIGN"
        print("WALLET_E2E_STAGE=SIGN",flush=True)
        # Instrument the actual signer entry, then delegate to real native
        # crypto. No fake transaction, signature or RPC is substituted.
        from unittest.mock import patch
        from wam_sp.wallet import Signer
        from .vault import KeychainAnchor, VaultError
        original_sign=Signer.sign
        observed={}
        def checked_sign(signer,*args):
            other=custody.anchor(session.vault.anchor.wallet_id,keychain)
            try:
                with other.lease():
                    raise WalletProbeError("WALLET_SIGN_LEASE_NOT_HELD")
            except ValueError as error:
                assert str(error)==("WIN_ANCHOR_SESSION_BUSY" if sys.platform=="win32" else "VAULT_SESSION_BUSY")
            path=datadir/'before-native-sign.sqlite'
            recovered_ring,recovered_scan=session.vault.restore(path,password)
            try:
                rows=recovered_scan.store.db.execute('SELECT state FROM reservations').fetchall()
                assert rows and all(r[0]=='signed' for r in rows)
                observed['before_crypto']=True
            finally:
                recovered_scan.close()
                recovered_ring.close()
                path.unlink()
            return original_sign(signer,*args)
        with patch.object(Signer,'sign',checked_sign):
            _operation(app,window,'sign',lambda:_approve_dialog(app,window,window.sign_button))
        assert observed.get('before_crypto') is True
        assert window.broadcast_button.isEnabled() and not window.cancel_button.isEnabled()
        stage="BROADCAST"
        print("WALLET_E2E_STAGE=BROADCAST",flush=True)
        txid=_operation(app,window,'broadcast',lambda:_approve_dialog(app,window,window.broadcast_button))
        assert txid in window.review_text.text()
        # Real Core's mempool/consensus must accept the exact native signature.
        rpc=session._rpc()
        assert txid in rpc._call('getrawmempool',[])
        window.apply_snapshot(session.snapshot())
        assert window._submitted_txid==txid and 'SUBMITTED' in window.status.text()
        stage="CONFIRM"
        print("WALLET_E2E_STAGE=CONFIRM",flush=True)
        confirmed=_operation(app,window,'mine',window.mine_button.click)
        expected=initial.confirmed_atoms-review.atoms-review.fee
        assert confirmed.height==105 and confirmed.confirmed_atoms==expected
        assert window._submitted_txid is None and 'CONFIRMED' in window.review_text.text()
        assert window.balance_text.text()==f'{expected/100_000_000:,.8f} WAM'
        assert window.history_table.rowCount()==2
        recipient_scan=Scanner(datadir/'recipient.sqlite',recipient.accounts())
        recipient_scan.sync(rpc)
        coins=recipient_scan.coins()
        assert len(coins)==1 and coins[0]['txid']==txid and coins[0]['atoms']==review.atoms
        # Real send-block reorg must remove debit/change and recipient receive;
        # signed/broadcast reservations remain irreversible during rollback.
        stage="REORG"
        print("WALLET_E2E_STAGE=REORG",flush=True)
        tip=rpc.call('getbestblockhash')
        rpc._call('invalidateblock',[tip])
        rolled=session.snapshot()
        recipient_scan.sync(rpc)
        assert rolled.confirmed_atoms==initial.confirmed_atoms and not recipient_scan.coins()
        assert session.scanner.store.db.execute("SELECT state FROM reservations").fetchone()[0]=='broadcast'
        rpc._call('reconsiderblock',[tip])
        restored=session.snapshot()
        assert restored.confirmed_atoms==expected and restored.height==105
        window.apply_snapshot(restored)
        stage="LOST_BROADCAST_REPLY"
        print("WALLET_E2E_STAGE=LOST_BROADCAST_REPLY",flush=True)
        # A second real payment spends confirmed change. Drop only the local
        # response AFTER genuine Core has accepted it; no synthetic RPC.
        _operation(app,window,'prepare',window.prepare_button.click)
        _capture_fusion_views(app,window)
        _operation(app,window,'sign',lambda:_approve_dialog(app,window,window.sign_button))
        from wam_sp.psbt import PSBT
        uncertain_txid=PSBT.decode(session._signed).txid()
        original_call=WalletCoreCli.call
        entered={}
        def lost_reply(client,method,params=None):
            if method=='sendrawtransaction':
                other=custody.anchor(session.vault.anchor.wallet_id,keychain)
                try:
                    with other.lease():
                        raise WalletProbeError("WALLET_BROADCAST_LEASE_NOT_HELD")
                except ValueError as error:
                    assert str(error)==("WIN_ANCHOR_SESSION_BUSY" if sys.platform=="win32" else "VAULT_SESSION_BUSY")
                path=datadir/'before-network.sqlite'
                recovered_ring,recovered_scan=session.vault.restore(path,password)
                try:
                    states={r[0] for r in recovered_scan.store.db.execute('SELECT state FROM reservations')}
                    assert 'uncertain' in states
                    entered['anchored_before_rpc']=True
                finally:
                    recovered_scan.close()
                    recovered_ring.close()
                    path.unlink()
                actual=original_call(client,method,params)
                assert actual==uncertain_txid
                raise WalletSessionError("WALLET_TEST_LOST_REPLY_AFTER_REAL_CORE")
            return original_call(client,method,params)
        with patch.object(WalletCoreCli,'call',lost_reply):
            _operation(app,window,'broadcast',lambda:_approve_dialog(app,window,window.broadcast_button),denied=True)
        assert entered.get('anchored_before_rpc') is True and session.faulted
        assert not window.prepare_button.isEnabled() and not window.broadcast_button.isEnabled()
        assert uncertain_txid in rpc._call('getrawmempool',[])
        _operation(app,window,'lock',window.lock_button.click)
        _operation(app,window,'unlock',lambda:window.start_operation('unlock',password))
        assert not session.faulted and not session.locked
        assert 'uncertain' in {r[0] for r in session.scanner.store.db.execute('SELECT state FROM reservations')}
        try:
            session.cancel()
        except WalletSessionError:
            pass
        else:
            raise WalletProbeError("WALLET_UNCERTAIN_RESERVATION_RELEASED")
        stage="BACKUP"
        print("WALLET_E2E_STAGE=BACKUP",flush=True)
        backup=datadir/'wallet-backup'
        custody.create_directory(backup)
        _operation(app,window,'backup',lambda:window.start_operation('backup',backup,'wallet-backup.enc'))
        stage="LOCK"
        print("WALLET_E2E_STAGE=LOCK",flush=True)
        _operation(app,window,'lock',window.lock_button.click)
        assert session.locked and not session.runtime.exists() and window.balance_text.text()=='—'
        assert window.dashboard.balance_value.text()=='—'
        assert window.dashboard.activity_table.rowCount()==0
        assert window.receive_page.qr.matrix is None and window.receive_page.code is None
        assert window.history_page.rows==() and not window.history_page.copy_button.isEnabled()
        assert window.dashboard.evidence_text.toolTip()==''
        assert initial.receive_code not in window.recipient.text() and code not in window.review_text.text()
        assert all(v.text()=='—' for v in window.mining_page.values.values())
        assert not window.dashboard.go_send.isEnabled()
        assert not window.prepare_button.isEnabled()
        assert 'block_height' not in window.disclosure_text.text() and session._disclosure_gate is None
        stage="PASSWORD"
        print("WALLET_E2E_STAGE=PASSWORD",flush=True)
        _operation(app,window,'unlock',lambda:window.start_operation('unlock',b'wrong-regtest-passphrase'),denied=True)
        assert session.locked
        stage="RECOVER"
        print("WALLET_E2E_STAGE=RECOVER",flush=True)
        final=_operation(app,window,'recover',lambda:window.start_operation('recover',backup,'wallet-backup.enc',password))
        assert final.confirmed_atoms==expected and final.height==105
        assert window.prepare_button.isEnabled()
        window.navigation.setCurrentRow(3)
        assert window.grab().save(str(Path('real-regtest-wallet-preview.png').resolve()))
        window.close()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        window=None
        stage="REOPEN_ON_NEW_CORE"
        print("WALLET_E2E_STAGE=REOPEN_ON_NEW_CORE",flush=True)
        from .core import smoke_real_core
        reopened=smoke_real_core(core_dir,explicit_consent=True,wsp_source=source,
                                 wsp_payment_e2e=True,
                                 recovery_case=(backup,'wallet-backup.enc',password,keychain,initial.receive_code))
        proof=reopened['recovery_live_core']
        assert proof['status']==('REAL_CORE_CROSS_SESSION_CREDENTIAL_BACKUP_REOPEN_PASS' if sys.platform=='win32' else 'REAL_CORE_CROSS_SESSION_KEYCHAIN_BACKUP_REOPEN_PASS')
        assert reopened['block_height']==103 and reopened['live_wamd_process_observed'] is True
        assert reopened['mainnet_allowed'] is False and reopened['node_sha256']==initial.core_sha256
        return {
            'status':('WIN64_REAL_CORE_NATIVE_QT_SEND_SIGN_BROADCAST_SECURITY_E2E_PASS' if sys.platform=='win32' else 'REAL_CORE_NATIVE_QT_SEND_SIGN_BROADCAST_SECURITY_E2E_PASS'),
            'real_core_rpc':True,'synthetic_rpc':False,'mainnet_allowed':False,
            'authenticated_selected_local_disclosure':True,'local_network_privacy_diagnostics':True,'disposable_test_keys_only':True,'native_qt_prepare_sign_broadcast':True,
            'native_psbtv2_payjoin_bip352_fail_closed':True,'payjoin_signing_authorized':False,'payjoin_transport_implemented':False,
            'operational_snapshot_http':http_proof,
            'exact_intent_approval_required':True,'real_core_mempool_accepted':True,
            'real_core_confirmed_recipient_atoms':100000,'native_sender_change_confirmed':True,
            'encrypted_reservations_before_network':True,'actual_send_reorg_depth':1,
            'irreversible_anchor_before_native_crypto':True,'sign_broadcast_os_lease_held':True,
            'real_core_lost_broadcast_reply_lock_retained':True,
            'uncertain_reservation_survives_unlock':True,
            'irreversible_reservations_survive_reorg':True,'native_qt_backup_lock_recovery':True,
            'wrong_unlock_password_denied':True,'background_sync_active':True,
            'background_sync_timer_live_core_verified':True,
            'background_sync_production_interval_ms':30000,'background_sync_test_interval_ms':50,
            'native_gui_navigation_pages':7,'observed_height':105,
            'qt_manual_light_dark_verified':True,'qt_auto_system_events_verified':auto_verified,
            'managed_original_wallet_reopen_real_core':True,
            'managed_original_scan_accounts_preserved':True,
            'managed_original_history_preserved':True,
            'managed_original_anchor_id_preserved':True,
            'cross_session_key_recovery':True,'cross_session_native_qt':True,
            'cross_session_recovery_proof':proof,
            'production_custody_qualified':False,
            'native_input_feedback_cases':validation_cases,'submitted_confirmation_feedback':True,
        }
    except WalletProbeError:
        raise
    except Exception as error:
        from .acceptance_failure import failure_site
        print('WALLET_FAILURE_SITE='+failure_site(error),flush=True)
        if error.__context__ is not None:
            print('WALLET_INNER_FAILURE_SITE='+failure_site(error.__context__),flush=True)
        raise WalletProbeError('WALLET_REAL_CORE_'+stage+'_DENIED') from None
    finally:
        if window is not None:
            worker=window._worker
            if worker is not None:
                worker.wait(15_000)
            QApplication.instance().processEvents()
            window.close()
        for item in (session,recipient_scan,recipient):
            if item is not None:
                item.close()
        if sys.platform=="win32" and session is not None:
            from .windows_vault_probe import _delete_fixture
            _delete_fixture(session.vault.anchor)
        if created:
            status=subprocess.run(['/usr/bin/security','delete-keychain',str(keychain)],
                                   capture_output=True,timeout=15,check=False).returncode
            if status:
                raise WalletProbeError('WALLET_TEST_KEYCHAIN_CLEANUP_DENIED')


def _approve_dialog(app,window,button,*,approve=True):
    # Drive the actual modal dialog as an explicit disposable-fixture operator.
    # No application test flag or authorization bypass is introduced.
    _await_gui_idle(app,window)
    assert button.isEnabled(), 'NATIVE_PAYMENT_ACTION_MUST_BE_READY'
    seen=[]
    def respond():
        dialog=QApplication.activeModalWidget()
        if isinstance(dialog,PaymentApproval):
            assert dialog.cancel.isDefault() and not dialog.approve.isDefault()
            # Emit the actual refresh timer inside the modal nested loop.
            # It must not start a worker or change the exact reviewed intent.
            review=window.review
            window._sync_timer.timeout.emit()
            window.request_sync()
            assert window._approval_open and window._worker is None and window.review is review
            seen.append(True)
            directory=Path('fusion-ui-review');directory.mkdir(exist_ok=True)
            import sys
            platform={'win32':'windows-x64','darwin':'macos-arm64','linux':'linux-x86_64'}[sys.platform]
            assert dialog.grab().save(str(directory/(platform+'-approval-'+('broadcast' if button is window.broadcast_button else 'sign')+'.png')))
            (dialog.approve if approve else dialog.cancel).click()
    QTimer.singleShot(80,respond)
    button.click()
    assert seen, 'NATIVE_PAYMENT_APPROVAL_DIALOG_REQUIRED'


def _capture_fusion_views(app,window):
    import json,sys
    directory=Path('fusion-ui-review');directory.mkdir(exist_ok=True)
    platform={'win32':'windows-x64','darwin':'macos-arm64','linux':'linux-x86_64'}[sys.platform]
    old_size=window.size();old_page=window.navigation.currentRow();old_mode=window.appearance.currentIndex()
    records=[];geometry=[]
    def capture(filename,requested):
        assert window.grab().save(str(directory/filename));records.append(filename)
        geometry.append({'file':filename,'requested_logical_size':list(requested),
            'actual_logical_size':[window.width(),window.height()],
            'device_pixel_ratio':window.devicePixelRatioF()})
    def settle():
        loop=QEventLoop();QTimer.singleShot(80,loop.quit);loop.exec()
        app.processEvents()
    try:
        window.resize(1280,800);window.appearance.setCurrentIndex(2)
        for index,name in enumerate(('overview','receive','history','send','security','settings','mining')):
            window.navigation.setCurrentRow(index)
            if index==2 and window.history_table.rowCount():window.history_table.selectRow(0)
            settle()
            filename=f'{platform}-dark-{name}-1280x800.png'
            capture(filename,(1280,800))
        window.navigation.setCurrentRow(0)
        for mode,index in (('light',1),('auto',0)):
            window.appearance.setCurrentIndex(index);settle()
            filename=f'{platform}-{mode}-overview-1280x800.png'
            capture(filename,(1280,800))
        window.appearance.setCurrentIndex(2)
        for width,height in ((1440,900),(1920,1080),(900,650)):
            window.resize(width,height);settle()
            filename=f'{platform}-dark-overview-{width}x{height}.png'
            capture(filename,(width,height))
        receipt={'platform':platform,'qt_platform':app.platformName(),'device_pixel_ratio':window.devicePixelRatioF(),
            'real_core_snapshot':True,'synthetic_rpc':False,'verified_height':window._snapshot.height,
            'screenshots':records,'capture_geometry':geometry,'visual_approval':'PENDING_HUMAN_REVIEW'}
        (directory/(platform+'-visual-receipt.json')).write_text(json.dumps(receipt,indent=2)+'\n')
    finally:
        window.resize(old_size);window.appearance.setCurrentIndex(old_mode);window.navigation.setCurrentRow(old_page);app.processEvents()


def _validation_feedback_probe(app,window,session):
    """Genuine session/worker failures, also executed inside final GUI binaries."""
    from .gui_errors import INPUT_ERRORS
    initial=session.snapshot()
    code=initial.receive_code
    cases=(('',code,'0.00010000','WALLET_INPUT_AMOUNT_INVALID'),
           ('0.00000001',code,'0.00010000','WALLET_INPUT_AMOUNT_INVALID'),
           ('0.00100000',code,'0','WALLET_INPUT_FEE_INVALID'),
           ('0.00100000',code,'0.01000001','WALLET_INPUT_FEE_INVALID'),
           ('0.00100000','not-an-address','0.00010000','WALLET_INPUT_RECIPIENT_INVALID'),
           ('0.00100000',code[:-1]+('q' if code[-1]!='q' else 'p'),'0.00010000','WALLET_INPUT_RECIPIENT_INVALID'),
           ('999999.00000000',code,'0.00010000','WALLET_INPUT_FUNDS_UNAVAILABLE'))
    rpc=session._rpc()
    for amount,recipient,fee,expected in cases:
        window.apply_snapshot(session.snapshot())
        window.recipient.setText(recipient);window.amount.setText(amount);window.fee.setText(fee)
        before=(tuple(tuple(r) for r in session.scanner.store.db.execute('SELECT * FROM reservations')),
                session.vault.anchor.read(),tuple(rpc._call('getrawmempool',[])))
        seen=[];handler=seen.append
        window.operation_failed.connect(handler)
        try:_operation(app,window,'prepare',window.prepare_button.click,denied=True)
        finally:window.operation_failed.disconnect(handler)
        after=(tuple(tuple(r) for r in session.scanner.store.db.execute('SELECT * FROM reservations')),
               session.vault.anchor.read(),tuple(rpc._call('getrawmempool',[])))
        assert seen==[expected] and expected in INPUT_ERRORS and before==after
        assert window._snapshot==initial and window.verification_badge.text().startswith('Last verified')
        assert not session.faulted and not session.locked and session._signed is None and session._prepared is None
    window.apply_snapshot(session.snapshot())
    assert window.verification_badge.text().startswith('Core verified')
    return len(cases)
