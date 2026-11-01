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
