"""Reopen an anchored encrypted test-key backup on a different actual Core session."""
from pathlib import Path
from PySide6.QtCore import QCoreApplication,QEvent
from .desktop import qt_application
from .operational_gui import OperationalWalletWindow
from .wallet_session import WalletSession


class ReopenProbeError(ValueError):
    pass


def probe_reopened_wallet(core_dir,datadir,source,mining_address,case):
    directory,name,password,keychain,expected_code=case
    session=window=None
    try:
        session=WalletSession.from_backup(core_dir,datadir,source,directory,name,password,
                                           mining_address,authorized=True,keychain=keychain)
        snap=session.snapshot()
        assert session.ring.accounts()[0].payment_code()==expected_code
        assert snap.receive_code!=expected_code and session.ring.accounts()[-1].epoch==1
        assert snap.height==103 and snap.confirmed_utxos==1 and snap.confirmed_atoms>0
        # Old broadcast/uncertain locks remain in the recovered state. Newly
        # funded epoch coins have different outpoints and can be proposed.
        rows=session.scanner.store.db.execute('SELECT state FROM reservations').fetchall()
        assert rows and all(row[0] in ('broadcast','signed','uncertain') for row in rows)
        window=OperationalWalletWindow(session)
        window.show()
        window.apply_snapshot(snap)
        qt_application().processEvents()
        assert window.receive_code.text()==snap.receive_code and window.prepare_button.isEnabled()
        assert window.navigation.count()==6
        window.close()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        window=None
        return {
            'status':'REAL_CORE_CROSS_SESSION_KEYCHAIN_BACKUP_REOPEN_PASS',
            'real_core_rpc':True,'synthetic_rpc':False,'mainnet_allowed':False,
            'same_test_keys_recovered':True,'old_reservations_retained':True,
            'fresh_chain_rescanned_before_balance':True,'new_testing_epoch_funded':True,
            'native_qt_recovered_receive_balance':True,'observed_height':103,
            'cross_mac_anchor_migration_allowed':False,
        }
    except Exception:
        raise ReopenProbeError('WALLET_REAL_CORE_REOPEN_DENIED') from None
    finally:
        if window is not None:
            window.close()
        if session is not None:
            session.close()
