"""Source/real-crypto guards; no mock result counts as Core acceptance."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
import json
import sqlite3
import tempfile
import unittest
from hashlib import sha256

from wam_regtest.bip39_reconciliation import _branch,_runtime_evidence,_approved,ReconciliationError


class ReconciliationContracts(unittest.TestCase):
    def test_competing_branch_requires_strictly_greater_work_and_orphan_proof(self):
        old=(103,'a'*64);tip=(104,'b'*64)
        info=dict(chain='regtest',blocks=104,bestblockhash=tip[1],chainwork=f'{105:064x}')
        block=dict(hash=old[1],height=103,confirmations=-1,chainwork=f'{104:064x}')
        def call(method,args=None):
            return {'getblockchaininfo':info,'getblockhash':'c'*64,'getblock':block}[method]
        owner=SimpleNamespace(read=SimpleNamespace(call=call))
        self.assertEqual(_branch(owner,old,tip),'owned-core-validated-stronger-branch')
        for key,value in (('chainwork',f'{104:064x}'),('chainwork',f'{103:064x}'),('chainwork','invalid')):
            changed=dict(info);changed[key]=value
            with patch.dict(info,changed):
                with self.assertRaises(ReconciliationError):_branch(owner,old,tip)
        block['confirmations']=1
        with self.assertRaises(ReconciliationError):_branch(owner,old,tip)

    def test_retained_sqlite_is_read_only_and_busy_sidecars_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();path=root/('wallet-runtime-recovery-'+'a'*16+'.sqlite')
            connection=sqlite3.connect(path)
            connection.execute('CREATE TABLE reservations(txid TEXT,vout INTEGER,token TEXT,state TEXT,created INTEGER)')
            connection.execute('INSERT INTO reservations VALUES(?,?,?,?,?)',('a'*64,0,'fixture-token','broadcast',1))
            connection.commit();connection.close();path.chmod(0o600)
            before=sha256(path.read_bytes()).hexdigest()
            digest,rows=_runtime_evidence(path)
            self.assertEqual(digest,before);self.assertEqual(rows[('a'*64,0)][1],'broadcast')
            self.assertEqual(sha256(path.read_bytes()).hexdigest(),before)
            path.with_name(path.name+'-wal').write_bytes(b'retained')
            with self.assertRaisesRegex(ReconciliationError,'RUNTIME_BUSY'):_runtime_evidence(path)

    def test_prepared_receipt_cannot_authorize_uncommitted_native_generation(self):
        from wam_sp.keystore import seal
        from wam_regtest import custody
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();folder=root/'snapshot';folder.mkdir(mode=0o700)
            receipts=root/'q06-reconciliations';receipts.mkdir(mode=0o700)
            storage=custody.storage();password=b'public-source-contract-only'
            one,two=seal(b'old-checkpoint',password,b'recovery'),seal(b'new-checkpoint',password,b'recovery')
            parent=(1,sha256(one).hexdigest());target=(2,sha256(two).hexdigest())
            storage.publish(folder,'snapshot-000000001.enc',one)
            storage.publish(folder,'snapshot-000000002.enc',two)
            record=dict(schema='wam-q06-shared-reconciliation/v1',owner_binding='a'*64,seed_id='b'*32,
                        parent=parent,target=target,tip=[104,'c'*64],branch='owned-core-validated-stronger-branch',runtimes={})
            storage.publish(receipts,'reconciliation-000000002.enc',seal(json.dumps(record).encode(),password,b'recovery'))
            owner=SimpleNamespace(directory=root);anchor=Mock();anchor.read.return_value=parent
            with patch('wam_regtest.bip39_reconciliation._owner_binding',return_value='a'*64):
                with self.assertRaisesRegex(ReconciliationError,'PENDING_NATIVE_CAS'):
                    _approved(owner,'b'*32,folder,anchor,None,password)
                anchor.read.return_value=target
                self.assertEqual(_approved(owner,'b'*32,folder,anchor,None,password),{})
                with self.assertRaises(Exception):_approved(owner,'b'*32,folder,anchor,None,b'incorrect-password-only')

    def test_default_public_native_ancestry_still_denies_competing_branch(self):
        from wam_regtest.bip39_native_checkpoint import _require_confirmed_descendant,SeededNativeCheckpointError
        owner=SimpleNamespace(read=Mock())
        with self.assertRaises(SeededNativeCheckpointError):
            _require_confirmed_descendant(owner,(103,'a'*64),(103,'b'*64))
        owner.read.call.assert_not_called()
