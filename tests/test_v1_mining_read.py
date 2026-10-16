"""Supplemental adversarial scope/render tests, not real-Core acceptance."""
import json
import unittest
from wam_regtest.json_rpc import ManagedReadRpc, RpcError, _params, _reply
from wam_regtest.mining_read import mining_params, MAX_MINING_UTXOS


class MiningReadContracts(unittest.TestCase):
    def test_fixed_read_scope_has_no_selector_write_key_export_or_fallback(self):
        for method in ('stop','createwallet','loadwallet','sendtoaddress','sendrawtransaction',
                       'lockunspent','getnewaddress','dumpprivkey','listdescriptors','getblockcount'):
            with self.assertRaises(RpcError):mining_params(method,[])
        for method in ('getwalletinfo','getbalances','getdevfeeinfo'):
            mining_params(method,[])
            with self.assertRaises(RpcError):mining_params(method,['test'])
            with self.assertRaises(RpcError):_params(method,[])
        client=object.__new__(ManagedReadRpc)
        for consent in (False,1,'yes',None):
            with self.assertRaisesRegex(RpcError,'^RPC_EXPLICIT_READ_CONSENT_REQUIRED$'):
                client.mining_snapshot(authorized_readonly=consent)

    def test_unbounded_wallet_or_path_inputs_fail_before_socket(self):
        for args in ([True],[1],[-1],[0,'other'],[],['0']):
            with self.assertRaises(RpcError):mining_params('listunspent',args)
        for address in ('../owner','/wallet/owner','a'*121,'a'*19,'a'*20+'\n'):
            with self.assertRaises(RpcError):mining_params('getaddressinfo',[address])
        mining_params('gettxout',['a'*64,0,True])
        for args in (['a'*64,True,True],['a'*64,-1,True],['a'*64,0,1],['x',0,True]):
            with self.assertRaises(RpcError):mining_params('gettxout',args)

    def test_wallet_replacement_absent_utxo_and_oversized_reply_fail(self):
        def reply(value):return json.dumps({'result':value,'error':None,'id':1}).encode()
        for method,value in (('getwalletinfo',{'walletname':'owner'}),('listunspent',[{}]*(MAX_MINING_UTXOS+1)),
                             ('gettxout',None),('getbalances',[]),('getaddressinfo',{'ismine':1})):
            with self.assertRaises(RpcError):_reply(reply(value),1,method,mining=True)
        self.assertEqual(_reply(reply({'walletname':'test'}),1,'getwalletinfo',mining=True),{'walletname':'test'})

    def test_treasury_overlap_and_moving_balance_never_return_partial_snapshot(self):
        from unittest.mock import Mock
        from wam_regtest.mining_read import read_mining_snapshot
        from wam_regtest.wsp_live import REGTEST_GENESIS
        # Failure injection only; never counted as real-Core acceptance.
        for mode in ('treasury_owner','changed_balance','changed_tip'):
            rpc=Mock();rpc.attest.return_value={'chain':'regtest','blocks':101}
            counts={}
            def request(method,params,**scope):
                counts[method]=counts.get(method,0)+1
                if method=='getbestblockhash':return ('b' if mode=='changed_tip' and counts[method]>1 else 'a')*64
                if method=='getwalletinfo':return {'walletname':'test','format':'sqlite','descriptors':True,'private_keys_enabled':True}
                if method=='getdevfeeinfo':return {'percent':5,'start_height':1,'last_height':400000,'script':'aa','address':'a'*30}
                if method=='getaddressinfo':return {'ismine':mode=='treasury_owner'}
                if method=='getbalances':return {'mine':{'trusted':1 if mode=='changed_balance' and counts[method]>1 else 0,'untrusted_pending':0,'immature':0}}
                if method=='listunspent':return []
                raise AssertionError('unexpected read')
            rpc._request.side_effect=request
            with self.assertRaises(RpcError):read_mining_snapshot(rpc)

    def test_mining_ui_rejects_reward_substitution_and_clears_stale_values(self):
        from wam_regtest.desktop import qt_application
        from wam_regtest.mining_gui import MiningAccountPage
        from wam_regtest.mining_read import MiningSnapshot
        from wam_regtest.mining_account import MiningWalletBalance,RewardSplit
        app=qt_application();page=MiningAccountPage()
        try:
            snapshot=MiningSnapshot(101,'a'*64,MiningWalletBalance(4750000000,0,0,4750000000,1),RewardSplit.regtest(102))
            page.render_snapshot(snapshot)
            self.assertEqual(page.values['available_atoms'].text(),'47.50000000 WAM')
            self.assertIn('treasury excluded',page.state.text())
            for invalid in (object(),MiningSnapshot(101,'a'*64,snapshot.balance,RewardSplit.regtest(151))):
                with self.assertRaisesRegex(ValueError,'^MINING_GUI_SNAPSHOT_DENIED$'):page.render_snapshot(invalid)
                self.assertTrue(all(v.text()=='—' for v in page.values.values()))
            page.render_snapshot(None);self.assertEqual(page.reward.text(),'—')
        finally:
            page.widget.close();page.widget.deleteLater();app.processEvents()
