"""v0.1.12 genuine-release *candidate* read tests; never enable wallet runtime."""
import json
import unittest
from unittest.mock import patch

from wam_regtest.json_rpc import RpcError, SUPPORTED_RPC, _reply
from wam_regtest.v012_candidate_compat import (
    CANDIDATE_VERSION, CANDIDATE_LINUX_ARCHIVE_SHA,
    CANDIDATE_LINUX_WAMD_SHA, CANDIDATE_LINUX_CLI_SHA, CANDIDATE_SIGNER,
    Candidate012Denied, candidate_network_reply, candidate_scope_status,
    exact_signed_linux_candidate,
)
from wam_regtest.v012_candidate_http import _auth
from wam_regtest.wsp_live import REGTEST_GENESIS


class Candidate012ReadContracts(unittest.TestCase):
    def _linux_identity(self, **changes):
        args=dict(
            signed_archive=True, signer=CANDIDATE_SIGNER,
            archive_sha=CANDIDATE_LINUX_ARCHIVE_SHA,
            node_sha=CANDIDATE_LINUX_WAMD_SHA, cli_sha=CANDIDATE_LINUX_CLI_SHA,
            process_is_owned=True, chain="regtest", genesis=REGTEST_GENESIS, peers=0)
        args.update(changes)
        return exact_signed_linux_candidate(**args)

    @staticmethod
    def _wire(info=None, identifier=1):
        if info is None:info={"version":112,"subversion":"/WAM:0.1.12/",
                              "protocolversion":70016}
        return json.dumps({"id":identifier,"error":None,"result":info}).encode()

    def test_exact_measured_linux_identity_only(self):
        self.assertIsNone(self._linux_identity())
        for item in ("signed_archive","signer","archive_sha","node_sha","cli_sha",
                     "process_is_owned","chain","genesis","peers"):
            value={"signed_archive":False,"signer":"untrusted",
                   "archive_sha":"0"*64,"node_sha":"0"*64,"cli_sha":"0"*64,
                   "process_is_owned":False,"chain":"main","genesis":"0"*64,
                   "peers":1}[item]
            with self.subTest(item=item), self.assertRaisesRegex(
                    Candidate012Denied,"^V012_CANDIDATE_LINUX_IDENTITY_DENIED$"):
                self._linux_identity(**{item:value})

    def test_candidate_version_is_not_implicitly_whitelisted_in_wallet(self):
        self.assertEqual(CANDIDATE_VERSION,(112,"/WAM:0.1.12/",70016))
        self.assertEqual(SUPPORTED_RPC,(111,"/WAM:0.1.11/",70016))
        raw=self._wire()
        self.assertEqual(candidate_network_reply(raw,1)["version"],112)
        with self.assertRaisesRegex(RpcError,"^RPC_VERSION_CAPABILITY_DENIED$"):
            _reply(raw,1,"getnetworkinfo")

    def test_reject_old_and_unmeasured_versions(self):
        for value in ({"version":111,"subversion":"/WAM:0.1.11/","protocolversion":70016},
                      {"version":112,"subversion":"/Bitcoin:0.1.12/","protocolversion":70016},
                      {"version":112,"subversion":"/WAM:0.1.12/","protocolversion":70015},
                      {"version":113,"subversion":"/WAM:0.1.13/","protocolversion":70016},
                      {"version":True,"subversion":"/WAM:0.1.12/","protocolversion":70016}):
            with self.subTest(value=value),self.assertRaises(Candidate012Denied):
                candidate_network_reply(self._wire(value),1)

    def test_malformed_duplicate_unknown_or_mismatched_rpc_denied(self):
        examples=[
            b'{"id":1,"id":1,"result":{},"error":null}',
            b'{"id":1,"result":{},"error":null,"secret":"leak"}',
            self._wire(identifier=2),
            b'{"id":1,"result":{},"error":{"message":"SECRET"}}',
            b'not json', b'NaN', b'{}',
            b'x'*(1024*1024+1),
        ]
        for raw in examples:
            with self.subTest(raw=raw[:20]),self.assertRaisesRegex(
                    Candidate012Denied,"^V012_CANDIDATE_REPLY_DENIED$"):
                candidate_network_reply(raw,1)

    def test_bad_identifier_denied_before_parsing(self):
        for ident in (-1,0,True,1001,"1",None):
            with self.subTest(ident=ident),self.assertRaises(Candidate012Denied):
                candidate_network_reply(self._wire(),ident)

    def test_version_component_does_not_activate_wallet(self):
        flags=candidate_scope_status()
        self.assertTrue(flags["v011_application_pin_unchanged"])
        self.assertTrue(flags["test_only"])
        for key in ("fusion_v012_activated","macos_v012_qualified",
                    "windows_v012_qualified","wsp_gui_signing_qualified",
                    "user_core_install_authorized","mainnet_allowed"):
            self.assertIs(flags[key],False)

    def test_refuse_untrusted_rpc_config_before_auth(self):
        with patch("wam_regtest.v012_candidate_http._private_config",
                   return_value=b"rpcuser=test\nrpcpassword=bad\n"):
            with self.assertRaisesRegex(Candidate012Denied,"V012_CANDIDATE_CONFIG_DENIED"):
                _auth(None)

    def test_accept_only_bounded_generated_rpc_credentials(self):
        with patch("wam_regtest.v012_candidate_http._private_config",
                   return_value=(b"regtest=1\nserver=1\n[regtest]\n"
                                 b"rpcuser=disposable_1234567890abcdef\n"
                                 b"rpcpassword="+b"a"*64+b"\n")):
            digest,header=_auth(None)
            self.assertEqual(len(digest),32)
            self.assertTrue(header.startswith("Basic "))
            self.assertNotIn("disposable_",header)


if __name__=="__main__":
    unittest.main()
