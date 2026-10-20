"""F-10 public synthetic contracts; not real Core or wam-miner acceptance."""
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Condition
import time
import unittest

from wam_regtest.f10_miner_coexistence import (
    F10_BLOCKS, MinerCoexistenceRefusal, prove_owned_core_miner_coexistence,
)
from wam_regtest.wsp_live import REGTEST_GENESIS

class FakeCore:
    def __init__(self,datadir,mode='ok'):
        self.height=451
        self.tip='a'*64
        self.cond=Condition()
        self.datadir=datadir
        self.mode=mode
        self.calls=[]
    def __call__(self,method,*args,**kwargs):
        self.calls.append(method)
        if method=='getconnectioncount':
            return 1 if self.mode=='peers' else 0
        if method=='waitfornewblock':
            with self.cond:
                initial=self.height
                self.cond.wait_for(lambda:self.height!=initial,timeout=2)
                return {'hash':self.tip,'height':self.height}
        if method=='generatetoaddress':
            with self.cond:
                self.height+=1
                self.tip=('%064x'%self.height)
                self.cond.notify_all()
            if self.mode=='bad_mined_hash':return ['f'*64]
            if self.mode=='config_changed':
                (self.datadir/'wam.conf').write_text('tampered=1')
            return [self.tip]
        if method=='getwalletinfo':
            return {'walletname':'test','descriptors':self.mode!='wallet_changed'}
        raise ValueError('NO_OTHER_RPC_ALLOWED')
    def read(self,method,params=None):
        self.calls.append(method)
        if method=='getblockhash' and params==[0]:return REGTEST_GENESIS
        if method=='getblockchaininfo':
            return {'chain':'main' if self.mode=='wrong_chain' else 'regtest',
                    'blocks':self.height+(1 if self.mode=='wrongheight' else 0),
                    'bestblockhash':self.tip}
        if method=='getblockcount':return self.height
        if method=='getbestblockhash':return self.tip
        raise ValueError('UNEXPECTED_READ')


class F10CoexistenceContracts(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory(prefix='f10-public-unit-')
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()
        (self.root/'wam.conf').write_text('regtest=1\n')
    def run_case(self,mode='ok',**extra):
        core=FakeCore(self.root,mode)
        from types import SimpleNamespace
        proof=prove_owned_core_miner_coexistence(
            rpc=core,read=SimpleNamespace(call=core.read),wallet=core,
            datadir=self.root,miner_address='public-regtest-address',
            sleep=lambda t: time.sleep(.025),**extra)
        return proof,core
    def test_core_mining_continues_while_own_wallet_stays_identified(self):
        proof,core=self.run_case()
        self.assertEqual(proof.generated_blocks,F10_BLOCKS)
        self.assertEqual(proof.longpoll_witnesses,F10_BLOCKS)
        self.assertEqual(proof.wallet_reads_verified,3*F10_BLOCKS)
        self.assertEqual(core.height,451+F10_BLOCKS)
        self.assertTrue(proof.original_core_config_unchanged)
        self.assertTrue(proof.no_node_restart_or_stop)
        self.assertTrue(proof.wallet_identity_continued)
        self.assertFalse(proof.external_solo_miner_binary_qualified)
        self.assertFalse(proof.queue_64_operator_option_qualified)
        self.assertFalse(proof.sunset_400001_real_miner_qualified)
        self.assertNotIn('stop',core.calls)
        self.assertNotIn('setconfig',core.calls)
        self.assertNotIn('getbalance',core.calls)
    def test_real_parallel_observation_or_generation_mismatch_denied(self):
        for bad in ('bad_mined_hash','wrong_chain','wrongheight',
                    'config_changed','wallet_changed','peers'):
            with self.subTest(mode=bad):
                (self.root/'wam.conf').write_text('regtest=1\n')
                with self.assertRaises(MinerCoexistenceRefusal):
                    self.run_case(bad)
    def test_missing_datadir_wrong_count_and_nonowned_scope_denied(self):
        core=FakeCore(self.root)
        from types import SimpleNamespace
        for change in (
            {'datadir':self.root/'absent'},
            {'miner_address':None},
            {'read':None},
            {'wallet':None},
        ):
            with self.subTest(change=change):
                payload=dict(rpc=core,read=SimpleNamespace(call=core.read),
                             wallet=core,datadir=self.root,
                             miner_address='public-regtest-address')
                payload.update(change)
                with self.assertRaises(MinerCoexistenceRefusal):
                    prove_owned_core_miner_coexistence(**payload)


if __name__=='__main__':unittest.main()
