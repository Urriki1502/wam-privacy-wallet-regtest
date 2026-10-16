"""Supplemental malformed-reply/scope tests, NOT synthetic Core acceptance."""
import json,unittest
from wam_regtest.json_rpc import _params,_reply,RpcError,ManagedReadRpc,MAX_REPLY

class ReadRpcContracts(unittest.TestCase):
    def test_writes_and_unknown_wallet_scope_refuse_without_socket(self):
        for method,params in [('stop',[]),('sendrawtransaction',['00']),('loadwallet',['test']),('getblockcount',{}),('getblockhash',[True]),('getblockhash',[-1]),('getblockcount',[1])]:
            with self.assertRaises(RpcError):_params(method,params)
        with self.assertRaises(RpcError):ManagedReadRpc(None,None)
        _params('getblockhash',[0])

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
