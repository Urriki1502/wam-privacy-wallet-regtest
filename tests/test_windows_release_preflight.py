"""Portable negative-only Windows release preflight tests (NOT Win64 E2E)."""
import hashlib
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile

from wam_regtest.windows_release_preflight import (
    ROOT, MEMBERS, WindowsReleaseError, _validate_amd64_pe,
    inspect_signed_zip_shape,
)


def fixture_pe(*, machine=0x8664, magic=b"\x0b\x02"):
    b = bytearray(512)
    b[:2] = b"MZ"
    struct.pack_into("<I", b, 0x3C, 0x80)
    b[0x80:0x84] = b"PE\x00\x00"
    struct.pack_into("<HHIIIHH", b, 0x84, machine, 2, 0, 0, 0, 0xF0, 0x0002)
    b[0x98:0x9A] = magic
    return bytes(b)


class WinReleasePreflightTests(unittest.TestCase):
    def _archive(self, *entries):
        home = tempfile.TemporaryDirectory()
        path = Path(home.name) / "source.zip"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            for name, value in (entries or [(name, fixture_pe()) for name in MEMBERS]):
                z.writestr(name, value)
        return home, path, hashlib.sha256(path.read_bytes()).hexdigest()

    def test_structural_pe_rejects_wrong_machine_magic_and_missing_headers(self):
        _validate_amd64_pe(fixture_pe())
        for bad in (b"\0"*512, fixture_pe(machine=0x14c), fixture_pe(magic=b"\x0b\x01")):
            with self.subTest(bad=bad[:4]), self.assertRaises(WindowsReleaseError):
                _validate_amd64_pe(bad)

    def test_fixture_only_produces_no_authority_receipt(self):
        home, path, digest = self._archive()
        try:
            result = inspect_signed_zip_shape(path, digest)
            self.assertEqual(len(result["member_sha256"]), 2)
            self.assertFalse(result["real_core_e2e_qualified"])
            self.assertFalse(result["wallet_signing_authorized"])
            self.assertFalse(result["native_windows_tests_passed"])
            self.assertNotIn("signed_archive_verified", result)
        finally:
            home.cleanup()

    def test_changed_archive_digest_rejected(self):
        home, path, digest = self._archive()
        try:
            with self.assertRaisesRegex(WindowsReleaseError, "WIN_RELEASE_ARCHIVE_DIGEST_DENIED"):
                inspect_signed_zip_shape(path, "0"*64 if digest != "0"*64 else "f"*64)
        finally:
            home.cleanup()

    def test_missing_binary_rejected(self):
        home, path, digest = self._archive((f"{ROOT}/bin/wamd.exe", fixture_pe()))
        try:
            with self.assertRaisesRegex(WindowsReleaseError, "WIN_RELEASE_ENTRY_COUNT_DENIED|WIN_RELEASE_MEMBERS_MISSING"):
                inspect_signed_zip_shape(path, digest)
        finally:
            home.cleanup()

    def test_zip_traversal_and_duplicate_case_denied(self):
        cases = [
            [(f"{ROOT}/bin/wamd.exe", fixture_pe()), (f"{ROOT}/bin/wam-cli.exe", fixture_pe()), (f"{ROOT}/../evil.txt", b"bad")],
            [(f"{ROOT}/bin/wamd.exe", fixture_pe()), (f"{ROOT}/bin/wam-cli.exe", fixture_pe()), (f"{ROOT}/bin/WAMD.EXE", fixture_pe())],
            [(f"{ROOT}\\bin\\wamd.exe", fixture_pe()), (f"{ROOT}/bin/wam-cli.exe", fixture_pe())]
        ]
        for rows in cases:
            with self.subTest(case=rows[-1][0]):
                home, path, digest = self._archive(*rows)
                try:
                    with self.assertRaises(WindowsReleaseError):
                        inspect_signed_zip_shape(path, digest)
                finally:
                    home.cleanup()

    def test_cannot_claim_signed_integrity_with_untrusted_key(self):
        # No verifier bypass: no signature/public-key inputs are supplied here.
        home, path, digest = self._archive()
        try:
            result = inspect_signed_zip_shape(path, digest)
            self.assertNotIn("signed_archive_verified", result)
            with self.assertRaises(WindowsReleaseError):
                inspect_signed_zip_shape(path, "BAD_DIGEST")
        finally:
            home.cleanup()


if __name__ == "__main__":
    unittest.main()
