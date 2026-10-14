"""Offline deterministic failure-injection tests for real hdiutil packaging.

These tests never claim REAL macOS packaging success. The actual Apple Silicon
job must still execute hdiutil create + verify on the final frozen application.
"""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest


_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "create_verified_dmg.py"
_spec = importlib.util.spec_from_file_location("wam_test_dmg_creator", _SCRIPT)
_dmg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_dmg)


class DmgReleaseContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.parent = Path(self.tmp.name).resolve()
        self.app = self.parent / "WAM Privacy Wallet REGTEST.app"
        self.app.mkdir()
        self.output = self.parent / "WAM-Privacy-Wallet-REGTEST-macOS-ARM64.dmg"
        self.delays = []

    def fake(self, create_results=(0,), verify_result=0, write_image=True):
        state = {"create": 0, "verify": 0}
        def runner(cmd, **kwargs):
            self.assertEqual(cmd[0], "hdiutil")
            self.assertTrue(kwargs.get("capture_output"))
            self.assertTrue(kwargs.get("check") is False)
            self.assertGreaterEqual(kwargs.get("timeout", 0), 1)
            if cmd[1] == "create":
                ix = state["create"]
                state["create"] += 1
                kind = create_results[min(ix, len(create_results)-1)]
                if kind == "busy":
                    return subprocess.CompletedProcess(cmd, 1, "", "hdiutil: create failed - Resource busy")
                if kind == "error":
                    return subprocess.CompletedProcess(cmd, 1, "", "unrelated failure")
                if kind == "timeout":
                    raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])
                if kind == 0 and write_image:
                    Path(cmd[-1]).write_bytes(b"DMG" + b"A"*4096)
                return subprocess.CompletedProcess(cmd, 0, "", "")
            self.assertEqual(cmd[1], "verify")
            state["verify"] += 1
            return subprocess.CompletedProcess(cmd, verify_result, "", "")
        return state, runner

    def test_busy_once_then_real_verify_and_atomic_publish(self):
        state, runner = self.fake(("busy", 0))
        n = _dmg.create_verified_dmg(self.app, self.output, runner=runner, sleeper=self.delays.append)
        self.assertEqual(n, 2)
        self.assertEqual(state, {"create": 2, "verify": 1})
        self.assertEqual(self.delays, [2])
        self.assertTrue(self.output.read_bytes().startswith(b"DMG"))
        self.assertFalse(list(self.parent.glob(".wam-dmg-build-*")))

    def test_busy_three_times_fail_closed_and_preserve_old_artifact(self):
        self.output.write_bytes(b"OLD-DMG")
        state, runner = self.fake(("busy",))
        with self.assertRaisesRegex(_dmg.DmgBuildError, "DMG_CREATE_RESOURCE_BUSY_EXHAUSTED"):
            _dmg.create_verified_dmg(self.app, self.output, runner=runner, sleeper=self.delays.append)
        self.assertEqual(state, {"create": 3, "verify": 0})
        self.assertEqual(self.output.read_bytes(), b"OLD-DMG")
        self.assertEqual(self.delays, [2, 4])

    def test_other_create_error_is_not_retried(self):
        state, runner = self.fake(("error", 0))
        with self.assertRaisesRegex(_dmg.DmgBuildError, "DMG_CREATE_NONTRANSIENT_FAILURE"):
            _dmg.create_verified_dmg(self.app, self.output, runner=runner, sleeper=self.delays.append)
        self.assertEqual(state, {"create": 1, "verify": 0})
        self.assertFalse(self.output.exists())
        self.assertEqual(self.delays, [])

    def test_failed_verify_does_not_publish_partial_artifact(self):
        self.output.write_bytes(b"OLD-DMG")
        state, runner = self.fake((0,), verify_result=1)
        with self.assertRaisesRegex(_dmg.DmgBuildError, "DMG_VERIFY_FAILED"):
            _dmg.create_verified_dmg(self.app, self.output, runner=runner, sleeper=self.delays.append)
        self.assertEqual(state, {"create": 1, "verify": 1})
        self.assertEqual(self.output.read_bytes(), b"OLD-DMG")

    def test_missing_or_too_short_output_is_rejected(self):
        _, runner = self.fake((0,), write_image=False)
        with self.assertRaisesRegex(_dmg.DmgBuildError, "DMG_CREATE_OUTPUT_INVALID"):
            _dmg.create_verified_dmg(self.app, self.output, runner=runner, sleeper=self.delays.append)
        self.assertFalse(self.output.exists())

    def test_timeout_does_not_retry(self):
        state, runner = self.fake(("timeout",))
        with self.assertRaisesRegex(_dmg.DmgBuildError, "DMG_CREATE_PROCESS_DENIED"):
            _dmg.create_verified_dmg(self.app, self.output, runner=runner, sleeper=self.delays.append)
        self.assertEqual(state, {"create": 1, "verify": 0})

    def test_refuse_symlink_or_bad_destination_before_subprocess(self):
        state, runner = self.fake()
        link = self.parent / "not-a-real-app.app"
        link.symlink_to(self.app, target_is_directory=True)
        with self.assertRaisesRegex(_dmg.DmgBuildError, "DMG_INPUT_SCOPE_DENIED"):
            _dmg.create_verified_dmg(link, self.output, runner=runner)
        with self.assertRaisesRegex(_dmg.DmgBuildError, "DMG_INPUT_SCOPE_DENIED"):
            _dmg.create_verified_dmg(self.app, self.parent / "invalid.zip", runner=runner)
        self.assertEqual(state, {"create": 0, "verify": 0})


if __name__ == "__main__":
    unittest.main()
