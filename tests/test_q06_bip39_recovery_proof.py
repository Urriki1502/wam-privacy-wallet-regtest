"""Q06 recovery proof contracts: mnemonic does not grant native signing.

The positive funded/history proof belongs to the real signed-Core macOS frozen
job; these source negatives must not be mistaken for external acceptance.
"""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import tempfile
import unittest

from mnemonic import Mnemonic
from wam_regtest.bip39_12 import Bip39Regtest12Keys
from wam_regtest.bip39_recovery_proof import (
    Q06RecoveryProofError, verify_mnemonic_on_original_chain)

SOURCE = Path(importlib.util.find_spec("wam_sp").origin).resolve().parents[2]


class Q06RecoveryProofContracts(unittest.TestCase):
    def test_missing_authenticated_original_chain_baseline_fails_before_io(self):
        with self.assertRaisesRegex(
                Q06RecoveryProofError, "Q06_RECOVERY_INPUT_OR_BASELINE_DENIED"):
            verify_mnemonic_on_original_chain(
                object(), SOURCE, Mnemonic("english").to_mnemonic(bytes(16)),
                SimpleNamespace(chain="regtest", signer_allowed=False))

    def test_wrong_twelve_words_never_create_scanner_or_signing_grant(self):
        phrase = Mnemonic("english").to_mnemonic(bytes(16))
        foreign = Mnemonic("english").to_mnemonic(bytes([1] * 16))
        with Bip39Regtest12Keys(
                phrase, source=SOURCE, authorized_disposable=True) as keys:
            receive = keys.public_metadata()["receive_code"]
        with tempfile.TemporaryDirectory(prefix="q06-recovery-source-") as root:
            directory = Path(root)
            owner = SimpleNamespace(directory=directory)
            baseline = SimpleNamespace(
                chain="regtest", signer_allowed=True,
                history_count=1, history_sha256="0" * 64,
                receive_code=receive)
            with patch("wam_regtest.bip39_recovery_proof._owned"):
                with self.assertRaisesRegex(
                        Q06RecoveryProofError,
                        "Q06_RECOVERY_MNEMONIC_IDENTITY_DENIED"):
                    verify_mnemonic_on_original_chain(
                        owner, SOURCE, foreign, baseline)
            self.assertEqual(list(directory.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
