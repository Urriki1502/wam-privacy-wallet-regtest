"""Cross-session recovery denials carry only fixed public diagnostic tokens."""
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class RecoveryDenialDiagnostics(unittest.TestCase):
    def test_stage_and_cause_are_fixed_public_tokens(self):
        import importlib.util
        from wam_regtest.wallet_session import WalletSession, WalletSessionError
        source = Path(importlib.util.find_spec("wam_sp").origin).resolve().parents[2]
        storage = mock.Mock()
        storage.read.side_effect = OSError("/private/secret/path PUBLIC_SECRET_TEXT")
        with tempfile.TemporaryDirectory() as d, \
                mock.patch("wam_regtest.wallet_session.custody.storage", return_value=storage):
            with self.assertRaises(WalletSessionError) as caught:
                WalletSession.from_backup(Path(d), Path(d), source, Path(d), "x.enc",
                                          b"public-test-password", None, authorized=True)
        error = caught.exception
        self.assertEqual(error.args, ("WALLET_CROSS_SESSION_RECOVERY_DENIED",))
        self.assertEqual((error.recovery_stage, error.recovery_cause), ("READ", "OSError"))
        self.assertTrue(error.__suppress_context__)
        for token in (error.recovery_stage, error.recovery_cause):
            self.assertRegex(token, r"^[A-Za-z0-9_]{1,80}$")
            self.assertNotIn("SECRET", token)

    def test_public_codes_pass_through_only_when_fixed_uppercase(self):
        from wam_regtest.wallet_session import WalletSession, WalletSessionError
        import importlib.util
        source = Path(importlib.util.find_spec("wam_sp").origin).resolve().parents[2]
        storage = mock.Mock()
        storage.read.return_value = b"x"
        with tempfile.TemporaryDirectory() as d, \
                mock.patch("wam_regtest.wallet_session.custody.storage", return_value=storage), \
                mock.patch("wam_sp.keystore.unseal", side_effect=ValueError("KEYSTORE_AUTH")):
            with self.assertRaises(WalletSessionError) as caught:
                WalletSession.from_backup(Path(d), Path(d), source, Path(d), "x.enc",
                                          b"public-test-password", None, authorized=True)
        self.assertEqual((caught.exception.recovery_stage, caught.exception.recovery_cause),
                         ("READ", "KEYSTORE_AUTH"))


    def test_q06_open_denial_carries_only_a_fixed_stage(self):
        from wam_regtest.bip39_spend_session import open_owned_spend_session, Q06SpendSessionError
        from types import SimpleNamespace
        with mock.patch("wam_regtest.bip39_spend_session._owned_password"), \
                mock.patch("wam_regtest.bip39_spend_session._owned"), \
                mock.patch("wam_regtest.bip39_spend_session.open_owned_seed_container",
                           side_effect=OSError("/secret/path PUBLIC_SECRET")):
            with self.assertRaises(Q06SpendSessionError) as caught:
                open_owned_spend_session(SimpleNamespace(), Path("/x"), Path("/x"), b"p" * 12,
                                         authorized=True)
        self.assertEqual(caught.exception.args, ("Q06_SPEND_OPEN_DENIED",))
        self.assertEqual(caught.exception.open_stage, "SEED_AUTH")
        self.assertTrue(caught.exception.__suppress_context__)

if __name__ == "__main__":
    unittest.main()
