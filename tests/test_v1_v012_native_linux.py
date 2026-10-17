"""Issue45 PR57: negative-only safety tests, not proof of actual native Core."""
import io
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from scripts.issue45_v012_native_linux import (
    _prerequisites, _member_copy, Native012Denied)


class CIOnlyExecutionContract(unittest.TestCase):
    def test_explicit_operator_and_ci_gate_required(self):
        with self.assertRaisesRegex(Native012Denied, "V012_NATIVE_RUNNER_SCOPE_DENIED"):
            _prerequisites(False)
        with patch.dict(os.environ, {"CI": "false", "GITHUB_ACTIONS": "false",
                                      "WAM_SOURCE_HEAD": "candidate"}, clear=True):
            with self.assertRaisesRegex(Native012Denied, "V012_NATIVE_RUNNER_SCOPE_DENIED"):
                _prerequisites(True)

    @unittest.skipUnless(sys.platform == "linux", "actual Linux native fixture only")
    def test_untrusted_member_symlink_rejected_without_execution(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            bundle = root / "invalid.tar.gz"
            with tarfile.open(bundle, "w:gz") as tar:
                for leaf in ("wamd", "wam-cli"):
                    m = tarfile.TarInfo("wam-coin-v0.1.12/bin/" + leaf)
                    m.type = tarfile.SYMTYPE
                    m.linkname = "/etc/passwd"
                    tar.addfile(m)
            with self.assertRaisesRegex(Native012Denied, "V012_NATIVE_BINARY_MEMBER_DENIED"):
                _member_copy(bundle, root)

    @unittest.skipUnless(sys.platform == "linux", "actual Linux native fixture only")
    def test_wrong_elf_header_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            bundle = root / "fake.tar.gz"
            with tarfile.open(bundle, "w:gz") as tar:
                for leaf in ("wamd", "wam-cli"):
                    payload = b"not-a-wam-binary"
                    m = tarfile.TarInfo("wam-coin-v0.1.12/bin/" + leaf)
                    m.size = len(payload)
                    tar.addfile(m, io.BytesIO(payload))
            with self.assertRaisesRegex(Native012Denied, "V012_NATIVE_ELF_AMD64_DENIED"):
                _member_copy(bundle, root)

    def test_mismatched_checkout_sha_fails_closed_before_network(self):
        if sys.platform != "linux":
            self.skipTest("native Linux checkout contract only")
        with patch.dict(os.environ, {"CI": "true", "GITHUB_ACTIONS": "true",
                                      "WAM_SOURCE_HEAD": "0" * 40}):
            with patch("scripts.issue45_v012_native_linux.subprocess.run",
                       return_value=subprocess.CompletedProcess([], 0, "not-head\n", "")):
                with self.assertRaisesRegex(Native012Denied, "V012_NATIVE_HEAD_DENIED"):
                    _prerequisites(True)


if __name__ == "__main__":
    unittest.main()
