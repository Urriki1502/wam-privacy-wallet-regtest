"""Source/real-crypto guards; no mock result counts as Core acceptance."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from hashlib import sha256

from wam_regtest.bip39_reconciliation import _branch,_runtime_evidence,_approved,ReconciliationError


def _linux_core_witness_unbound():
    if sys.platform != 'linux':
        return False
    from wam_regtest.linux_developer_core import LinuxCoreError
    from wam_regtest.linux_runtime import policy
    try:
        policy()
    except LinuxCoreError:
        return True
    return False


class ReconciliationContracts(unittest.TestCase):
    def test_isolated_backend_cannot_enter_shared_reconciliation(self):
        from wam_regtest.bip39_owner_backend import Bip39ReadOnlyBackend,Q06ReadOnlyError
        backend=Bip39ReadOnlyBackend(Path('/unused'),Path('/unused'),Path('/unused'))
        with self.assertRaises(Q06ReadOnlyError):
            backend.execute('reconcile_reorg',(b'public-unit-password-only',),{})
        self.assertIsNone(backend.owner)

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

    @unittest.skipIf(_linux_core_witness_unbound(),
                     "Linux RuntimeGuard requires explicit Core+witness; covered by native Core jobs")
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

    @unittest.skipIf(_linux_core_witness_unbound(),
                     "Linux custody.storage requires explicit Core+witness; covered by native Core jobs")
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

    @unittest.skipIf(_linux_core_witness_unbound(),
                     "Linux RuntimeGuard requires explicit Core+witness; covered by native Core jobs")
    def test_runtime_change_during_read_cannot_receive_reconciliation_authority(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp).resolve()/('wallet-runtime-recovery-'+'a'*16+'.sqlite')
            db=sqlite3.connect(path)
            db.execute('CREATE TABLE reservations(txid TEXT,vout INTEGER,token TEXT,state TEXT,created INTEGER)')
            db.commit();db.close();path.chmod(0o600)
            connect=sqlite3.connect
            def changed(*args,**kwargs):
                real=connect(*args,**kwargs)
                class ReadOnly:
                    def execute(self,*args):
                        result=real.execute(*args)
                        st=path.stat();os.utime(path,ns=(st.st_atime_ns,st.st_mtime_ns+1))
                        return result
                    def close(self):real.close()
                return ReadOnly()
            with patch('wam_regtest.bip39_reconciliation.sqlite3.connect',side_effect=changed):
                with self.assertRaisesRegex(ReconciliationError,'RUNTIME_CHANGED'):_runtime_evidence(path)

    def test_default_public_native_ancestry_still_denies_competing_branch(self):
        from wam_regtest.bip39_native_checkpoint import _require_confirmed_descendant,SeededNativeCheckpointError
        owner=SimpleNamespace(read=Mock())
        with self.assertRaises(SeededNativeCheckpointError):
            _require_confirmed_descendant(owner,(103,'a'*64),(103,'b'*64))
        owner.read.call.assert_not_called()

    @unittest.skipUnless(importlib.util.find_spec("PySide6") is not None,
                         "Native Qt GUI is verified on macOS/Windows and Linux desktop runners")
    def test_gui_reconciliation_never_enables_signing_without_separate_activation(self):
        from wam_regtest.desktop import qt_application
        from wam_regtest.bip39_fusion_gui import Bip39FusionWindow
        from wam_regtest.wallet_executor import ExecutorState,immutable
        from wam_regtest.shared_regtest import SharedRegtestProfile
        app=qt_application()
        executor=SimpleNamespace(state=ExecutorState(locked=False,core_alive=True),busy=False,closed=False)
        window=Bip39FusionWindow(executor,shared_profile=SharedRegtestProfile('127.0.0.1',peer_port=29557))
        try:
            window._spend_enabled=window._signed_ready=True
            result=immutable(dict(profile='unit-regtest',account_id='fixture',receive_code='wamrtsp1fixture',
                mnemonic_once='',backup_status='verified',checkpoint_present=True,
                reconciliation=dict(signing_authorized=False,automatic_broadcast=False,reservations_preserved=True)))
            window._on_ready('reconcile_reorg',result)
            self.assertTrue(window._ready)
            self.assertFalse(window._spend_enabled)
            self.assertFalse(window._signed_ready)
            self.assertFalse(window.send.isEnabled())
            self.assertFalse(window.broadcast.isEnabled())
            self.assertTrue(window.activate.isEnabled())
        finally:
            window._poll.stop();window.hide();window.deleteLater();app.processEvents()
