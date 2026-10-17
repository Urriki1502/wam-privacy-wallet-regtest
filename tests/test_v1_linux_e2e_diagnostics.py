"""Safe diagnostics for explicitly opted-in Linux acceptance only.

These are supplemental negative tests: no Core process, root service, or keys.
"""
import contextlib
import io
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from wam_regtest.linux_headless import run


class LinuxFrozenAcceptanceDiagnostics(TestCase):
    def arguments(self, *, acceptance):
        return SimpleNamespace(
            core_dir=Path('/public-disposable-core'),
            wsp_source_root=Path('/public-wsp-fixture'),
            manifest_sha256='0'*64,
            anchor_socket=Path('/public-fixture/anchor.sock'),
            confirm_experimental_developer_regtest=True,
            confirm_headless_e2e=acceptance,
            confirm_qt_e2e=False,
            gui=False,
            recover_backup=None,
            report=None,
        )

    def test_opted_in_exception_never_emits_raw_private_text(self):
        out=io.StringIO()
        with patch('wam_regtest.linux_runtime.configure',
                   side_effect=RuntimeError('SECRET_MNEMONIC private /owner/path')):
            with contextlib.redirect_stderr(out):
                self.assertEqual(run(self.arguments(acceptance=True)),2)
        text=out.getvalue()
        self.assertIn('LINUX_E2E_FAILURE_KIND=RuntimeError',text)
        self.assertIn('LINUX_E2E_FAILURE_SITE=linux_headless.py:',text)
        self.assertIn('LINUX_HEADLESS_REGTEST_DENIED',text)
        self.assertNotIn('SECRET_MNEMONIC',text)
        self.assertNotIn('/owner/path',text)

    def test_normal_mode_does_not_emit_acceptance_diagnostics(self):
        out=io.StringIO()
        with patch('wam_regtest.linux_runtime.configure',
                   side_effect=RuntimeError('SECRET')):
            with contextlib.redirect_stderr(out):
                self.assertEqual(run(self.arguments(acceptance=False)),2)
        self.assertEqual(out.getvalue().strip(),'LINUX_HEADLESS_REGTEST_DENIED')
