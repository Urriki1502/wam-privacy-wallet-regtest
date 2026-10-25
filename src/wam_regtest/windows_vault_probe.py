"""Native Credential Manager + encrypted custody over genuine REGTEST Core.

No operational signing authority. Reuse frozen WSP keystore, Scanner, Wallet
reservations and the shared CheckpointVault; never simulate RPC or cryptography.
"""
import base64
from hashlib import sha256
import json
from pathlib import Path
import re
import secrets

from . import custody
from .vault import CheckpointVault, VaultError
from .windows_checkpoint_anchor import WindowsCredentialAnchor
from .windows_core_regtest_smoke import _rpc
from .wsp_live import LiveCoreReadOnlyCli, _pinned_source, _public_fixture_payment


class WindowsVaultProbeError(ValueError):
    pass


class WindowsVaultFixtureRpc(LiveCoreReadOnlyCli):
    """Only the disposable fixture and reorg harness; NOT a wallet transport."""
    def __init__(self, cli, datadir, port, env):
        super().__init__(cli, datadir)
        self.port, self.env = port, env

    def _call(self, method, args):
        permitted = {'getblockchaininfo','getnetworkinfo','getconnectioncount','getblockcount',
                     'getbestblockhash','getblockhash','getblock','sendrawtransaction',
                     'generatetoaddress','invalidateblock','reconsiderblock'}
        if method not in permitted or type(args) is not list or any(type(a) is not str for a in args):
            raise WindowsVaultProbeError('WIN_VAULT_FIXTURE_RPC_DENIED')
        if method in ('invalidateblock','reconsiderblock') and (len(args)!=1 or not re.fullmatch('[0-9a-f]{64}',args[0])):
            raise WindowsVaultProbeError('WIN_VAULT_FIXTURE_REORG_DENIED')
        return _rpc(self._binary,self._datadir,self.port,self.env,method,*args)


def _delete_fixture(anchor):
    # ONLY targets generated inside this disposable proof; no runtime delete API.
    import ctypes
    from ctypes import wintypes
    delete=ctypes.WinDLL('advapi32',use_last_error=True).CredDeleteW
    delete.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD];delete.restype=wintypes.BOOL
    if not delete(anchor._target,1,0) and ctypes.get_last_error()!=1168:
        raise WindowsVaultProbeError('WIN_VAULT_FIXTURE_CREDENTIAL_CLEANUP_DENIED')


def prove_real_windows_vault(cli,datadir,port,env,source,mining_address):
    _pinned_source(source)
    storage=custody.storage()
    storage.validate_directory(datadir)
    from wam_sp.keystore import Keyring, ScanAccount, seal
    from wam_sp.scanner import Scanner
    from wam_sp.wallet import Wallet, Intent, Signer
    from wam_sp.core import pub
    from wam_sp.watcher import GENESIS
    rpc=WindowsVaultFixtureRpc(cli,datadir,port,env);rpc.attest()
    if rpc.call('getblockcount')!=102:
        raise WindowsVaultProbeError('WIN_VAULT_REAL_CORE_INITIAL_HEIGHT_DENIED')
    password=b'public-disposable-windows-vault-test'
    resources=[];anchors=[];stage='SETUP'
    def directory(name):
        path=datadir/name;custody.create_directory(path);return path
    def anchor():
        value=WindowsCredentialAnchor(secrets.token_hex(16));anchors.append(value);return value
    def denied(action):
        try:action()
        except VaultError:return
        raise WindowsVaultProbeError('WIN_VAULT_NEGATIVE_GATE_ACCEPTED')
    try:
        ring=Keyring();resources.append(ring)
        current_anchor=anchor();vault=CheckpointVault(directory('encrypted-vault'),current_anchor,source)
        stage='REAL_BIP352_FUNDING'
        txid,amount,height=_public_fixture_payment(rpc,ring.accounts()[0],mining_address,
            funding_height=2,expected_before_height=102)
        scanner=Scanner(datadir/'vault-live.sqlite',ring.accounts());resources.append(scanner)
        scanner.sync(rpc)
        assert scanner.ready and height==103 and len(scanner.coins())==1
        assert scanner.coins()[0]['txid']==txid and scanner.coins()[0]['atoms']==amount
        stage='ANCHORED_SAVE'
        first=vault.save(ring,scanner,password)
        first_bytes=storage.read(vault.directory,vault._filename(first[0]))
        duplicate=directory('stale-vault-copy')
        storage.publish(duplicate,vault._filename(first[0]),first_bytes)
        stale=CheckpointVault(duplicate,current_anchor,source)
        # Exercise irreversible native WSP reservations without granting signing.
        wallet=Wallet(scanner)
        recipient=ScanAccount(0,11,pub(12),birthday=1).payment_code()
        proposal=wallet.propose((Intent(recipient,100000),),5000)
        Signer(ring).prepare(proposal)
        wallet.mark_signed(proposal.token)
        scanner.store.db.execute("UPDATE reservations SET state='uncertain' WHERE token=?",(proposal.token,))
        locks=[tuple(row) for row in scanner.store.db.execute('SELECT * FROM reservations ORDER BY txid,vout')]
        assert locks and all(row[3]=='uncertain' for row in locks)
        second=vault.save(ring,scanner,password)
        assert second[0]==first[0]+1
        denied(lambda:stale.save(ring,scanner,password))
        stage='BACKUP_RESTORE'
        backup=directory('encrypted-backup');vault.backup(backup,'recovery.enc')
        recovery=directory('recovered-vault')
        ciphertext=storage.read(backup,'recovery.enc')
        storage.publish(recovery,vault._filename(second[0]),ciphertext)
        reopened=CheckpointVault(recovery,WindowsCredentialAnchor(current_anchor.wallet_id),source)
        denied(lambda:reopened.restore(datadir/'wrong-password.sqlite',b'wrong-public-password'))
        restored_ring,restored=reopened.restore(datadir/'recovered.sqlite',password)
        resources.extend((restored_ring,restored))
        assert restored_ring.accounts()==ring.accounts() and not restored.ready
        try:restored.coins()
        except ValueError:pass
        else:raise WindowsVaultProbeError('WIN_VAULT_RESTORED_BALANCE_TRUSTED')
        restored.sync(rpc)
        assert restored.coins()[0]['atoms']==amount
        assert [tuple(row) for row in restored.store.db.execute('SELECT * FROM reservations ORDER BY txid,vout')]==locks
        stage='REAL_CORE_REORGS'
        tip=rpc.call('getbestblockhash')
        for depth in (1,12,100):
            changed=rpc.call('getblockhash',[103-depth+1])
            rpc._call('invalidateblock',[changed])
            assert restored.sync(rpc).rollback==depth and not restored.coins()
            assert [tuple(row) for row in restored.store.db.execute('SELECT * FROM reservations ORDER BY txid,vout')]==locks
            rpc._call('reconsiderblock',[changed]);restored.sync(rpc)
            assert restored.store.tip()==(103,tip) and restored.coins()[0]['atoms']==amount
        stage='FILE_ONLY_ROLLBACK'
        latest=vault.directory/vault._filename(second[0]);original=storage.read(vault.directory,latest.name)
        latest.write_bytes(first_bytes)  # Deliberately attack only our own fixture.
        denied(lambda:vault.restore(datadir/'rollback.sqlite',password))
        latest.write_bytes(original)
        stage='ORPHAN_SNAPSHOT'
        payload=vault._load_payload(password,second);payload['generation']=second[0]+1
        orphan=seal(json.dumps(payload,sort_keys=True).encode(),password,b'recovery')
        storage.publish(vault.directory,vault._filename(second[0]+1),orphan)
        from .windows_private_storage import WindowsCustodyError
        try:vault.save(ring,scanner,password)
        except WindowsCustodyError:pass
        else:raise WindowsVaultProbeError('WIN_VAULT_ORPHAN_REPLACED')
        assert current_anchor.read()==second
        stage='ANCHOR_LOSS_REPLACEMENT_AND_RESTORE_CLEANUP'
        bad_anchor=anchor();bad_dir=directory('bad-checkpoint')
        bad_payload={**custody.envelope_profile(),'disposable_regtest':True,'network':GENESIS,
            'wallet_id':bad_anchor.wallet_id,'generation':1,
            'keys':base64.b64encode(ring.backup(password)).decode(),
            'checkpoint':base64.b64encode(seal(b'{}',password,b'checkpoint')).decode()}
        broken=seal(json.dumps(bad_payload).encode(),password,b'recovery')
        storage.publish(bad_dir,vault._filename(1),broken)
        missing=CheckpointVault(bad_dir,bad_anchor,source)
        denied(lambda:missing.restore(datadir/'missing.sqlite',password))
        bad_anchor.advance(None,(1,sha256(broken).hexdigest()))
        malformed=CheckpointVault(bad_dir,bad_anchor,source)
        failed=datadir/'failed.sqlite'
        for _ in range(2):
            denied(lambda:malformed.restore(failed,password))
            assert not any(failed.with_name(failed.name+s).exists() for s in ('','-journal','-wal','-shm'))
        _delete_fixture(bad_anchor)
        denied(lambda:malformed.restore(failed,password))
        bad_anchor.advance(None,(1,'0'*64))
        denied(lambda:malformed.restore(failed,password))
        stage='NATIVE_PLATFORM_BINDING'
        foreign_anchor=anchor();foreign_dir=directory('foreign-profile')
        foreign=vault._load_payload(password,second)
        foreign.pop('custody_platform');foreign['version']=1;foreign['generation']=1;foreign['wallet_id']=foreign_anchor.wallet_id
        envelope=seal(json.dumps(foreign).encode(),password,b'recovery')
        storage.publish(foreign_dir,vault._filename(1),envelope)
        foreign_anchor.advance(None,(1,sha256(envelope).hexdigest()))
        denied(lambda:CheckpointVault(foreign_dir,foreign_anchor,source).restore(failed,password))
        assert rpc.call('getblockcount')==103
        return {'status':'WIN64_REAL_CORE_CREDENTIAL_ENCRYPTED_VAULT_RECOVERY_REORG_PASS',
            'real_core_rpc':True,'synthetic_rpc':False,'native_credential_anchor':True,
            'encrypted_backup_restore':True,'same_test_keys_preserved':True,
            'irreversible_uncertain_reservations_preserved':True,'stale_writer_denied':True,
            'wrong_password_denied':True,'file_only_rollback_denied':True,
            'actual_core_reorg_depths':[1,12,100],'orphan_snapshot_overwrite_denied':True,
            'missing_replaced_anchor_denied':True,'failed_restore_plaintext_cleaned':True,
            'foreign_platform_backup_denied':True,'restored_balance_requires_live_scan':True,
            'observed_height':103,'operational_signer_enabled':False,'mainnet_allowed':False,
            'power_loss_durability_qualified':False,'same_user_malware_protection':False,
            'credential_profile_rollback_protection':False,'plaintext_sqlite_while_unlocked':True}
    except Exception:
        raise WindowsVaultProbeError('WIN_VAULT_REAL_CORE_'+stage+'_DENIED') from None
    finally:
        for item in reversed(resources):item.close()
        for value in anchors:_delete_fixture(value)
