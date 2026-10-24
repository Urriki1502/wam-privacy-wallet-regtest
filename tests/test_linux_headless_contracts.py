"""Supplementary text-approval and no-terminal refusal, not Core E2E."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from wam_regtest.linux_headless import HeadlessWallet,passphrase
from wam_regtest.wallet_session import WalletSessionError


class HeadlessApprovalContracts(unittest.TestCase):
    def test_default_or_wrong_commitment_cannot_reach_backend(self):
        # Absence of backend methods proves refusal happens before authority.
        front=HeadlessWallet(SimpleNamespace())
        front.review=SimpleNamespace(commitment='a'*64)
        for text in ('','yes','SIGN','SIGN '+'b'*64):
            with self.assertRaises(WalletSessionError):front.sign(text)
        front.signed=True
        for text in ('','yes','BROADCAST','BROADCAST '+'b'*64):
            with self.assertRaises(WalletSessionError):front.broadcast(text)
    def test_passphrase_never_falls_back_to_non_terminal_input(self):
        with patch('sys.stdin.isatty',return_value=False):
            with self.assertRaisesRegex(WalletSessionError,'PRIVATE_TERMINAL'):passphrase('passphrase')
