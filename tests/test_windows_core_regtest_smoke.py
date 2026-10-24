"""Negative/offline contracts for native REAL Windows Core smoke; no node exec."""
import hashlib
from pathlib import Path
import tempfile
import unittest
import zipfile

from wam_regtest.windows_core_regtest_smoke import (
    WindowsCoreSmokeError, _staged_signed_binaries, smoke_signed_windows_regtest,
)
from wam_regtest.windows_release_preflight import ROOT


class WindowsCoreSmokeContracts(unittest.TestCase):
    def test_explicit_consent_is_required_before_any_file_or_process(self):
        missing = Path("NONEXISTENT-WAM-TEST-INPUT")
        for flag in (False, None, 1, "true"):
            with self.subTest(consent=flag), self.assertRaisesRegex(
                WindowsCoreSmokeError, "^WIN_CORE_EXPLICIT_CONSENT_REQUIRED$"
            ):
                smoke_signed_windows_regtest(
                    missing, missing, missing, missing, consent=flag)

    def test_timeout_is_bounded_before_any_file_or_process(self):
        missing = Path("NONEXISTENT-WAM-TEST-INPUT")
        for limit in (0, 29, 241, True, "120"):
            with self.subTest(timeout=limit), self.assertRaisesRegex(
                WindowsCoreSmokeError, "^WIN_CORE_EXPLICIT_CONSENT_REQUIRED$"
            ):
                smoke_signed_windows_regtest(
                    missing, missing, missing, missing, consent=True, timeout=limit)

    def test_staging_rejects_invalid_member_hash_without_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "fixture.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr(f"{ROOT}/bin/wamd.exe", b"fixture-node")
                z.writestr(f"{ROOT}/bin/wam-cli.exe", b"fixture-cli")
            receipt = {
                "member_sha256": {
                    "wamd.exe": "0" * 64,
                    "wam-cli.exe": hashlib.sha256(b"fixture-cli").hexdigest(),
                }
            }
            with self.assertRaisesRegex(WindowsCoreSmokeError, "^WIN_CORE_STAGED_HASH_DENIED$"):
                _staged_signed_binaries(archive, receipt, root / "stage")

    def test_staging_rejects_existing_directory_without_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            stage = root / "stage"
            stage.mkdir()
            marker = stage / "original"
            marker.write_text("preserve")
            with self.assertRaisesRegex(WindowsCoreSmokeError, "^WIN_CORE_STAGE_EXISTS_DENIED$"):
                _staged_signed_binaries(root / "missing.zip", {}, stage)
            self.assertEqual(marker.read_text(), "preserve")


if __name__ == "__main__":
    unittest.main()
