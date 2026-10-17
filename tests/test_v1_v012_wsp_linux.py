"""v0.1.12 BIP352 fixture adapter negative tests — mocked RPC is NOT E2E."""
import unittest

from wam_regtest.v012_wsp_linux import CandidateLinuxWspRpc, CandidateWspDenied
from wam_regtest.wsp_live import REGTEST_GENESIS


class FixtureCalls:
    def __init__(self):
        self.sent=[]
    def __call__(self,method,*args):
        self.sent.append((method,args))
        if method=="getblockchaininfo":
            return {"chain":"regtest","blocks":101}
        if method=="getblockhash":return REGTEST_GENESIS
        if method=="getconnectioncount":return 0
        if method=="getblockcount":return 101
        if method=="getbestblockhash":return "a"*64
        if method=="getblock":return {"hash":args[0],"tx":[{"txid":"b"*64}]}
        raise AssertionError("UNEXPECTED_METHOD")


class BIP352FixtureAdapterTests(unittest.TestCase):
    def setUp(self):
        self.fake=FixtureCalls()
        self.rpc=CandidateLinuxWspRpc(self.fake, "wamrt1q"+"q"*42)

    def test_scanner_reads_not_allowed_until_real_chain_attestation(self):
        with self.assertRaisesRegex(CandidateWspDenied,"V012_WSP_SCANNER_READ_ONLY_DENIED"):
            self.rpc.call("getblockcount")
        self.assertEqual(self.fake.sent,[])

    def test_read_only_scanner_methods_validate_exact_shapes(self):
        self.rpc.attest()
        self.assertEqual(self.rpc.call("getblockcount"),101)
        self.assertEqual(self.rpc.call("getblockhash",[0]),REGTEST_GENESIS)
        self.assertEqual(self.rpc.call("getbestblockhash"),"a"*64)
        self.assertEqual(self.rpc.call("getblock",["f"*64,3])["hash"],"f"*64)

    def test_scanner_cannot_call_fixture_writes(self):
        self.rpc.attest()
        for name in ("generatetoaddress","sendrawtransaction","stop",
                     "dumpprivkey","createwallet","getbalance"):
            with self.subTest(name=name), self.assertRaises(CandidateWspDenied):
                self.rpc.call(name,[])
        self.assertFalse(any(x[0] in ("stop","sendrawtransaction") for x in self.fake.sent))

    def test_unexpected_writes_and_tx_bytes_denied(self):
        for name,args in (
            ("sendrawtransaction",["not-hex"]),
            ("sendrawtransaction",["aa","bb"]),
            ("sendrawtransaction",[""]),
            ("generatetoaddress",["2","wamrt1qqqqqq"]),
            ("generatetoaddress",["1","wam1mainnet"]),
            ("generatetoaddress",["1","not-regtest"]),
            ("stop",[]),
        ):
            with self.subTest(method=name), self.assertRaises(CandidateWspDenied):
                self.rpc._call(name,args)
        self.assertEqual(self.fake.sent,[])

    def test_wrong_network_peers_or_genesis_refused(self):
        for method,wrong in (
            ("getblockchaininfo",{"chain":"main","blocks":101}),
            ("getconnectioncount",1),
            ("getblockhash","b"*64),
        ):
            data=FixtureCalls()
            old=data.__call__
            class WrongRpc:
                def __call__(self,called,*args):
                    return wrong if called==method else old(called,*args)
            r=CandidateLinuxWspRpc(WrongRpc(), "wamrt1q"+"q"*42)
            with self.subTest(method=method), self.assertRaises(CandidateWspDenied):
                r.attest()

    def test_invalid_rpc_response_and_wrong_height_denied(self):
        self.rpc.attest()
        for params in ([True],[-1],[103],["1"],[]):
            with self.subTest(params=params), self.assertRaises(CandidateWspDenied):
                self.rpc.call("getblockhash",params)
        with self.assertRaises(CandidateWspDenied):
            self.rpc.call("getblock",["f"*64,2])
        with self.assertRaises(CandidateWspDenied):
            self.rpc.call("getblock",[123,3])


if __name__=="__main__":
    unittest.main()
