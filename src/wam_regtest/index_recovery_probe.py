"""Genuine A06 v0.1.11 crash/index-loss/reindex acceptance, disposable only."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def _blocks(directory):
    result={}
    for path in (directory/'regtest/blocks').glob('blk*.dat'):
        assert not path.is_symlink() and path.is_file() and path.stat().st_size<=128*1024*1024
        result[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
    assert result
    return result


def _vault_files(directory):
    return {p.name:hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (directory/'wallet-vault').iterdir() if p.is_file()}


def _reservations(session):
    return tuple(tuple(row) for row in session.scanner.store.db.execute(
        'SELECT txid,vout,token,state FROM reservations ORDER BY txid,vout'))


def prove_index_recovery(core,source):
    from .core import _read_cli,verified_core_paths
    from .core_supervisor import CoreSupervisor
    from .custody import create_directory
    from .owned_recovery import recover_index,IndexRecoveryError
    from .shutdown_probe import _wallet_witness
    from .wallet_session import WalletSession,WalletCoreCli,WalletSessionError
    from .wsp_live import public_regtest_mining_address,_public_fixture_payment
    node,cli,receipt=verified_core_paths(core)
    cases=[]
    for fusion in (False,True):
        print('OWNED_INDEX_RECOVERY_STAGE='+('FUSION_WALLET' if fusion else 'CORE_101'),flush=True)
        temporary=Path(tempfile.mkdtemp(prefix='wam-explicit-reindex-')).resolve()
        root=temporary/'wam-fusion-core-0123456789abcdef'
        owner=session=None
        children=[]
        safe_cleanup=True
        keychain=None
        try:
            create_directory(root)
            owner=CoreSupervisor(root,core,authorized=True)
            owner.start();children.append(owner.process)
            directory=owner.directory
            prefix=[str(cli),f'-datadir={directory}']
            _read_cli(prefix+['createwallet','test'])
            if fusion:
                mine=public_regtest_mining_address(source)
            else:
                mine=_read_cli(prefix+['-rpcwallet=test','getnewaddress','a06-original-wallet'])
            _read_cli(prefix+['generatetoaddress','102' if fusion else '101',mine],timeout=90)
            if fusion:
                if sys.platform=='darwin':
                    keychain=temporary/'a06-disposable.keychain-db'
                    assert subprocess.run(['/usr/bin/security','create-keychain','-p',
                        'public-disposable-only',str(keychain)],capture_output=True,timeout=15).returncode==0
                password=b'public-disposable-a06-reindex-wallet'
                session=WalletSession.create(core,directory,source,password,mine,
                    authorized=True,keychain=keychain,read_rpc=owner.read)
                session.enable_managed_reopen(authorized=True)
                code=session.snapshot().receive_code
                first=session.prepare(code,50000,10000)
                session.sign(first.commitment)  # genuine signature; never broadcast
                # Second independently funded coin creates a second irreversible
                # reservation; do not mutate a signed reservation into a draft.
                funding=WalletCoreCli(cli,directory);funding.attest()
                _public_fixture_payment(funding,session.ring.accounts()[0],mine,
                    funding_height=3,expected_before_height=103)
                session.snapshot();session.close();session=None
                session=WalletSession.reopen_managed(core,directory,source,password,mine,
                    authorized=True,keychain=keychain,read_rpc=owner.read)
                second=session.prepare(code,50000,10000)
                session.sign(second.commitment)
                # Drop a reply AFTER the actual pinned Core accepts the tx.
                # No synthetic response/blockchain or broadcast retry.
                from unittest.mock import patch
                actual=WalletCoreCli.call;accepted=[]
                def lost_reply(client,method,params=None):
                    value=actual(client,method,params)
                    if method=='sendrawtransaction':
                        accepted.append(value)
                        raise WalletSessionError('WALLET_BROADCAST_UNCERTAIN')
                    return value
                with patch.object(WalletCoreCli,'call',lost_reply):
                    try:session.broadcast(second.commitment)
                    except WalletSessionError:pass
                    else:raise AssertionError('A06_LOST_REPLY_NOT_EXERCISED')
                assert len(accepted)==1
                held=_reservations(session)
                assert {row[3] for row in held}=={'signed','uncertain'}
                history=tuple(tuple(row) for row in session.scanner.store.db.execute(
                    'SELECT txid,height,credit,debit FROM history ORDER BY txid'))
                anchor=session.vault.anchor
                anchored=anchor.read()
                session.close();session=None
                sealed=_vault_files(directory)
            else:
                balances=_wallet_witness(owner,'getbalances')
                labels=_wallet_witness(owner,'getaddressesbylabel','a06-original-wallet')
                assert balances['mine']['trusted']>0
            before=owner.read.attest();height=before['blocks'];tip=before['bestblockhash']
            assert height==(104 if fusion else 101)
            disk=_blocks(directory)
            from .supervisor_store import SupervisorStorageError
            try:
                recover_index(root,core,expected_height=height,expected_tip=tip,authorized_reindex=True)
            except SupervisorStorageError as error:
                assert error.args==('SUPERVISOR_STORAGE_LEASE_BUSY',)
            else:raise AssertionError('A06_ACTIVE_SUPERVISOR_RECOVERY_ACCEPTED')
            assert owner.process.poll() is None and _blocks(directory)==disk
            owner.binding._assert_image()
            killed=owner.process;killed.kill()
            assert killed.wait(timeout=15)!=0
            owner.status()
            owner.start();children.append(owner.process)
            observed=owner.read.attest()
            assert observed['blocks']<height and observed['bestblockhash']!=tip, 'A06_EXPECTED_INDEX_LOSS_NOT_OBSERVED'
            assert _blocks(directory)==disk
            if fusion:
                assert anchor.read()==anchored and _vault_files(directory)==sealed
            owner.shutdown();owner.close_listener();owner.stack.close();owner=None
            assert _blocks(directory)==disk
            # Missing consent is refused before any native profile/chain open.
            try:recover_index(root,core,expected_height=height,expected_tip=tip)
            except IndexRecoveryError as error:
                assert error.args==('RECOVERY_EXPLICIT_EXISTING_REGTEST_REINDEX_APPROVAL_REQUIRED',)
            else:raise AssertionError('A06_UNAPPROVED_REINDEX_ACCEPTED')
            safe_cleanup=False
            recovered=recover_index(root,core,expected_height=height,expected_tip=tip,authorized_reindex=True)
            safe_cleanup=True
            assert recovered['status']=='OWNED_REGTEST_EXPLICIT_REINDEX_VERIFIED_STOPPED'
            assert _blocks(directory)==disk
            if fusion:
                assert anchor.read()==anchored and _vault_files(directory)==sealed
            owner=CoreSupervisor(root,core,authorized=True,existing_only=True)
            owner.start();children.append(owner.process)
            after=owner.read.attest()
            assert (after['blocks'],after['bestblockhash'])==(height,tip)
            # Original disposable Core wallet is explicitly loaded, never
            # created/replaced. Core does not promise load-on-startup here.
            # Legacy WalletSession's independent Mining Account read uses it.
            if 'test' not in _wallet_witness(owner,'listwallets'):
                _wallet_witness(owner,'loadwallet','test')
            if fusion:
                try:
                    session=WalletSession.reopen_managed(core,directory,source,password,mine,
                        authorized=True,keychain=keychain,read_rpc=owner.read)
                except Exception as error:
                    from .acceptance_failure import failure_site
                    cause=error.__context__
                    if cause is not None:
                        print('A06_REOPEN_CAUSE_KIND='+type(cause).__name__,flush=True)
                        print('A06_REOPEN_CAUSE_SITE='+failure_site(cause),flush=True)
                    raise
                assert session.snapshot().receive_code==code
                assert _reservations(session)==held
                assert tuple(tuple(row) for row in session.scanner.store.db.execute(
                    'SELECT txid,height,credit,debit FROM history ORDER BY txid'))==history
                assert session.vault.anchor.read()[0]>=anchored[0]
                # No restored reviewed/signed transaction object can broadcast.
                assert session._prepared is None and session._signed is None
            else:
                assert _wallet_witness(owner,'getbalances')==balances
                assert _wallet_witness(owner,'getaddressesbylabel','a06-original-wallet')==labels
                assert _wallet_witness(owner,'getaddressinfo',mine)['ismine'] is True
            cases.append({'scenario':'fusion-native-checkpoint' if fusion else 'original-101-core-wallet',
                'status':'PASS','original_height':height,'original_tip':tip,
                'index_loss_observed_height':observed['blocks'],'explicit_reindex':recovered,
                'exact_height_tip_after_second_restart':True,'complete_block_file_bytes_unchanged':True,
                'original_wallet_state_preserved':True,'native_anchor_and_vault_unchanged_by_reindex':fusion,
                'signed_and_uncertain_reservations_preserved':fusion,
                'confirmed_scanner_history_preserved':fusion,
                'automatic_broadcast':False,'post_crash_mining':False,'replacement_wallet':False})
        finally:
            if session is not None:session.close()
            if owner is not None:
                owner.status()
                if owner.process is not None:owner.shutdown()
                owner.close_listener();owner.stack.close()
            if any(c.poll() is None for c in children):
                safe_cleanup=False
            if safe_cleanup:
                if keychain is not None:
                    assert subprocess.run(['/usr/bin/security','delete-keychain',str(keychain)],
                        capture_output=True,timeout=15).returncode==0
                shutil.rmtree(temporary)
        assert safe_cleanup and not temporary.exists(), 'A06_RECOVERY_FIXTURE_CLEANUP_UNVERIFIED'
    assert verified_core_paths(core)[2]==receipt
    return {'status':'REAL_CORE_EXPLICIT_INDEX_RECOVERY_WALLET_CONTINUITY_PASS',
        'core_version':'v0.1.11','platform':receipt['platform'],
        'wamd_sha256':receipt['wamd_sha256'],'wam_cli_sha256':receipt['wam_cli_sha256'],
        'cases':cases,'synthetic_rpc':False,'mainnet_allowed':False,'cleanup_verified':True,
        'physical_accepted':False,'historical_a06_failure_unchanged':True}
