"""Real-Core native Qt Send/Sign/Broadcast/backup recovery acceptance."""
from pathlib import Path
import subprocess
import secrets
from PySide6.QtCore import QEventLoop,QTimer,QCoreApplication,QEvent,Qt
from PySide6.QtWidgets import QApplication
from .wallet_session import WalletSession, WalletSessionError, WalletCoreCli
from .operational_gui import OperationalWalletWindow


class WalletProbeError(ValueError):
    pass


def _operation(app,window,action,trigger,*,denied=False):
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
    trigger()
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


def probe_wallet(core_dir,datadir,source,mining_address):
    from wam_sp.keystore import Keyring
    from wam_sp.scanner import Scanner
    session=recipient=recipient_scan=window=None
    keychain=datadir/'wallet-acceptance.keychain-db'
    created=False
    stage="KEYCHAIN"
    print("WALLET_E2E_STAGE=KEYCHAIN",flush=True)
    password=b"public-disposable-wallet-acceptance"
    try:
        status=subprocess.run(['/usr/bin/security','create-keychain','-p','public-test-only',str(keychain)],
                               capture_output=True,timeout=15,check=False).returncode
        if status:
            raise WalletProbeError("WALLET_TEST_KEYCHAIN_DENIED")
        created=True
        stage="CREATE"
        print("WALLET_E2E_STAGE=CREATE",flush=True)
        session=WalletSession.create(core_dir,datadir,source,password,mining_address,authorized=True,keychain=keychain)
        initial=session.snapshot()
        assert initial.height==104 and initial.confirmed_utxos==1
        recipient=Keyring()
        code=recipient.accounts()[0].payment_code()
        from .desktop import qt_application
        app=qt_application()
        window=OperationalWalletWindow(session)
        window.show()
        window.apply_snapshot(initial)
        assert window.navigation.count()==6 and window._sync_timer.isActive()
        assert window._sync_timer.interval()==30_000
        # Exercise an actual Qt timer-triggered background worker with live
        # Core. Accelerate only the test interval, then restore the real 30s.
        sync_loop=QEventLoop()
        sync_result={}
        def background_ready(snap):
            sync_result['snap']=snap
            sync_loop.quit()
        def background_denied(reason):
            sync_loop.quit()
        deadline=QTimer()
        deadline.setSingleShot(True)
        deadline.timeout.connect(sync_loop.quit)
        window.snapshot_updated.connect(background_ready)
        window.snapshot_failed.connect(background_denied)
        window._sync_timer.setInterval(50)
        deadline.start(15_000)
        sync_loop.exec()
        window._sync_timer.stop()
        deadline.stop()
        window.snapshot_updated.disconnect(background_ready)
        window.snapshot_failed.disconnect(background_denied)
        if window._worker is not None:
            assert window._worker.wait(15_000)
            app.processEvents()
        window._sync_timer.setInterval(30_000)
        window._sync_timer.start()
        assert sync_result.get('snap')==initial and window._worker is None
        assert not window.sign_button.isEnabled() and not window.broadcast_button.isEnabled()
        for index,color in ((2,'#10100F'),(1,'#F5F3EE')):
            window.appearance.setCurrentIndex(index)
            app.processEvents()
            assert color in window.styleSheet()
        window.appearance.setCurrentIndex(0)
        hints=app.styleHints()
        prior=hints.colorScheme()
        auto_verified=False
        if prior in (Qt.ColorScheme.Light,Qt.ColorScheme.Dark):
            for scheme,color in ((Qt.ColorScheme.Dark,'#10100F'),(Qt.ColorScheme.Light,'#F5F3EE')):
                hints.setColorScheme(scheme)
                app.processEvents()
                assert hints.colorScheme()==scheme and color in window.styleSheet()
            hints.setColorScheme(prior)
            app.processEvents()
            auto_verified=True
        window.recipient.setText(code)
        window.amount.setText("0.00100000")
        window.fee.setText("0.00010000")
        stage="PREPARE"
        print("WALLET_E2E_STAGE=PREPARE",flush=True)
        review=_operation(app,window,'prepare',window.prepare_button.click)
        assert review.code==code and review.atoms==100000 and review.fee==10000
        assert str(review.atoms) in window.review_text.text() and code in window.review_text.text()
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
            other=KeychainAnchor(session.vault.anchor.wallet_id,keychain)
            try:
                with other.lease():
                    raise WalletProbeError("WALLET_SIGN_LEASE_NOT_HELD")
            except VaultError as error:
                assert str(error)=="VAULT_SESSION_BUSY"
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
            _operation(app,window,'sign',window.sign_button.click)
        assert observed.get('before_crypto') is True
        assert window.broadcast_button.isEnabled() and not window.cancel_button.isEnabled()
        stage="BROADCAST"
        print("WALLET_E2E_STAGE=BROADCAST",flush=True)
        txid=_operation(app,window,'broadcast',window.broadcast_button.click)
        assert txid in window.review_text.text()
        # Real Core's mempool/consensus must accept the exact native signature.
        rpc=session._rpc()
        assert txid in rpc._call('getrawmempool',[])
        stage="CONFIRM"
        print("WALLET_E2E_STAGE=CONFIRM",flush=True)
        confirmed=_operation(app,window,'mine',window.mine_button.click)
        expected=initial.confirmed_atoms-review.atoms-review.fee
        assert confirmed.height==105 and confirmed.confirmed_atoms==expected
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
        _operation(app,window,'sign',window.sign_button.click)
        from wam_sp.psbt import PSBT
        uncertain_txid=PSBT.decode(session._signed).txid()
        original_call=WalletCoreCli.call
        entered={}
        def lost_reply(client,method,params=None):
            if method=='sendrawtransaction':
                other=KeychainAnchor(session.vault.anchor.wallet_id,keychain)
                try:
                    with other.lease():
                        raise WalletProbeError("WALLET_BROADCAST_LEASE_NOT_HELD")
                except VaultError as error:
                    assert str(error)=="VAULT_SESSION_BUSY"
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
            _operation(app,window,'broadcast',window.broadcast_button.click,denied=True)
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
        backup.mkdir(mode=0o700)
        _operation(app,window,'backup',lambda:window.start_operation('backup',backup,'wallet-backup.enc'))
        stage="LOCK"
        print("WALLET_E2E_STAGE=LOCK",flush=True)
        _operation(app,window,'lock',window.lock_button.click)
        assert session.locked and not session.runtime.exists() and window.balance_text.text()=='—'
        assert not window.prepare_button.isEnabled()
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
        assert proof['status']=='REAL_CORE_CROSS_SESSION_KEYCHAIN_BACKUP_REOPEN_PASS'
        assert reopened['block_height']==103 and reopened['live_wamd_process_observed'] is True
        assert reopened['mainnet_allowed'] is False and reopened['node_sha256']==initial.core_sha256
        return {
            'status':'REAL_CORE_NATIVE_QT_SEND_SIGN_BROADCAST_SECURITY_E2E_PASS',
            'real_core_rpc':True,'synthetic_rpc':False,'mainnet_allowed':False,
            'disposable_test_keys_only':True,'native_qt_prepare_sign_broadcast':True,
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
            'native_gui_navigation_pages':6,'observed_height':105,
            'qt_manual_light_dark_verified':True,'qt_auto_system_events_verified':auto_verified,
            'cross_session_key_recovery':True,'cross_session_native_qt':True,
            'cross_session_recovery_proof':proof,
            'production_custody_qualified':False,
        }
    except WalletProbeError:
        raise
    except Exception:
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
        if created:
            status=subprocess.run(['/usr/bin/security','delete-keychain',str(keychain)],
                                   capture_output=True,timeout=15,check=False).returncode
            if status:
                raise WalletProbeError('WALLET_TEST_KEYCHAIN_CLEANUP_DENIED')
