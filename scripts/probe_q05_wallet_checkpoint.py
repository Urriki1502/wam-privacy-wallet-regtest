"""Bounded wallet create/reopen on a fresh signed macOS REGTEST owner.

Uses a new disposable Keychain only. Optional explicitly requested public
fixture funding is probe-only, never product onboarding. No existing wallet,
GUI, default Keychain changes, control-IPC secrets or full acceptance claims.
"""
import argparse
from datetime import datetime,timezone
from hashlib import sha256
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

from wam_regtest.probe_source import verify_source
from wam_regtest.core import verified_core_paths
from wam_regtest.core_supervisor import CoreSupervisor
from wam_regtest.custody import create_directory
from wam_regtest.managed_wallet_checkpoint import checkpoint,ManagedWalletError
from wam_regtest.wsp_live import PINNED_WSP_COMMIT,_pinned_source


class AfterPublicationCut(ValueError):pass
class BeforeRecoveryCommitCut(ValueError):pass


def interrupted_publication(owner,source,password,keychain,initial):
    """Real durable ciphertext, controlled cut before native anchor advance.

    Safety refusal evidence ONLY. Preserve the ambiguous runtime/orphan; never
    call this successful interrupted-write recovery or physical power loss.
    """
    from wam_regtest import custody
    from wam_regtest.vault import CheckpointVault
    anchor=custody.anchor(initial['wallet_id'],keychain)
    before=anchor.read();folder=owner.directory/'wallet-vault'
    reference=(owner.root/'supervisor.wallet').read_bytes()
    files={p.name:sha256(p.read_bytes()).hexdigest() for p in folder.glob('snapshot-*.enc')}
    store=custody.storage();publish=store.publish;published={}
    next_name=CheckpointVault._filename(before[0]+1)
    def cut(directory,name,blob):
        publish(directory,name,blob)  # Existing native fsync/create-only publication.
        if directory==folder and name==next_name:
            published['sha256']=sha256(blob).hexdigest()
            raise AfterPublicationCut('Q05_TEST_CUT_AFTER_DURABLE_PUBLICATION')
    try:
        with patch.object(store,'publish',cut):
            checkpoint(owner,source,password,authorized=True,keychain=keychain)
        raise ValueError('Q05_PUBLICATION_CUT_NOT_EXERCISED')
    except ManagedWalletError as error:
        if (error.args!=('MANAGED_WALLET_CHECKPOINT_DENIED',)
                or type(error.__context__) is not AfterPublicationCut or not published):raise
    if (anchor.read()!=before or (owner.root/'supervisor.wallet').read_bytes()!=reference
            or any(sha256((folder/name).read_bytes()).hexdigest()!=digest for name,digest in files.items())
            or sha256(store.read(folder,next_name)).hexdigest()!=published['sha256']
            or not (owner.directory/'wallet-runtime.sqlite').exists()):
        raise ValueError('Q05_INTERRUPTED_CHECKPOINT_STATE_NOT_PRESERVED')
    runtime=owner.directory/'wallet-runtime.sqlite';runtime_digest=sha256(runtime.read_bytes()).hexdigest()
    try:
        checkpoint(owner,source,password,authorized=True,keychain=keychain)
        raise ValueError('Q05_AMBIGUOUS_RUNTIME_ADOPTED')
    except ManagedWalletError as error:
        if error.args!=('MANAGED_WALLET_EXISTING_RUNTIME_DENIED',):raise
    if anchor.read()!=before or sha256(runtime.read_bytes()).hexdigest()!=runtime_digest:
        raise ValueError('Q05_AMBIGUOUS_STATE_REPAIRED')
    return {'cut_after_real_durable_publication_before_anchor':True,
            'unchanged_native_anchor':list(before),'original_ciphertexts_reference_preserved':True,
            'orphan_ciphertext_sha256':published['sha256'],'runtime_preserved':True,
            'next_open_refused_before_keys_or_balance':True,
            'prior_anchored_reservation_sha256':initial['reservation_sha256'],
            'recovery_completed':False,'physical_power_loss_test':False}


def interrupted_recovery_reference(owner,source,password,keychain,initial,preserved):
    """Real anchor advance, then deny before COMMIT; no automatic completion."""
    from wam_regtest import custody,wallet_recovery
    from wam_regtest.vault import CheckpointVault
    original_append=wallet_recovery._append;observed={'cut':False}
    def cut(*args,**kwargs):
        if kwargs.get('state')=='COMMIT':
            observed['cut']=True
            raise BeforeRecoveryCommitCut('Q05_TEST_CUT_BEFORE_RECOVERY_COMMIT')
        return original_append(*args,**kwargs)
    try:
        with patch.object(wallet_recovery,'_append',cut):
            wallet_recovery.recover_checkpoint(owner,source,password,authorized=True,keychain=keychain)
        raise ValueError('Q05_RECOVERY_REFERENCE_CUT_NOT_EXERCISED')
    except ManagedWalletError as error:
        if (error.args!=('MANAGED_RECOVERY_DENIED',)
                or type(error.__context__) is not BeforeRecoveryCommitCut or not observed['cut']):raise
    anchor=custody.anchor(initial['wallet_id'],keychain);actual=anchor.read()
    rows,_=wallet_recovery._records(owner,initial['wallet_id'])
    if (rows[-1]['state']!='BEGIN' or actual[0]!=initial['checkpoint'][0]+1
            or any(sha256(p.read_bytes()).hexdigest()!=digest for p,digest in preserved.items())):
        raise ValueError('Q05_PENDING_RECOVERY_EVIDENCE_DIVERGED')
    target=owner.directory/('wallet-recovery-'+rows[-1]['action'])
    CheckpointVault(target,anchor,source)._load_payload(password,actual)
    for operation in (checkpoint,wallet_recovery.recover_checkpoint):
        try:
            operation(owner,source,password,authorized=True,keychain=keychain)
            raise ValueError('Q05_PENDING_RECOVERY_AUTO_COMPLETED')
        except ManagedWalletError as error:
            if error.args!=('MANAGED_RECOVERY_PENDING',):raise
    if anchor.read()!=actual:raise ValueError('Q05_PENDING_RECOVERY_ADVANCED_ANCHOR')
    return {'cut_after_real_target_anchor_before_reference_commit':True,
            'target_ciphertext_authenticated_by_actual_native_anchor':True,
            'pending_reference_blocks_normal_open_and_recovery':True,
            'original_orphan_runtime_reference_preserved':True,
            'native_anchor':list(actual),'recovery_completed':False,
            'automatic_reference_completion':False,'physical_power_loss_test':False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--core-dir',required=True,type=Path)
    parser.add_argument('--wsp-source',required=True,type=Path)
    parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--receipt',required=True,type=Path)
    parser.add_argument('--confirm-disposable-regtest',action='store_true')
    parser.add_argument('--fund-disposable-wallet',action='store_true')
    parser.add_argument('--reservation',choices=('none','signed','uncertain'),default='none')
    parser.add_argument('--interrupt-publication',action='store_true')
    parser.add_argument('--recover-after-interruption',action='store_true')
    parser.add_argument('--interrupt-recovery-reference',action='store_true')
    parser.add_argument('--complete-pending-recovery',action='store_true')
    a=parser.parse_args();source=Path(__file__).resolve().parents[1]
    if (not a.confirm_disposable_regtest or platform.system()!='Darwin'
            or platform.machine()!='arm64' or a.root.exists() or a.root.is_symlink()
            or a.receipt.exists() or a.reservation!='none' and not a.fund_disposable_wallet
            or a.recover_after_interruption and not a.interrupt_publication
            or a.interrupt_recovery_reference and not a.recover_after_interruption
            or a.complete_pending_recovery and not a.interrupt_recovery_reference
            or subprocess.check_output(['git','status','--porcelain'],cwd=source)):
        raise SystemExit('Q05_WALLET_PROBE_SCOPE_DENIED')
    provenance=verify_source(source)
    head=provenance['checkout_sha']
    node,cli,intake=verified_core_paths(a.core_dir);_pinned_source(a.wsp_source)
    record={'schema':'q05-wallet-checkpoint-native/v1','status':'FAIL',
        'wallet_fixture':'PUBLIC_FIXTURE_FUNDED' if a.fund_disposable_wallet else 'EMPTY',
        'qualification_scope':('EXPLICIT_PENDING_RECOVERY_COMPLETION' if a.complete_pending_recovery else
            'INCOMPLETE_RECOVERY_REFERENCE_SAFE_REFUSAL' if a.interrupt_recovery_reference else
            'EXPLICIT_SAME_OWNER_CHECKPOINT_RECOVERY' if a.recover_after_interruption else
            'INTERRUPTED_PUBLICATION_SAFE_REFUSAL' if a.interrupt_publication else 'CLEAN_OWNER_REOPEN'),
        'source_sha':head,'checkout_sha':head,'source_provenance':provenance,
        'platform':'macos-arm64','frozen':False,
        'core_trust':'official-signed-v0.1.11','core_version':'v0.1.11',
        'core_sha256':{p.name:sha256(p.read_bytes()).hexdigest() for p in (node,cli)},
        'wsp_source_commit':PINNED_WSP_COMMIT,'wsp_executed':True,
        'python_version':platform.python_version(),
        'dependencies':{p:importlib.metadata.version(p) for p in ('coincurve','cryptography')},
        'adapter_sha256':sha256((source/'src/wam_regtest/managed_wallet_checkpoint.py').read_bytes()).hexdigest(),
        'source_files':{p:sha256((source/p).read_bytes()).hexdigest() for p in (
            'src/wam_regtest/core_supervisor.py','src/wam_regtest/supervisor_journal.py',
            'src/wam_regtest/supervisor_identity.py','src/wam_regtest/supervisor_store.py',
            'src/wam_regtest/supervisor_protocol.py','src/wam_regtest/managed_wallet_checkpoint.py',
            'src/wam_regtest/wallet_recovery.py','src/wam_regtest/history_pages.py',
            'src/wam_regtest/probe_source.py',
            'src/wam_regtest/vault.py','src/wam_regtest/wallet_session.py',
            'src/wam_regtest/rpc_scope.py','src/wam_regtest/json_rpc.py',
            'src/wam_regtest/cli_rpc.py','scripts/probe_q05_wallet_checkpoint.py')},
        'synthetic_rpc':False,'funding_or_mining':a.fund_disposable_wallet,
        'wallet_signing':a.reservation!='none','wallet_broadcast_requested':a.reservation=='uncertain',
        'public_fixture_signature_and_broadcast':a.fund_disposable_wallet,
        'physical_device_acceptance':False,'mainnet_allowed':False,'observations':[]}
    owner=None;session=None;stage='KEYCHAIN';send_calls=[];submitted_txid=None
    # A test-only observer may drop the caller result ONLY after the real
    # signed CLI returned Core's actual matching txid. Never fabricate RPC.
    from wam_regtest.wallet_session import WalletCoreCli,WalletSession,WalletSessionError
    original_call=WalletCoreCli.call
    def observe_call(client,method,params=None):
        if method=='sendrawtransaction':send_calls.append(True)
        result=original_call(client,method,params)
        if method=='sendrawtransaction' and a.reservation=='uncertain':
            if result!=submitted_txid:raise ValueError('Q05_REAL_CORE_TXID_MISMATCH')
            raise WalletSessionError('Q05_FIXTURE_LOST_RESULT_AFTER_REAL_CORE')
        return result
    observer=patch.object(WalletCoreCli,'call',observe_call);observer.start()
    try:
        create_directory(a.root)
        owner=CoreSupervisor(a.root,a.core_dir,authorized=True)
        record['lifecycle_schema']=owner.journal.schema
        record['directory_identity_sha256']=sha256(json.dumps(owner.journal.identity,
            sort_keys=True,separators=(',',':')).encode()).hexdigest()
        owner.start(timeout=30)
        keychain=a.root/'q05-disposable.keychain-db'
        result=subprocess.run(['/usr/bin/security','create-keychain','-p',
            'public-test-only',str(keychain)],capture_output=True,timeout=15)
        if result.returncode:raise ValueError('Q05_DISPOSABLE_KEYCHAIN_DENIED')
        stage='CREATE'
        password=b'public-disposable-q05-native-only'
        initial=checkpoint(owner,a.wsp_source,password,authorized=True,keychain=keychain,create=True)
        if (initial['height']!=0 or initial['confirmed_atoms']!=0 or initial['history_count']!=0
                or initial['signer_allowed'] or initial['broadcast_allowed']
                or initial['checkpoint'][0]!=1):raise ValueError('Q05_EMPTY_CHECKPOINT_DENIED')
        first=a.root/'chain'/'wallet-vault'/'snapshot-000000001.enc'
        first_digest=sha256(first.read_bytes()).hexdigest()
        record['wallet_id']=initial['wallet_id']
        record['payment_code_sha256']=sha256(initial['payment_code'].encode()).hexdigest()
        record['observations'].append({'created_empty_anchored_generation':initial['checkpoint'],
            'height':initial['height'],'confirmed_atoms':0,'history_count':0,'plaintext_runtime_removed':True})
        stage='DUPLICATE_REFUSAL'
        try:
            checkpoint(owner,a.wsp_source,password,authorized=True,keychain=keychain,create=True)
            raise ValueError('Q05_DUPLICATE_CREATE_ACCEPTED')
        except ManagedWalletError as error:
            if error.args!=('MANAGED_WALLET_EXISTS_OR_UNCERTAIN',):raise
        if sha256(first.read_bytes()).hexdigest()!=first_digest:
            raise ValueError('Q05_DUPLICATE_MUTATED_VAULT')
        stage='WRONG_PASSWORD_REFUSAL'
        from wam_regtest.custody import anchor
        native_anchor=anchor(initial['wallet_id'],keychain)
        anchor_before=native_anchor.read()
        reference=(a.root/'supervisor.wallet').read_bytes()
        try:
            checkpoint(owner,a.wsp_source,b'wrong-public-disposable-password',
                       authorized=True,keychain=keychain)
            raise ValueError('Q05_WRONG_PASSWORD_ACCEPTED')
        except ManagedWalletError as error:
            if error.args!=('MANAGED_WALLET_CHECKPOINT_DENIED',):raise
        if (native_anchor.read()!=anchor_before
                or (a.root/'supervisor.wallet').read_bytes()!=reference
                or sha256(first.read_bytes()).hexdigest()!=first_digest
                or (owner.directory/'wallet-runtime.sqlite').exists()):
            raise ValueError('Q05_PASSWORD_FAILURE_MUTATED_CHECKPOINT')
        record['observations'].append({'wrong_password_refused':True,
            'native_anchor_reference_ciphertext_preserved':True})
        if a.fund_disposable_wallet:
            stage='PUBLIC_DISPOSABLE_FIXTURE_FUNDING'
            from wam_regtest.wallet_session import WalletCoreCli
            from wam_regtest.wsp_live import _public_fixture_payment,public_regtest_mining_address
            rpc=WalletCoreCli(owner.cli,owner.directory);rpc.attest()
            address=public_regtest_mining_address(a.wsp_source)
            rpc._call('generatetoaddress',['101',address])
            txid,atoms,height=_public_fixture_payment(rpc,
                SimpleNamespace(payment_code=lambda:initial['payment_code']),address)
            if getattr(rpc,'_transport',None) is not None:rpc._transport.close()
            initial=checkpoint(owner,a.wsp_source,password,authorized=True,keychain=keychain)
            if (initial['confirmed_atoms']!=atoms or initial['height']!=height
                    or initial['history_count']!=1):raise ValueError('Q05_FUNDED_SCAN_DENIED')
            record['observations'].append({'real_fixture_payment_txid':txid,
                'height':height,'confirmed_atoms':atoms,'history_count':1,
                'history_sha256':initial['history_sha256'],'wallet_signing_or_broadcast':False})
        if a.reservation!='none':
            stage='NATIVE_WALLET_SIGNED_RESERVATION'
            from wam_regtest.vault import CheckpointVault
            from wam_sp.keystore import Keyring
            from wam_sp.psbt import PSBT
            from wam_sp.wallet import Wallet
            vault=CheckpointVault(owner.directory/'wallet-vault',native_anchor,a.wsp_source)
            ring,scanner=vault.restore(owner.directory/'wallet-runtime.sqlite',password)
            session=WalletSession(a.core_dir,owner.directory,a.wsp_source,ring,scanner,vault,
                password,None,core_cli=owner.cli,core_receipt=owner.receipt)
            recipient=Keyring()
            try:code=recipient.accounts()[0].payment_code()
            finally:recipient.close()
            review=session.prepare(code,100000,10000);session.sign(review.commitment)
            submitted_txid=PSBT.decode(session._signed).txid()
            if a.reservation=='uncertain':
                stage='REAL_BROADCAST_CALLER_RESULT_LOSS'
                try:
                    session.broadcast(review.commitment)
                    raise ValueError('Q05_LOST_RESULT_NOT_OBSERVED')
                except WalletSessionError as error:
                    if error.args!=('WALLET_BROADCAST_UNCERTAIN_LOCK_RETAINED',):raise
                if len(send_calls)!=1:
                    raise ValueError('Q05_BROADCAST_ATTEMPT_COUNT_DENIED')
                from wam_regtest.core import _read_cli
                # Fixture introspection uses the existing signed CLI read
                # capability. Do not broaden the scanner's HTTP/method scope.
                mempool=_read_cli([str(owner.cli),f'-datadir={owner.directory}','getrawmempool'])
                if submitted_txid not in mempool:
                    raise ValueError('Q05_REAL_BROADCAST_NOT_OBSERVED')
            rows=session.scanner.store.db.execute('SELECT state FROM reservations').fetchall()
            if not rows or any(row[0]!=a.reservation for row in rows):
                raise ValueError('Q05_RESERVATION_STATE_NOT_DURABLE')
            token=session._prepared.proposal.token
            try:
                Wallet(session.scanner).release_draft(token)
                raise ValueError('Q05_IRREVERSIBLE_RESERVATION_RELEASED')
            except ValueError as error:
                if error.args!=('RESERVATION_NOT_DRAFT',):raise
            session.lock();session=None
            initial=checkpoint(owner,a.wsp_source,password,authorized=True,keychain=keychain)
            if (initial['reservation_count']!=1 or initial['reservation_states']!=[a.reservation]
                    or initial['reserved_atoms']!=initial['confirmed_atoms']
                    or initial['available_atoms']!=0):
                raise ValueError('Q05_RESERVATION_RESTORE_DENIED')
            record['observations'].append({'genuine_wallet_signature':True,
                'reservation_state':a.reservation,'reservation_sha256':initial['reservation_sha256'],
                'irreversible_draft_release_refused':True,'actual_wallet_broadcast_calls':len(send_calls),
                'core_acceptance_before_caller_loss':a.reservation=='uncertain'})
        if a.interrupt_publication:
            stage='INTERRUPTED_PUBLICATION_SAFE_REFUSAL'
            record['observations'].append(interrupted_publication(owner,a.wsp_source,
                password,keychain,initial))
            record['recovery_completed']=False
            if a.recover_after_interruption:
                stage='EXPLICIT_SAME_OWNER_CHECKPOINT_RECOVERY'
                from wam_regtest.wallet_recovery import recover_checkpoint
                original=[*(owner.directory/'wallet-vault').glob('snapshot-*.enc'),
                          owner.root/'supervisor.wallet']
                original.extend(p for suffix in ('','-journal','-wal','-shm')
                    if (p:=owner.directory/('wallet-runtime.sqlite'+suffix)).exists())
                preserved={p:sha256(p.read_bytes()).hexdigest() for p in original}
                if a.interrupt_recovery_reference:
                    stage='INCOMPLETE_RECOVERY_REFERENCE_SAFE_REFUSAL'
                    record['observations'].append(interrupted_recovery_reference(owner,a.wsp_source,
                        password,keychain,initial,preserved))
                    if a.complete_pending_recovery:
                        stage='EXPLICIT_PENDING_RECOVERY_COMPLETION'
                        from wam_regtest.wallet_recovery import complete_recovery,_records
                        from wam_regtest import custody
                        rows,_=_records(owner,initial['wallet_id']);action=rows[-1]['action']
                        anchor=custody.anchor(initial['wallet_id'],keychain);before=anchor.read()
                        reference=(owner.root/'supervisor.recovery.000001').read_bytes()
                        try:
                            complete_recovery(owner,a.wsp_source,b'wrong-public-test-password',
                                authorized=True,keychain=keychain,action=action)
                            raise ValueError('Q05_COMPLETION_WRONG_PASSWORD_ACCEPTED')
                        except ManagedWalletError:
                            pass
                        if (anchor.read()!=before or
                                (owner.root/'supervisor.recovery.000001').read_bytes()!=reference):
                            raise ValueError('Q05_COMPLETION_WRONG_PASSWORD_MUTATED_STATE')
                        recovered=complete_recovery(owner,a.wsp_source,password,authorized=True,
                            keychain=keychain,action=action)
                        reference=(owner.root/'supervisor.recovery.000002').read_bytes()
                        repeated=complete_recovery(owner,a.wsp_source,password,authorized=True,
                            keychain=keychain,action=action)
                        if (recovered['completion_already_committed'] is not False
                                or repeated['completion_already_committed'] is not True
                                or anchor.read()!=before or recovered['checkpoint']!=list(before)
                                or (owner.root/'supervisor.recovery.000002').read_bytes()!=reference
                                or any(recovered[k]!=initial[k] for k in ('wallet_id','payment_code',
                                    'history_sha256','reservation_sha256','reserved_atoms'))
                                or any(sha256(p.read_bytes()).hexdigest()!=digest for p,digest in preserved.items())):
                            raise ValueError('Q05_PENDING_COMPLETION_NOT_AUTHENTIC_OR_IDEMPOTENT')
                        initial=recovered;record['recovery_completed']=True
                        record['observations'].append({'explicit_pending_commit_completed':True,
                            'wrong_password_preserved_pending_reference':True,'native_anchor_unchanged':list(before),
                            'same_wallet_history_and_uncertainty_preserved':True,
                            'authenticated_retry_idempotent':True,'original_unknown_bytes_preserved':True})
                else:
                    recovered=recover_checkpoint(owner,a.wsp_source,password,authorized=True,keychain=keychain)
                    if (recovered['wallet_id']!=initial['wallet_id']
                            or recovered['payment_code']!=initial['payment_code']
                            or recovered['history_sha256']!=initial['history_sha256']
                            or recovered['reservation_sha256']!=initial['reservation_sha256']
                            or recovered['reserved_atoms']!=initial['reserved_atoms']
                            or recovered['checkpoint'][0]!=initial['checkpoint'][0]+1
                            or any(sha256(p.read_bytes()).hexdigest()!=digest for p,digest in preserved.items())):
                        raise ValueError('Q05_EXPLICIT_RECOVERY_DIVERGED_OR_CHANGED_OLD_EVIDENCE')
                    initial=recovered;record['recovery_completed']=True
                    record['observations'].append({'explicit_same_wallet_checkpoint_recovery':True,
                        'original_orphan_runtime_reference_preserved':True,
                        'reservation_sha256':initial['reservation_sha256'],
                        'native_anchored_generation':initial['checkpoint']})
        if (not a.interrupt_recovery_reference or a.complete_pending_recovery) and (not a.interrupt_publication or a.recover_after_interruption):
            stage='CORE_OWNER_REOPEN'
            owner.shutdown();owner.close()
            owner=CoreSupervisor(a.root,a.core_dir,authorized=True);owner.start(timeout=30)
            stage='RESTORE_AND_LIVE_RESYNC'
            restored=checkpoint(owner,a.wsp_source,password,authorized=True,keychain=keychain)
            if (restored['wallet_id']!=initial['wallet_id']
                    or restored['payment_code']!=initial['payment_code']
                    or restored['tip']!=initial['tip'] or restored['height']!=initial['height']
                    or restored['confirmed_atoms']!=initial['confirmed_atoms']
                    or restored['history_count']!=initial['history_count']
                    or restored['history_sha256']!=initial['history_sha256']
                    or restored['reservation_sha256']!=initial['reservation_sha256']
                    or restored['reservation_states']!=initial['reservation_states']
                    or restored['reserved_atoms']!=initial['reserved_atoms']
                    or restored['checkpoint'][0]!=initial['checkpoint'][0]+1
                    or sha256(first.read_bytes()).hexdigest()!=first_digest):
                raise ValueError('Q05_REOPEN_WALLET_CONTINUITY_DENIED')
            record['observations'].append({'reopened_same_wallet_live_resync':True,
                'anchored_generation':restored['checkpoint'],'original_generation_preserved':True,
                'height':restored['height'],'confirmed_atoms':restored['confirmed_atoms'],
                'history_count':restored['history_count'],'history_sha256':restored['history_sha256'],
                'plaintext_runtime_removed':True})
        if len(send_calls)!=(1 if a.reservation=='uncertain' else 0):
            raise ValueError('Q05_UNCERTAIN_TRANSACTION_REPLAYED')
        record['wallet_broadcast_calls_total']=len(send_calls)
        record['automatic_wallet_transaction_replay']=False
        stage='SAFE_SHUTDOWN'
        owner.shutdown();owner.close();owner=None
        record['status']='PASS'
    except Exception as error:
        record['failure_stage']=stage;record['failure_type']=type(error).__name__
        context=error.__context__
        if context is not None:record['inner_failure_type']=type(context).__name__
        if session is not None:
            try:session.lock()
            except (OSError,ValueError,RuntimeError):record['wallet_lock_blocked']=True
        # Original in-process Popen only, never guessed PID cleanup.
        if owner is not None and owner.process is not None and owner.process.poll() is None:
            try:owner.recover_stop()
            except (OSError,ValueError,RuntimeError):record['owned_release_blocked']=True
    finally:
        observer.stop()
        if owner is not None:
            try:owner.close()
            except (OSError,ValueError,RuntimeError):record['owner_close_blocked']=True
        record['timestamp_utc']=datetime.now(timezone.utc).isoformat()
        with a.receipt.open('x') as out:json.dump(record,out,indent=2);out.write('\n')
    print(json.dumps({'status':record['status'],'source_sha':head,
        'observations':len(record['observations'])}))
    if record['status']!='PASS':raise SystemExit(2)


if __name__=='__main__':main()
