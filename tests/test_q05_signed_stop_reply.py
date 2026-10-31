"""Regression for the exact public stop reply in pinned signed Core v0.1.11."""
import unittest
from wam_regtest.cli_rpc import decode, validate, CliRpcError


class SignedStopContracts(unittest.TestCase):
    def test_pinned_and_legacy_literals_only(self):
        for reply in (b'WAM Coin stopping\n', b'WAM Core stopping\n'):
            self.assertEqual(decode(reply,'stop',[]),reply.decode().strip())
        for reply in (b'Core stopping',b'WAM Coin stopping evil',b'true',b'null',
                      b'',b'WAM Coin stopping\nsecret',b'Bitcoin Core stopping'):
            with self.assertRaises(CliRpcError):decode(reply,'stop',[])

    def test_stop_still_has_no_wallet_or_parameter_override(self):
        self.assertEqual(validate(['stop']),('stop',[]))
        for args in (['stop','true'],['-rpcwallet=test','stop'],['stop','-rpcconnect=remote']):
            with self.assertRaises(CliRpcError):validate(args)
