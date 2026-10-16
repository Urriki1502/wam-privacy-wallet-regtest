"""Supplemental malformed-reply/scope tests, NOT synthetic Core acceptance."""
import json,unittest
from wam_regtest.json_rpc import _params,_reply,RpcError,ManagedReadRpc,MAX_REPLY

class ReadRpcContracts(unittest.TestCase):
    def test_scanner_reads_have_exact_verbosity_and_bounded_shape(self):
        h='a'*64
        _params('getblock',[h,3]);_params('getbestblockhash',[])
        for args in ([h,2],[h,True],[h,'3'],['x',3],[h,3,'extra']):
            with self.assertRaises(RpcError):_params('getblock',args)
        def reply(value):return json.dumps({'id':1,'result':value,'error':None}).encode()
        good={'hash':h,'height':101,'tx':[{'vin':[],'vout':[]}]}
        self.assertEqual(_reply(reply(good),1,'getblock'),good)
        for bad in ({**good,'hash':'x'},{**good,'height':True},{**good,'tx':[]},{**good,'tx':'not-list'}):
            with self.assertRaises(RpcError):_reply(reply(bad),1,'getblock')
        with self.assertRaises(RpcError):_reply(reply(True),1,'getconnectioncount')

    def test_version_capability_requires_exact_qualified_profile(self):
        good={'version':111,'subversion':'/WAM:0.1.11/','protocolversion':70016}
        def reply(value):return json.dumps({'id':1,'result':value,'error':None}).encode()
        self.assertEqual(_reply(reply(good),1,'getnetworkinfo'),good)
        _params('getnetworkinfo',[])
        for key,value in [('version',112),('version',True),('subversion','/WAM:0.1.12/'),('protocolversion',70017),('protocolversion','70016')]:
            invalid={**good,key:value}
            with self.assertRaisesRegex(RpcError,'^RPC_VERSION_CAPABILITY_DENIED$'):
                _reply(reply(invalid),1,'getnetworkinfo')
        with self.assertRaises(RpcError):_params('getnetworkinfo',['wallet'])

    def test_writes_and_unknown_wallet_scope_refuse_without_socket(self):
        for method,params in [('stop',[]),('sendrawtransaction',['00']),('loadwallet',['test']),('getblockcount',{}),('getblockhash',[True]),('getblockhash',[-1]),('getblockcount',[1])]:
            with self.assertRaises(RpcError):_params(method,params)
        with self.assertRaises(RpcError):ManagedReadRpc(None,None)
        _params('getblockhash',[0])

    def test_contention_acceptance_requires_a_boolean_opt_in(self):
        from pathlib import Path
        from wam_regtest.core import smoke_real_core,CoreSmokeError
        for value in (1,'yes',None):
            with self.assertRaisesRegex(CoreSmokeError,'^CORE_RPC_CONTENTION_CONSENT_DENIED$'):
                smoke_real_core(Path('/not-opened'),explicit_consent=True,rpc_contention_e2e=value)

        with self.assertRaisesRegex(CoreSmokeError,'^CORE_RPC_CONTENTION_SCOPE_DENIED$'):
            smoke_real_core(Path('/not-opened'),explicit_consent=True,interactive_demo=True,rpc_contention_e2e=True)

    def test_only_explicit_busy_reads_retry_with_bounded_jitter(self):
        from unittest.mock import patch,Mock
        client=object.__new__(ManagedReadRpc)
        client._request_once=Mock(side_effect=RpcError('RPC_NODE_BUSY'))
        with patch('wam_regtest.json_rpc.time.sleep') as sleep:
            with self.assertRaisesRegex(RpcError,'^RPC_NODE_BUSY$'):
                client._request('getblockcount',[])
            self.assertEqual(client._request_once.call_count,3)
            self.assertEqual(len(sleep.call_args_list),2)
            for call,low,high in zip(sleep.call_args_list,(.05,.1),(.15,.3)):
                self.assertGreaterEqual(call.args[0],low);self.assertLessEqual(call.args[0],high)
        for code in ('RPC_AUTHENTICATION_DENIED','RPC_CONNECTION_UNCERTAIN_READ_FAILED','RPC_REPLY_INVALID','RPC_CONFIG_CHANGED'):
            client._request_once=Mock(side_effect=RpcError(code))
            with patch('wam_regtest.json_rpc.time.sleep') as sleep:
                with self.assertRaisesRegex(RpcError,'^'+code+'$'):client._request('getblockcount',[])
                self.assertEqual(client._request_once.call_count,1);sleep.assert_not_called()
        client._request_once.reset_mock()
        with self.assertRaisesRegex(RpcError,'^RPC_READ_SCOPE_DENIED$'):
            client._request('sendrawtransaction',['00'])
        client._request_once.assert_not_called()

    def test_config_drift_is_denied_before_wire_and_never_adopts_new_auth(self):
        from hashlib import sha256
        from pathlib import Path
        from unittest.mock import patch
        client=object.__new__(ManagedReadRpc)
        client._closed=False;client._identifier=0
        client._config_directory=Path('/not-opened-by-unit')
        client._config_digest=sha256(b'original-protected-profile').digest()
        client._auth='PRIVATE_UNIT_CANARY'
        with patch('wam_regtest.json_rpc._private_config',return_value=b'changed-profile'):
            with self.assertRaisesRegex(RpcError,'^RPC_CONFIG_CHANGED$'):
                client._request('getblockcount',[])
        self.assertEqual(client._identifier,0)  # Refused before any connection.
        self.assertEqual(client._auth,'PRIVATE_UNIT_CANARY')
        self.assertFalse(client._closed)
        with patch('wam_regtest.json_rpc._private_config',return_value=b'original-protected-profile'):
            client._assert_config()

    def test_malformed_wrong_id_duplicate_and_wrong_chain_never_echo_reply(self):
        for raw in [b'not json',b'{"id":1,"id":1,"error":null,"result":0}',b'NaN',b'x'*(MAX_REPLY+1),json.dumps({'id':2,'result':0,'error':None}).encode(),json.dumps({'id':1,'result':True,'error':None}).encode(),json.dumps({'id':1,'result':None,'error':{'message':'secret-marker'}}).encode()]:
            try:_reply(raw,1,'getblockcount')
            except RpcError as e:self.assertNotIn('secret-marker',str(e))
            else:self.fail('MALFORMED_REPLY_ACCEPTED')
        with self.assertRaises(RpcError):_reply(b'{"id":1,"error":null,"result":{"chain":"main","blocks":0}}',1,'getblockchaininfo')
        self.assertEqual(_reply(b'{"id":1,"error":null,"result":101}',1,'getblockcount'),101)

    def test_wrong_genesis_and_closed_session_are_quarantined(self):
        import threading
        client=object.__new__(ManagedReadRpc)
        client._lock=threading.RLock();client._closed=False;client._auth=None;client._connection=None
        client._request=lambda method,params: {'chain':'regtest','blocks':0} if method=='getblockchaininfo' else '0'*64
        with self.assertRaisesRegex(RpcError,'^RPC_GENESIS_DENIED$'):client.attest()
        self.assertTrue(client._closed)
        del client._request
        with self.assertRaisesRegex(RpcError,'^RPC_SESSION_CLOSED$'):client.call('getblockcount')
