"""Actual Linux Core + shared headless frontend, no Qt/mock blockchain."""
from pathlib import Path
import sys
from unittest.mock import patch
from . import custody
from .linux_headless import HeadlessWallet,open_session
from .wallet_session import WalletSession,WalletCoreCli,WalletSessionError
from .vault import CheckpointVault
from .core import smoke_real_core

PASSWORD=b'public-disposable-linux-e2e-password'


def denied(action):
    try:action()
    except ValueError:return
    raise WalletSessionError('LINUX_NEGATIVE_SECURITY_GATE_ACCEPTED')


def locks(session):
    return tuple(tuple(row) for row in session.scanner.store.db.execute(
        "SELECT txid,vout,token,state FROM reservations WHERE state!='draft' ORDER BY txid,vout"))


def probe(core,datadir,source,mining,*,read_rpc):
    from wam_sp.keystore import Keyring
    from wam_sp.scanner import Scanner
    from wam_sp.wallet import Signer
    session=receiver=receiver_scan=None
    stage='CREATE'
    try:
        print('LINUX_HEADLESS_STAGE='+stage,flush=True)
        session=WalletSession.create(core,datadir,source,PASSWORD,mining,authorized=True,read_rpc=read_rpc)
        from .http_session_probe import prove_session_reads
        http_proof=prove_session_reads(session)
        front=HeadlessWallet(session);initial=session.snapshot();original_accounts=session.ring.accounts()
        assert initial.height==103 and initial.confirmed_utxos==1 and initial.history
        receiver=Keyring();code=receiver.accounts()[0].payment_code()
        receiver_scan=Scanner(datadir/'recipient.sqlite',receiver.accounts())
        review=front.prepare(code,'0.00100000','0.00010000')
        denied(lambda:front.sign(''));assert session._signed is None
        stage='SIGN';print('LINUX_HEADLESS_STAGE='+stage,flush=True)
        original_sign=Signer.sign;observed={}
        def checked_sign(signer,*args):
            other=custody.anchor(session.vault.anchor.wallet_id)
            denied(other.read)
            path=datadir/'before-sign.sqlite'
            ring,scan=session.vault.restore(path,PASSWORD)
            try:
                states=[r[0] for r in scan.store.db.execute('SELECT state FROM reservations')]
                assert states and all(s=='signed' for s in states)
                observed['anchored_before_crypto']=True
            finally:scan.close();ring.close();path.unlink()
            return original_sign(signer,*args)
        with patch.object(Signer,'sign',checked_sign):front.sign('SIGN '+review.commitment)
        assert observed['anchored_before_crypto']
        denied(lambda:front.broadcast(''));rpc=session._rpc()
        txid=front.broadcast('BROADCAST '+review.commitment)
        assert txid in rpc._call('getrawmempool',[])
        confirmed=session.mine();receiver_scan.sync(rpc)
        assert confirmed.height==104 and confirmed.confirmed_atoms==initial.confirmed_atoms-110000
        assert sum(c['atoms'] for c in receiver_scan.coins())==100000
        held=locks(session);assert held
        stage='REORG';print('LINUX_HEADLESS_STAGE='+stage,flush=True)
        tip=confirmed.tip
        for depth in (1,12,100):
            block=rpc.call('getblockhash',[104-depth+1]);rpc._call('invalidateblock',[block])
            assert session.snapshot().height==104-depth and locks(session)==held
            rpc._call('reconsiderblock',[block]);assert session.snapshot().tip==tip and locks(session)==held
        stage='LOST_REPLY';print('LINUX_HEADLESS_STAGE='+stage,flush=True)
        review=front.prepare(code,'0.00100000','0.00010000');front.sign('SIGN '+review.commitment)
        actual_call=WalletCoreCli.call;accepted=[]
        def lost_reply(client,method,params=None):
            value=actual_call(client,method,params)
            if method=='sendrawtransaction':
                accepted.append(value)
                raise WalletSessionError('WALLET_BROADCAST_UNCERTAIN')
            return value
        with patch.object(WalletCoreCli,'call',lost_reply):
            denied(lambda:front.broadcast('BROADCAST '+review.commitment))
        assert session.faulted and len(accepted)==1 and accepted[0] in rpc._call('getrawmempool',[])
        retained=locks(session);assert any(row[3]=='uncertain' for row in retained)
        denied(session.cancel);session.lock();front.clear();session.unlock(PASSWORD)
        assert locks(session)==retained
        stage='BACKUP_RECOVER';print('LINUX_HEADLESS_STAGE='+stage,flush=True)
        backup=datadir/'backup';custody.create_directory(backup);session.backup(backup,'wallet-backup.enc')
        session.lock();denied(lambda:session.unlock(b'wrong-linux-password'))
        assert session.locked and not session.runtime.exists()
        session.recover_backup(backup,'wallet-backup.enc',PASSWORD)
        assert locks(session)==retained and session.ring.accounts()==original_accounts
        session.close();session=None
        stage='FRESH_CHAIN_STALE_SIGN';print('LINUX_HEADLESS_STAGE='+stage,flush=True)
        next_backup=datadir/'next-backup';custody.create_directory(next_backup)
        recovery=[]
        def reopen(backup_path,stale_broadcast):
            def driver(c,d,s,m,*,read_rpc):
                restored=open_session(c,d,s,m,PASSWORD,backup_path/'wallet-backup.enc',read_rpc=read_rpc)
                try:
                    snapshot=restored.snapshot()
                    assert snapshot.height==103 and restored.ring.accounts()[0]==original_accounts[0]
                    assert set(retained).issubset(set(locks(restored)))
                    frontend=HeadlessWallet(restored);prepared=frontend.prepare(code,'0.00100000','0.00010000')
                    if stale_broadcast:frontend.sign('SIGN '+prepared.commitment)
                    writer=CheckpointVault(restored.vault.directory,custody.anchor(restored.vault.anchor.wallet_id),s)
                    writer.save(restored.ring,restored.scanner,PASSWORD)
                    if stale_broadcast:
                        submitted=[]
                        def inspect_call(client,method,params=None):
                            if method=='sendrawtransaction':submitted.append(True)
                            return actual_call(client,method,params)
                        with patch.object(WalletCoreCli,'call',inspect_call):denied(lambda:frontend.broadcast('BROADCAST '+prepared.commitment))
                        assert not submitted
                    else:
                        called=[]
                        def inspect_sign(signer,*args):called.append(True);return original_sign(signer,*args)
                        with patch.object(Signer,'sign',inspect_sign):denied(lambda:frontend.sign('SIGN '+prepared.commitment))
                        assert not called
                    assert restored.faulted
                    restored.lock();restored.unlock(PASSWORD)
                    if not stale_broadcast:restored.backup(next_backup,'wallet-backup.enc')
                    recovery.append(True)
                    return {'fresh_chain_same_keys_and_reservations':True}
                finally:restored.close()
            return driver
        smoke_real_core(core,explicit_consent=True,wsp_source=source,wsp_payment_e2e=True,
            headless_callback=reopen(backup,False))
        smoke_real_core(core,explicit_consent=True,wsp_source=source,wsp_payment_e2e=True,
            headless_callback=reopen(next_backup,True))
        assert len(recovery)==2 and not any(n.startswith('PySide6') for n in sys.modules)
        return {'status':'REAL_LINUX_CORE_ROOT_WITNESS_HEADLESS_WALLET_E2E_PASS',
            'operational_snapshot_http':http_proof,
            'real_core_rpc':True,'synthetic_rpc':False,'mainnet_allowed':False,
            'confirmed_recipient_atoms':100000,'confirmed_sender_change':True,
            'actual_reorg_depths':[1,12,100],'fresh_chain_key_recovery':True,
            'irreversible_reservations_retained':True,'lost_actual_broadcast_reply_retained':True,
            'stale_before_native_sign_denied':True,'stale_before_broadcast_denied':True,
            'anchored_irreversible_before_crypto':True,'separate_sign_broadcast_approvals':True,
            'backup_lock_wrong_password_recovery':True,'qt_imported':False}
    except Exception as error:
        print('LINUX_HEADLESS_FAILED_STAGE='+stage,flush=True)
        raise
    finally:
        if session is not None:session.close()
        if receiver_scan is not None:receiver_scan.close()
        if receiver is not None:receiver.close()
