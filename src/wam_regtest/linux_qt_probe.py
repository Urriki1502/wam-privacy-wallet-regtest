"""Linux xcb Qt workers and approvals over genuine Core/WSP/root custody.

Headless acceptance independently covers deeper reorg/stale/uncertain paths.
This gate qualifies the existing frontend; it is not human desktop signoff.
"""
from pathlib import Path
from PySide6.QtCore import QEventLoop,QTimer,QCoreApplication,QEvent,Qt
from PySide6.QtWidgets import QApplication
from . import custody
from .desktop import qt_application
from .fusion_ui import fusion_palette
from .linux_headless import open_session
from .linux_headless_probe import locks
from .operational_gui import OperationalWalletWindow
from .wallet_probe import _operation,_approve_dialog,_capture_fusion_views
from .wallet_session import WalletSession

PASSWORD=b'public-disposable-linux-qt-acceptance'


def background_snapshot(app,window):
    loop=QEventLoop();observed=[]
    def ready(snap):observed.append(snap);loop.quit()
    def denied(_):loop.quit()
    deadline=QTimer();deadline.setSingleShot(True);deadline.timeout.connect(loop.quit)
    window.snapshot_updated.connect(ready);window.snapshot_failed.connect(denied)
    try:
        window._sync_timer.setInterval(50);deadline.start(15000);loop.exec()
        window._sync_timer.stop()
        if window._worker is not None:assert window._worker.wait(15000)
        app.processEvents();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        assert len(observed)==1 and window._worker is None
        return observed[0]
    finally:
        deadline.stop();window.snapshot_updated.disconnect(ready);window.snapshot_failed.disconnect(denied)
        window._sync_timer.setInterval(30000);window._sync_timer.start()


def probe(core,datadir,source,mining):
    from wam_sp.keystore import Keyring
    from wam_sp.scanner import Scanner
    from .core import smoke_real_core
    app=qt_application();session=window=receiver=scan=None;stage='CREATE'
    try:
        assert app.platformName()=='xcb','LINUX_NATIVE_XCB_REQUIRED'
        session=WalletSession.create(core,datadir,source,PASSWORD,mining,authorized=True)
        initial=session.snapshot();accounts=session.ring.accounts()
        assert initial.height==103 and initial.confirmed_utxos==1 and initial.history
        window=OperationalWalletWindow(session);window.show();window.apply_snapshot(initial)
        assert window.navigation.count()==6 and window._sync_timer.interval()==30000
        assert background_snapshot(app,window)==initial
        for index,mode in ((2,'dark'),(1,'light')):
            window.appearance.setCurrentIndex(index);app.processEvents()
            assert fusion_palette(mode)['bg'] in window.styleSheet()
        window.appearance.setCurrentIndex(0);app.processEvents()
        hints=app.styleHints();prior=hints.colorScheme()
        auto_events=False
        # Xvfb may report Unknown: record it; never claim OS appearance tested.
        if prior in (Qt.ColorScheme.Light,Qt.ColorScheme.Dark):
            try:
                for scheme,mode in ((Qt.ColorScheme.Dark,'dark'),(Qt.ColorScheme.Light,'light')):
                    hints.setColorScheme(scheme);app.processEvents()
                    assert hints.colorScheme()==scheme and fusion_palette(mode)['bg'] in window.styleSheet()
                auto_events=True
            finally:hints.setColorScheme(prior);app.processEvents()
        network=_operation(app,window,'network',window.network_button.click)
        assert network['zero_peers'] is True and network['clearnet_fallback_allowed'] is False
        receiver=Keyring();code=receiver.accounts()[0].payment_code()
        window.recipient.setText(code);window.amount.setText('0.00100000');window.fee.setText('0.00010000')
        stage='APPROVAL';print('LINUX_QT_STAGE='+stage,flush=True)
        review=_operation(app,window,'prepare',window.prepare_button.click)
        assert review.atoms==100000 and review.fee==10000 and not window.broadcast_button.isEnabled()
        before=tuple(session.scanner.store.db.execute('SELECT * FROM reservations'))
        _approve_dialog(app,window,window.sign_button,approve=False)
        assert session._signed is None and tuple(session.scanner.store.db.execute('SELECT * FROM reservations'))==before
        _capture_fusion_views(app,window)
        stage='SIGN_BROADCAST';print('LINUX_QT_STAGE='+stage,flush=True)
        _operation(app,window,'sign',lambda:_approve_dialog(app,window,window.sign_button))
        assert window.broadcast_button.isEnabled() and not window.cancel_button.isEnabled()
        _approve_dialog(app,window,window.broadcast_button,approve=False)
        assert not session._rpc()._call('getrawmempool',[])
        txid=_operation(app,window,'broadcast',lambda:_approve_dialog(app,window,window.broadcast_button))
        assert txid in session._rpc()._call('getrawmempool',[])
        confirmed=_operation(app,window,'mine',window.mine_button.click)
        assert confirmed.height==104 and confirmed.confirmed_atoms==initial.confirmed_atoms-110000
        assert window.history_table.rowCount()==2 and window._snapshot==confirmed
        scan=Scanner(datadir/'qt-recipient.sqlite',receiver.accounts());scan.sync(session._rpc())
        assert sum(c['atoms'] for c in scan.coins())==100000
        retained=locks(session);assert retained
        stage='BACKUP_LOCK_RECOVER';print('LINUX_QT_STAGE='+stage,flush=True)
        backup=datadir/'qt-backup';custody.create_directory(backup)
        _operation(app,window,'backup',lambda:window.start_operation('backup',backup,'wallet-backup.enc'))
        _operation(app,window,'lock',window.lock_button.click)
        assert session.locked and not session.runtime.exists() and window._snapshot is None
        assert not window.prepare_button.isEnabled() and not window.broadcast_button.isEnabled()
        assert window.history_table.rowCount()==0 and not window.recipient.text()
        _operation(app,window,'unlock',lambda:window.start_operation('unlock',b'wrong-test-password'),denied=True)
        assert session.locked and not session.runtime.exists()
        recovered=_operation(app,window,'recover',lambda:window.start_operation('recover',backup,'wallet-backup.enc',PASSWORD))
        assert recovered==confirmed and session.ring.accounts()==accounts and locks(session)==retained
        window.close();window.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);window=None;session=None
        stage='FRESH_CORE_REOPEN';print('LINUX_QT_STAGE='+stage,flush=True)
        def reopen(c,d,s,m):
            restored=open_session(c,d,s,m,PASSWORD,backup/'wallet-backup.enc');view=None
            try:
                assert restored.ring.accounts()[0]==accounts[0] and set(retained).issubset(set(locks(restored)))
                snap=restored.snapshot();assert snap.height==103
                view=OperationalWalletWindow(restored);view.show();view.apply_snapshot(snap)
                assert background_snapshot(app,view)==snap and view.prepare_button.isEnabled()
                return {'fresh_core_same_keys_reservations_native_qt':True}
            finally:
                if view is not None:view.close();view.deleteLater()
                restored.close();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        second=smoke_real_core(core,explicit_consent=True,wsp_source=source,wsp_payment_e2e=True,headless_callback=reopen)
        assert second['wallet_live_core']['fresh_core_same_keys_reservations_native_qt']
        return {'status':'REAL_LINUX_CORE_ROOT_WITNESS_NATIVE_QT_WALLET_E2E_PASS',
            'synthetic_rpc':False,'mainnet_allowed':False,'qt_platform':app.platformName(),
            'native_pages':6,'background_timer_live_core_verified':True,
            'separate_native_sign_broadcast_approvals':True,'cancel_is_default':True,
            'confirmed_recipient_atoms':100000,'confirmed_sender_change':True,
            'backup_lock_wrong_password_recovery':True,'fresh_core_same_keys_reservations':True,
            'manual_light_dark_verified':True,'qt_auto_events_verified':auto_events,
            'desktop_os_appearance_signoff':'PENDING_OPERATOR','visual_signoff':'PENDING_OPERATOR',
            'production_qualified':False}
    except Exception:
        print('LINUX_QT_FAILED_STAGE='+stage,flush=True)
        raise
    finally:
        if window is not None:
            if window._worker is not None:window._worker.wait(15000)
            app.processEvents();window.close()
        for item in (session,scan,receiver):
            if item is not None:item.close()
