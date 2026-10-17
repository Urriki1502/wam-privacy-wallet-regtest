"""Q05 unit/negative contracts for WSP-only scan IPC.

These fixtures are NOT genuine Core acceptance. The separate T05 real-process
harness must scan genuine blocks over the authenticated supervisor channel.
"""
from decimal import Decimal
from pathlib import Path
import json
import secrets
import unittest
from unittest.mock import Mock,patch

from wam_regtest.managed_scan_protocol import (
    SCAN_PROTOCOL,ScanProtocolError,encode_request,decode_request,
    encode_reply,decode_reply,MAX_SCAN_REPLY,
)
from wam_regtest.managed_scan_client import ManagedScanRpc,ManagedScanError


class ScanIpcContracts(unittest.TestCase):
    def setUp(self):
        self.token=b"t"*32
        self.nonce="c"*32

    def test_genuine_scope_hmac_and_replay_rejection(self):
        raw=encode_request(self.token,"getblockhash",[101],self.nonce)
        seen=set()
        self.assertEqual(decode_request(raw,self.token,seen),
                         ("getblockhash",[101],self.nonce))
        with self.assertRaisesRegex(ScanProtocolError,"SCAN_AUTH_DENIED"):
            decode_request(raw,self.token,seen)
        with self.assertRaisesRegex(ScanProtocolError,"SCAN_AUTH_DENIED"):
            decode_request(raw,b"x"*32,set())
        with self.assertRaisesRegex(ScanProtocolError,"SCAN_AUTH_DENIED"):
            changed=json.loads(raw)
            changed["params"]=[102]
            decode_request((json.dumps(changed)+"\n").encode("ascii"),
                           self.token,set())

    def test_every_write_or_endpoint_selector_refused_before_network(self):
        for name,params in (
            ("sendrawtransaction",["00"]),("stop",[]),("getnewaddress",[]),
            ("createwallet",["default"]),("getwalletinfo",[]),
            ("generatetoaddress",[1,"abc"]),("dumpprivkey",["key"]),
            ("getblock",["d"*64,2]),("getblockhash",[-1]),
            ("getblock",[None,3]),("rpc",[]),("getblockcount",["wallet"])):
            with self.subTest(name=name,params=params):
                with self.assertRaises(ScanProtocolError):
                    encode_request(self.token,name,params,self.nonce)

    def test_duplicate_fields_and_malformed_frames_refuse(self):
        valid=encode_request(self.token,"getblockcount",[],self.nonce)
        for malformed in (
            valid[:-1], valid+b"x",b"{}\n",b"x"*5000,
            b'{"protocol":"x","protocol":"y"}\n',b"\xff\n"
        ):
            with self.subTest(malformed=malformed[:25]):
                with self.assertRaises(ScanProtocolError):
                    decode_request(malformed,self.token,set())

    def test_response_authenticates_whole_result_and_regtest_only(self):
        signed=encode_reply(self.token,"getblockcount",self.nonce,103)
        self.assertEqual(decode_reply(signed,self.token,"getblockcount",self.nonce),103)
        for value in (b"x"*32,b"a"*32):
            with self.assertRaises(ScanProtocolError):
                decode_reply(signed,value,"getblockcount",self.nonce)
        forged=json.loads(signed)
        for changes in ({"result":104},{"chain":"main"},{"mainnet_allowed":True},
                        {"nonce":"a"*32},{"proof":"0"*64},
                        {"method":"sendrawtransaction"}):
            with self.subTest(changes=changes):
                mutated={**forged,**changes}
                with self.assertRaises(ScanProtocolError):
                    decode_reply((json.dumps(mutated)+"\n").encode("ascii"),
                                 self.token,"getblockcount",self.nonce)

    def test_canonical_decimal_block_roundtrip_preserves_exact_atoms(self):
        value={"height":101,"hash":"a"*64,"tx":[{"txid":"b"*64,
              "vout":[{"value":Decimal("50.00000001")}]}]}
        signed=encode_reply(self.token,"getblock",self.nonce,value)
        actual=decode_reply(signed,self.token,"getblock",self.nonce)
        self.assertEqual(actual["tx"][0]["vout"][0]["value"],"50.00000001")

    def test_oversized_core_result_is_rejected_not_truncated(self):
        value={"height":101,"hash":"a"*64,"tx":[{"x":"x"*MAX_SCAN_REPLY}]}
        with self.assertRaisesRegex(ScanProtocolError,"SCAN_REPLY_TOO_LARGE"):
            encode_reply(self.token,"getblock",self.nonce,value)

    def test_core_supervisor_denies_when_not_owned_before_any_read(self):
        from wam_regtest.core_supervisor import CoreSupervisor,ManagedCoreError
        owner=CoreSupervisor.__new__(CoreSupervisor)
        owner._scan_secret=self.token
        owner._scan_seen=set()
        owner.status=lambda:{"state":"recovery-needed"}
        owner.read=Mock()
        raw=encode_request(self.token,"getblockcount",[],self.nonce)
        with self.assertRaisesRegex(ManagedCoreError,"MANAGED_SCAN_CORE_NOT_READY"):
            owner._scan_handle(raw)
        owner.read.call.assert_not_called()

    def test_real_owner_read_only_and_duplicate_replay_guard(self):
        from wam_regtest.core_supervisor import CoreSupervisor
        owner=CoreSupervisor.__new__(CoreSupervisor)
        owner._scan_secret=self.token;owner._scan_seen=set()
        owner.status=lambda:{"state":"ready"}
        reader=Mock()
        reader.call.return_value=103
        owner.read=reader
        frame=encode_request(self.token,"getblockcount",[],self.nonce)
        data=owner._scan_handle(frame)
        self.assertEqual(decode_reply(data,self.token,"getblockcount",self.nonce),103)
        reader.call.assert_called_once_with("getblockcount",[])
        with self.assertRaisesRegex(ScanProtocolError,"SCAN_AUTH_DENIED"):
            owner._scan_handle(frame)
        self.assertEqual(reader.call.call_count,1)

    def test_client_requires_explicit_consent_and_absolute_root(self):
        with self.assertRaisesRegex(ManagedScanError,"SCAN_CLIENT_CONSENT_OR_ROOT_DENIED"):
            ManagedScanRpc(Path("relative"),authorized_readonly=True)
        with self.assertRaisesRegex(ManagedScanError,"SCAN_CLIENT_CONSENT_OR_ROOT_DENIED"):
            ManagedScanRpc(Path.cwd())


if __name__=="__main__":
    unittest.main()
