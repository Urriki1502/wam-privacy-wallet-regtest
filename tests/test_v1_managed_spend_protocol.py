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


class ManagedWalletReadTransportContracts(unittest.TestCase):
    """Supplemental native file-identity negatives; NOT Core E2E evidence."""

    @staticmethod
    def _session():
        from pathlib import Path
        from types import SimpleNamespace
        from unittest.mock import Mock
        from wam_regtest.managed_scan_client import ManagedScanRpc
        from wam_regtest.managed_spend_session import ManagedWalletSession
        session=object.__new__(ManagedWalletSession)
        session.ring=object()
        session.faulted=False
        session.source=Path("/unit-source-not-opened")
        session._managed_root=Path("/unit-supervisor-not-opened")
        reader=object.__new__(ManagedScanRpc)
        reader._root=session._managed_root
        reader.attest=Mock(return_value={"chain":"regtest","blocks":10})
        session._read_rpc=reader
        session.vault=SimpleNamespace(
            anchor=SimpleNamespace(read=Mock(return_value="original-native-anchor")),
            _expected="original-native-anchor",
        )
        session._core_member_paths=(Path("/unit-node-not-opened"),
                                    Path("/unit-cli-not-opened"))
        session._core_member_metadata=("node-identity","cli-identity")
        session._verified_core_receipt={
            "platform":"macos-arm64","wamd_sha256":"a"*64,
        }
        return session,reader

    def test_managed_reads_reuse_one_time_signed_receipt_without_full_rehash(self):
        from unittest.mock import patch
        session,reader=self._session()
        status={"state":"ready","core_process_owned":True}
        with (patch("wam_regtest.managed_spend_session._pinned_source"),
              patch("wam_regtest.core_process._metadata",
                    side_effect=["node-identity","cli-identity"]) as metadata,
              patch("wam_regtest.custody.platform_name",return_value="macos-arm64"),
              patch("wam_regtest.supervisor_client.control",return_value=status) as control,
              patch("wam_regtest.core.verified_core_paths",
                    side_effect=AssertionError("PER_READ_CORE_REHASH_FORBIDDEN"))):
            rpc,receipt=session._read()
        self.assertIs(rpc,reader)
        self.assertIs(receipt,session._verified_core_receipt)
        self.assertFalse(session.faulted)
        self.assertEqual(metadata.call_count,2)
        control.assert_called_once()
        reader.attest.assert_called_once()

    def test_native_node_or_cli_replacement_faults_before_network(self):
        from unittest.mock import patch
        from wam_regtest.managed_spend_session import ManagedWalletSpendError
        for changed in (("replaced-node","cli-identity"),
                        ("node-identity","replaced-cli")):
            with self.subTest(changed=changed):
                session,reader=self._session()
                with (patch("wam_regtest.managed_spend_session._pinned_source"),
                      patch("wam_regtest.core_process._metadata",side_effect=changed),
                      patch("wam_regtest.custody.platform_name",return_value="macos-arm64"),
                      patch("wam_regtest.supervisor_client.control") as control):
                    with self.assertRaisesRegex(
                            ManagedWalletSpendError,"^MANAGED_SPEND_CORE_CHANGED$"):
                        session._read()
                self.assertTrue(session.faulted)
                control.assert_not_called()
                reader.attest.assert_not_called()

    def test_missing_one_time_identity_fails_closed(self):
        from unittest.mock import patch
        from wam_regtest.managed_spend_session import ManagedWalletSpendError
        session,reader=self._session()
        del session._core_member_metadata
        with (patch("wam_regtest.managed_spend_session._pinned_source"),
              patch("wam_regtest.core_process._metadata") as metadata,
              patch("wam_regtest.custody.platform_name",return_value="macos-arm64"),
              patch("wam_regtest.supervisor_client.control") as control):
            with self.assertRaisesRegex(
                    ManagedWalletSpendError,"^MANAGED_SPEND_CORE_CHANGED$"):
                session._read()
        self.assertTrue(session.faulted)
        control.assert_not_called()
        reader.attest.assert_not_called()
