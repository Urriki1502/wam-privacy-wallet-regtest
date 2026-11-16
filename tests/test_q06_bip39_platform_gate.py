"""Windows/Linux Q06 frozen qualification refuses source and scope bypass.

These are source-only denial checks. Real-Core, frozen Qt and native witness
acceptance must run inside the final OS-specific package, not this suite.
"""
import tempfile
from pathlib import Path
import unittest

from wam_regtest.q06_platform_probe import (
    Q06PlatformQualificationError, qualify)


class Q06NativePlatformScope(unittest.TestCase):
    def test_source_import_never_grants_frozen_core_qualification(self):
        with tempfile.TemporaryDirectory(prefix="q06-platform-source-") as t:
            parent=Path(t).resolve()
            with self.assertRaisesRegex(
                    Q06PlatformQualificationError,
                    "Q06_PLATFORM_SCOPE_DENIED"):
                qualify(
                    parent/"untrusted-core", parent/"wsp",
                    parent/("wam-fusion-core-"+"a"*16),
                    parent/"receipt.json", confirmed=True)

    def test_windows_native_read_scanners_use_approved_acl_runtime_name(self):
        # Structural regression only; REAL Windows ACL/Qt/Core acceptance is
        # separately required from the final executable on Windows CI.
        import inspect
        from wam_regtest.bip39_owner_backend import Bip39ReadOnlyBackend
        from wam_regtest.bip39_recovery_proof import verify_mnemonic_on_original_chain
        for function in (Bip39ReadOnlyBackend._scan_q06,
                         verify_mnemonic_on_original_chain):
            source=inspect.getsource(function)
            self.assertIn('"wallet-runtime.sqlite"', source)
            self.assertNotIn('"wallet.sqlite"', source)
            self.assertIn('if sys.platform == "win32":', source)
            self.assertIn('create_managed_runtime(', source)
            self.assertLess(source.index('create_managed_runtime('),
                            source.index('Scanner(', source.index('create_managed_runtime(')))
        from wam_regtest.bip39_spend_session import open_owned_spend_session
        spend=inspect.getsource(open_owned_spend_session)
        self.assertIn('create_managed_runtime(', spend)

    def test_missing_explicit_regtest_consent_denied_without_creating_profile(self):
        with tempfile.TemporaryDirectory(prefix="q06-platform-no-consent-") as t:
            parent=Path(t).resolve()
            profile=parent/("wam-fusion-core-"+"b"*16)
            with self.assertRaises(Q06PlatformQualificationError):
                qualify(parent/"core",parent/"source",profile,
                        parent/"proof.json",confirmed=False)
            self.assertFalse(profile.exists())
            self.assertFalse((parent/"proof.json").exists())


if __name__=="__main__":
    unittest.main()
