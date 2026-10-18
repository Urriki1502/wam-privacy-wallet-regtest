"""Managed native Core transaction IPC security contracts.

Unit/negative only. Real Core mempool, PSBT and spend permission must be
qualified separately: no synthetic transaction counts as a Core E2E PASS.
"""
import unittest

from wam_regtest.managed_spend_protocol import (
    SpendProtocolError,encode_request,decode_request,
    encode_reply,decode_reply,MAX_SPEND_REQUEST,
)
from wam_regtest.managed_scan_protocol import ScanProtocolError,encode_request as scan_request


class SpendIpcContracts(unittest.TestCase):
    secret=b"t"*32
    nonce="c"*32
    rawtx="01000000000100"

    def test_one_use_request_hmac_and_response(self):
        seen=set()
        for method,args,result in (
            ("gettxout",["a"*64,0,True],
             {"value":"0.00200000","scriptPubKey":{"hex":"5120"+"d"*64}}),
            ("testmempoolaccept",[[self.rawtx]],
             [{"allowed":True}]),
            ("sendrawtransaction",[self.rawtx],"f"*64),
        ):
            with self.subTest(method=method):
                nonce=hex(len(seen)+11)[2:].zfill(32)
                wire=encode_request(self.secret,method,args,nonce)
                self.assertEqual(decode_request(wire,self.secret,seen),(method,args,nonce))
                reply=encode_reply(self.secret,method,nonce,result)
                self.assertEqual(decode_reply(reply,self.secret,method,nonce),result)
                with self.assertRaisesRegex(SpendProtocolError,"REPLAY_DENIED"):
                    decode_request(wire,self.secret,seen)

    def test_control_and_scanner_protocols_cannot_authorize_spend(self):
        with self.assertRaises(ScanProtocolError):
            scan_request(self.secret,"sendrawtransaction",[self.rawtx],self.nonce)
        spend=encode_request(self.secret,"sendrawtransaction",[self.rawtx],self.nonce)
        with self.assertRaisesRegex(SpendProtocolError,"AUTH_DENIED"):
            decode_request(spend,b"z"*32,set())
        with self.assertRaises(SpendProtocolError):
            decode_request(spend.replace(b"regtest",b"mainnet"),
                           self.secret,set())

    def test_transaction_rpc_narrow_allowlist(self):
        for method,args in (
            ("stop",[]),("generatetoaddress",["1","abc"]),
            ("getwalletinfo",[]),("dumpprivkey",["key"]),
            ("sendtoaddress",["addr",1]),
            ("gettxout",["a"*64,0,False]),
            ("gettxout",["a"*64,-1,True]),
            ("gettxout",["a"*64,True,True]),
            ("testmempoolaccept",[[]]),
            ("sendrawtransaction",["not-hex"]),
            ("sendrawtransaction",["f"*12002]),
        ):
            with self.subTest(method=method,args=str(args)[:60]):
                with self.assertRaises(SpendProtocolError):
                    encode_request(self.secret,method,args,self.nonce)

    def test_spend_reply_tampering_wrong_nonce_and_result_denied(self):
        reply=encode_reply(self.secret,"sendrawtransaction",self.nonce,"e"*64)
        for invalid in (
            reply.replace(b"e"*64,b"f"*64),
            reply.replace(b"regtest",b"mainnet"),
            reply[:-1],
        ):
            with self.assertRaises(SpendProtocolError):
                decode_reply(invalid,self.secret,"sendrawtransaction",self.nonce)
        with self.assertRaises(SpendProtocolError):
            decode_reply(reply,self.secret,"sendrawtransaction","d"*32)
        with self.assertRaises(SpendProtocolError):
            encode_reply(self.secret,"sendrawtransaction",self.nonce,
                         {"wrong":"object"})

    def test_oversized_payload_fails_before_socket(self):
        with self.assertRaises(SpendProtocolError):
            encode_request(self.secret,"sendrawtransaction",
                           ["a"*12004],self.nonce)
        with self.assertRaises(SpendProtocolError):
            decode_request(b"a"*(MAX_SPEND_REQUEST+1),self.secret,set())


if __name__=="__main__":
    unittest.main()
