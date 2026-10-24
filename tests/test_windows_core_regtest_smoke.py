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
    def test_rpc_launch_keeps_gui_console_free_and_local_custody_contract(self):
        # Static launch boundary, NOT proof of physical Windows absence of flashes.
        import ast, inspect
        from wam_regtest.cli_rpc import execute
        from wam_regtest.rpc_scope import route
        tree=ast.parse(inspect.getsource(execute))
        calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call)
               and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name)
               and n.func.value.id=='subprocess' and n.func.attr=='Popen']
        self.assertEqual(len(calls),1)
        fields={k.arg:ast.unparse(k.value) for k in calls[0].keywords}
        self.assertEqual(fields['creationflags'],'creationflags')
        self.assertEqual(fields['stdin'],'subprocess.DEVNULL')
        self.assertEqual(fields['stdout'],'subprocess.PIPE')
        self.assertEqual(fields['stderr'],'subprocess.PIPE') # drained/bounded/redacted, never printed
        self.assertEqual(fields['cwd'],'directory');self.assertEqual(fields['env'],'env')
        self.assertNotIn('shell',fields)
        # Preserve the original Windows no-console launch requirement at the
        # actual shared CLI caller, rather than an obsolete wrapper location.
        caller=ast.parse(inspect.getsource(route))
        flags=[n.value for n in ast.walk(caller) if isinstance(n,ast.keyword) and n.arg=='creationflags']
        self.assertEqual(len(flags),1)
        self.assertEqual(ast.literal_eval(flags[0].body),0x08000000)
        self.assertEqual(ast.unparse(flags[0].test),"sys.platform == 'win32'")

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
