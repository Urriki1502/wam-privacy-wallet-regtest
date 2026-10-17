"""Acceptance-client consent/input negatives; not genuine-Core acceptance."""
from pathlib import Path
import subprocess
import sys
import unittest

from wam_regtest.managed_gui_probe import probe


class GuiProcessProbeScope(unittest.TestCase):
    def test_refuses_without_explicit_probe_consent_before_importing_qt(self):
        child = subprocess.run([sys.executable, "-m", "wam_regtest.managed_gui_probe",
            "--root", "untrusted-root", "--expected-height", "101"],
            capture_output=True, timeout=15)
        self.assertEqual(child.returncode, 2)
        self.assertEqual(child.stdout, b"")

    def test_invalid_root_height_and_mode_refused_before_gui_or_connection(self):
        root = Path("C:/wam-fusion-core-0123456789abcdef" if sys.platform == "win32"
                    else "/tmp/wam-fusion-core-0123456789abcdef")
        for height in (True, -1, 1_000_001, "101"):
            with self.assertRaisesRegex(ValueError, "T05_GUI_PROBE_HEIGHT_DENIED"):
                probe(root, height)
        with self.assertRaisesRegex(ValueError, "T05_GUI_PROBE_HEIGHT_DENIED"):
            probe(root, 101, wait_for_crash=1)
        with self.assertRaisesRegex(ValueError, "SUPERVISOR_STORAGE_ROOT_DENIED"):
            probe(Path("external-core"), 101)
