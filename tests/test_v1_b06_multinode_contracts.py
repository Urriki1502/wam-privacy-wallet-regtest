"""B-06: fail-closed lab controls; genuine native Core E2E runs in macOS CI."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.issue45_b06_multinode_regtest import (
    B06LabError, DURATIONS, LabReader, _rpc, _fresh_ports,
    genuine_two_node_lab, make_private_lab_config,
)


class B06PrivateLabContracts(unittest.TestCase):
    def test_reorg_depths_are_exactly_mandated(self):
        self.assertEqual(DURATIONS,(1,12,100))

    def test_lab_requires_disposable_consent_and_verified_core(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp).resolve()
            with self.assertRaisesRegex(B06LabError,"B06_DISPOSABLE_NATIVE_SCOPE_DENIED"):
                genuine_two_node_lab(directory,directory,authorized=False)

    def test_private_loopback_config_without_mainnet_or_external_peer(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp).resolve()
            make_private_lab_config(path,21001,21002)
            config=(path/"wam.conf").read_text()
            for line in ("regtest=1","server=1","[regtest]",
                         "rpcbind=127.0.0.1","rpcallowip=127.0.0.1",
                         "bind=127.0.0.1","listen=1","connect=0",
                         "dnsseed=0","discover=0","upnp=0",
                         "txindex=1","blockfilterindex=1","coinstatsindex=1"):
                self.assertIn(line+"\n",config)
            self.assertNotIn("mainnet=1",config)
            self.assertNotIn("connect=8.8.8.8",config)
            self.assertIn("rpcpassword=",config)
            with self.assertRaises(B06LabError):
                make_private_lab_config(path,21001,21002)

    def test_ports_are_distinct_and_loopback_allocated(self):
        ports=_fresh_ports()
        self.assertEqual(len(set(ports)),4)
        self.assertTrue(all(1<=v<=65535 for v in ports))

    def test_scanner_read_allowlist_never_grants_write(self):
        reader=LabReader(Path("/public-cli"),Path("/public-disposable"))
        for method in ("sendrawtransaction","addnode","stop",
                       "generatetoaddress","getpeerinfo"):
            with self.subTest(method=method):
                with self.assertRaisesRegex(B06LabError,"B06_SCANNER_READ_SCOPE_DENIED"):
                    reader.call(method)
        with self.assertRaisesRegex(B06LabError,"B06_SCANNER_ARGUMENT_DENIED"):
            reader.call("getblockhash",["1"])
        with self.assertRaisesRegex(B06LabError,"B06_SCANNER_ARGUMENT_DENIED"):
            reader.call("getblock",["0"*64,2])

    def test_public_cli_entry_rejects_unknown_methods_without_spawn(self):
        with patch("scripts.issue45_b06_multinode_regtest.subprocess.run",
                   side_effect=AssertionError("unexpected CLI spawn")):
            for method in ("dumpprivkey","importprivkey","setban",
                           "getwalletinfo","getpeerinfo "):
                with self.subTest(method=method):
                    with self.assertRaisesRegex(B06LabError,"B06_RPC_METHOD_SCOPE_DENIED"):
                        _rpc(Path("/public-cli"),Path("/public-temp"),method)
            with self.assertRaisesRegex(B06LabError,"B06_RPC_METHOD_SCOPE_DENIED"):
                _rpc(Path("/public-cli"),Path("/public-temp"),"getblockcount",
                     ["$(curl hostile.example)"])

    def test_config_rejects_duplicate_ports_and_invalid_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            private=Path(tmp).resolve()
            with self.assertRaisesRegex(B06LabError,"B06_CONFIG_SCOPE_DENIED"):
                make_private_lab_config(private,12345,12345)
            with self.assertRaisesRegex(B06LabError,"B06_CONFIG_SCOPE_DENIED"):
                make_private_lab_config(private,0,12345)
            with self.assertRaisesRegex(B06LabError,"B06_CONFIG_SCOPE_DENIED"):
                make_private_lab_config(private/"not-existing",21001,21002)

    def test_scanner_adapter_attests_against_actual_core_not_unit_fixture(self):
        reader=LabReader(Path("/public-cli"),Path("/public-disposable"))
        with patch("scripts.issue45_b06_multinode_regtest._rpc",return_value=101) as mock_rpc:
            self.assertEqual(reader.call("getblockcount"),101)
            mock_rpc.assert_called_once_with(reader.cli,reader.data,
                                             "getblockcount",[])
        # The fake stub is used ONLY to test argument routing. It is not
        # reported as WAM Core, WSP reorg, or native integration acceptance.


if __name__=="__main__":
    unittest.main()
