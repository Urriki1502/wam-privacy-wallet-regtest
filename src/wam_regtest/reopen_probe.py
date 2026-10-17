"""Reopen an anchored encrypted test-key backup on a different actual Core session."""
from pathlib import Path
import sys
from PySide6.QtCore import QCoreApplication,QEvent
from .desktop import qt_application
from .operational_gui import OperationalWalletWindow
from .wallet_session import WalletSession


class ReopenProbeError(ValueError):
    pass


def probe_reopened_wallet(core_dir,datadir,source,mining_address,case,*,read_rpc):
    directory,name,password,keychain,expected_code=case
    session=window=None
    try:
        if sys.platform=='win32':print('WIN_REOPEN_STAGE=FROM_BACKUP',flush=True)
        session=WalletSession.from_backup(core_dir,datadir,source,directory,name,password,
                                           mining_address,authorized=True,keychain=keychain,read_rpc=read_rpc)
        if sys.platform=='win32':print('WIN_REOPEN_STAGE=SNAPSHOT',flush=True)
        from .http_session_probe import prove_session_reads
        http_proof=prove_session_reads(session)
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
        assert window.navigation.count()==7
        assert 'treasury excluded' in window.mining_page.state.text()
        stale_proof={'stale_before_native_signature_denied':False,
                     'stale_before_real_broadcast_denied':False}
        if sys.platform in ('win32','darwin'):
            # Window close locks its session. Exercise stale writers while
            # the actual recovered wallet is open, then close it normally.
            window._sync_timer.stop()
            print('NATIVE_REOPEN_STAGE=STALE_PAYMENT',flush=True)
            stale_proof=_prove_native_stale_payment(session,password,keychain=keychain)
        window.close()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        window=None
        return {
            **stale_proof,
            'status':('REAL_CORE_CROSS_SESSION_CREDENTIAL_BACKUP_REOPEN_PASS' if sys.platform=='win32' else 'REAL_CORE_CROSS_SESSION_KEYCHAIN_BACKUP_REOPEN_PASS'),
            'operational_snapshot_http':http_proof,
            'real_core_rpc':True,'synthetic_rpc':False,'mainnet_allowed':False,
            'same_test_keys_recovered':True,'old_reservations_retained':True,
            'fresh_chain_rescanned_before_balance':True,'new_testing_epoch_funded':True,
            'native_qt_recovered_receive_balance':True,'observed_height':103,
            'cross_mac_anchor_migration_allowed':False,
        }
    except Exception as error:
        from .acceptance_failure import failure_site
        print('REOPEN_FAILURE_SITE='+failure_site(error),flush=True)
        raise ReopenProbeError('WALLET_REAL_CORE_REOPEN_DENIED') from None
    finally:
        if window is not None:
            window.close()
        if session is not None:
            session.close()


def _prove_native_stale_payment(session,password,*,keychain=None):
    """Real same-wallet writer advances from another private vault directory.

    Exercise both pre-sign and pre-broadcast rejection against a genuine Core
    session. Instrument native entry only; never substitute crypto or RPC.
    """
    from . import custody
    from .vault import CheckpointVault
    from .wallet_session import WalletSessionError, WalletCoreCli
    from wam_sp.wallet import Signer, Wallet
    from unittest.mock import patch
    if sys.platform=='darwin' and (
            type(keychain) is not type(Path()) or not keychain.is_absolute()
            or session.vault.anchor.keychain!=keychain):
        # This probe must NEVER fall back to the operator's default Keychain.
        raise ReopenProbeError('REOPEN_DISPOSABLE_KEYCHAIN_REQUIRED')
    storage=custody.storage()
    root=session.datadir
    def competing_vault(suffix):
        directory=root/suffix;custody.create_directory(directory)
        record=session.vault.anchor.read()
        storage.publish(directory,session.vault._filename(record[0]),
            storage.read(session.vault.directory,session.vault._filename(record[0])))
        vault=CheckpointVault(directory,custody.anchor(session.vault.anchor.wallet_id,keychain),session.source)
        ring,scan=vault.restore(root/(suffix+'.sqlite'),password)
        scan.sync(session._rpc())
        return vault,ring,scan
    label='MAC' if sys.platform=='darwin' else 'WIN'
    print(label+'_STALE_STAGE=PREPARE',flush=True)
    review=session.prepare(session.ring.accounts()[0].payment_code(),100000,10000)
    proposal=session._prepared.proposal
    print(label+'_STALE_STAGE=CLONE_BEFORE_SIGN',flush=True)
    other,ring,scan=competing_vault('stale-before-sign')
    try:
        print(label+'_STALE_STAGE=ADVANCE_BEFORE_SIGN',flush=True)
        other.save(ring,scan,password)
        entered=[];original=Signer.sign
        def tracked_sign(*args,**kwargs):
            entered.append(True);return original(*args,**kwargs)
        with patch.object(Signer,'sign',tracked_sign):
            try:session.sign(review.commitment)
            except WalletSessionError as error:assert str(error)=='WALLET_STALE_SESSION_DENIED'
            else:raise ValueError('STALE_SIGNATURE_ACCEPTED')
        assert not entered and session.faulted
        # This exact fixture draft never entered signing. Native WSP permits
        # unsigned cancellation; no signed/uncertain lock is released.
        print(label+'_STALE_STAGE=CANCEL_UNSIGNED',flush=True)
        Wallet(scan).release_draft(proposal.token)
        other.save(ring,scan,password)
        latest=root/'stale-recovery-backup';custody.create_directory(latest)
        other.backup(latest,'recovery.enc')
        print(label+'_STALE_STAGE=RECOVER_CURRENT',flush=True)
        session.lock();session.recover_backup(latest,'recovery.enc',password)
    finally:scan.close();ring.close()
    review=session.prepare(session.ring.accounts()[0].payment_code(),100000,10000)
    print(label+'_STALE_STAGE=POSITIVE_NATIVE_SIGN',flush=True)
    session.sign(review.commitment)  # Actual native signature, positive control.
    print(label+'_STALE_STAGE=CLONE_BEFORE_BROADCAST',flush=True)
    other,ring,scan=competing_vault('stale-before-broadcast')
    try:
        other.save(ring,scan,password)
        submitted=[];original=WalletCoreCli.call
        def tracked_call(client,method,params=None):
            if method=='sendrawtransaction':submitted.append(True)
            return original(client,method,params)
        with patch.object(WalletCoreCli,'call',tracked_call):
            try:session.broadcast(review.commitment)
            except WalletSessionError as error:assert str(error)=='WALLET_STALE_SESSION_DENIED'
            else:raise ValueError('STALE_BROADCAST_ACCEPTED')
        assert not submitted and session.faulted
        states={row[0] for row in scan.store.db.execute('SELECT state FROM reservations')}
        assert 'signed' in states and states <= {'signed','broadcast','uncertain'}
        try:Wallet(scan).release_draft(session._prepared.proposal.token)
        except ValueError:pass
        else:raise ValueError('SIGNED_RESERVATION_RELEASED')
    finally:scan.close();ring.close()
    return {'stale_before_native_signature_denied':True,
            'stale_before_real_broadcast_denied':True,
            'stale_writer_same_wallet_other_vault_directory':True,
            'stale_writer_signed_reservation_retained':True}
