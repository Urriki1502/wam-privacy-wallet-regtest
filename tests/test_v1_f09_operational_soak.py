"""F-09 pure contracts: public-only synthetic observations are NOT Core E2E."""
import unittest
from wam_regtest.f09_operational_soak import (
    verify_owned_core_read_soak, OperationalSoakRefusal,
    F09_CYCLES,F09_TOTAL_DEADLINE_SECONDS,F09_BUDGET_VERSION,
)
from wam_regtest.wsp_live import REGTEST_GENESIS

TIP='3'*64
HEIGHT=451


class FakeRead:
    def __init__(self, *, kind=None):
        self.calls=[]
        self.kind=kind
    def __call__(self,method):
        self.calls.append(method)
        if self.kind=='fail' and len(self.calls)==4:
            raise ValueError('RPC_NODE_BUSY')
        if method=='getblockchaininfo':
            row=dict(chain='regtest',blocks=HEIGHT,bestblockhash=TIP)
            if self.kind=='mainnet':row['chain']='main'
            if self.kind=='drift' and len(self.calls)>=6:row['blocks']+=1
            return row
        if method=='getblockcount':
            return True if self.kind=='boolheight' else HEIGHT
        if method=='getbestblockhash':
            return '4'*64 if self.kind=='wrongtip' else TIP
        raise AssertionError('UNEXPECTED_RPC_METHOD')


class FakeClock:
    def __init__(self,delta=0.01):
        self.now=0.0
        self.delta=delta
    def __call__(self):
        self.now+=self.delta
        return self.now


class F09SoakContracts(unittest.TestCase):
    def run_witness(self,reader=None,clock=None,**kwargs):
        return verify_owned_core_read_soak(
            call=reader or FakeRead(),expected_genesis=REGTEST_GENESIS,
            height=HEIGHT,tip=TIP,monotonic=clock or FakeClock(),**kwargs)

    def test_short_soak_budget_read_scope_and_pending_long_qualification(self):
        reader=FakeRead()
        proof=self.run_witness(reader)
        self.assertEqual(proof.budget_version,F09_BUDGET_VERSION)
        self.assertEqual(proof.cycles_completed,64)
        self.assertEqual(proof.read_only_rpc_calls,192)
        self.assertEqual(reader.calls,
                         ['getblockchaininfo','getblockcount','getbestblockhash']*F09_CYCLES)
        self.assertTrue(proof.stable_tip)
        self.assertTrue(proof.no_core_mutations)
        self.assertTrue(proof.no_wallet_keys_or_balances_read)
        self.assertFalse(proof.long_hours_days_qualified)
        self.assertFalse(proof.multi_node_peer_sync_qualified)
        self.assertFalse(proof.low_disk_crash_memory_pressure_qualified)
        self.assertFalse(proof.real_large_history_rescan_qualified)

    def test_wrong_chain_drift_rpc_failure_and_tip_mismatch_denied(self):
        for kind in ('mainnet','drift','fail','boolheight','wrongtip'):
            with self.subTest(kind=kind):
                with self.assertRaises(OperationalSoakRefusal):
                    self.run_witness(FakeRead(kind=kind))

    def test_timeout_budget_is_real_and_refuses_slow_rpc(self):
        for delta in (6.1,2.0):
            with self.subTest(delta=delta):
                with self.assertRaises(OperationalSoakRefusal):
                    self.run_witness(clock=FakeClock(delta=delta))
        self.assertEqual(F09_TOTAL_DEADLINE_SECONDS,180)

    def test_wrong_identity_malformed_height_and_wrong_count_denied(self):
        for field,value in (
            ('expected_genesis','f'*64),
            ('tip','z'*64),
            ('height',True),
            ('height',0),
            ('height',1000001),
            ('cycles',63),
            ('cycles',128),
            ('cycles',True),
        ):
            with self.subTest(field=field,value=value):
                args=dict(call=FakeRead(),expected_genesis=REGTEST_GENESIS,
                          height=HEIGHT,tip=TIP,monotonic=FakeClock())
                args[field]=value
                with self.assertRaises(OperationalSoakRefusal):
                    verify_owned_core_read_soak(**args)

    def test_no_hidden_rpc_write_or_restart_on_failure(self):
        reader=FakeRead(kind='fail')
        with self.assertRaises(OperationalSoakRefusal) as error:
            self.run_witness(reader)
        self.assertEqual(error.exception.args,('F09_BOUNDED_CORE_READ_DENIED',))
        self.assertEqual(reader.calls,[
            'getblockchaininfo','getblockcount','getbestblockhash',
            'getblockchaininfo'])


if __name__=='__main__':
    unittest.main()
