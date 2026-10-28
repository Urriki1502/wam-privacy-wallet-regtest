"""Supplementary text-approval and no-terminal refusal, not Core E2E."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from wam_regtest.linux_headless import HeadlessWallet,passphrase,history_view
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
    def test_history_view_keeps_complete_counts_outside_the_window(self):
        from wam_regtest.wallet_read import HistoryRow,WalletReadSnapshot
        rows=(HistoryRow('b'*64,104,2,1,0),)
        snap=WalletReadSnapshot('regtest',105,'a'*64,'wamrtsp1-public',1,1,rows,'c'*64,
            history_count=900,history_complete=False,receive_count=40,history_offset=250)
        view=history_view(snap)
        self.assertEqual(view['history_count'],900)
        self.assertEqual(view['receive_count'],40)
        self.assertEqual(view['history_offset'],250)
        self.assertEqual(len(view['rows']),1)
    def test_passphrase_never_falls_back_to_non_terminal_input(self):
        with patch('sys.stdin.isatty',return_value=False):
            with self.assertRaisesRegex(WalletSessionError,'PRIVATE_TERMINAL'):passphrase('passphrase')
