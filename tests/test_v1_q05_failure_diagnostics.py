"""Supplemental redaction contracts, never Core acceptance."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
spec=importlib.util.spec_from_file_location('windows_builder',Path(__file__).resolve().parents[1]/'scripts/build_windows_bundle.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)

class FailureDiagnosticContracts(unittest.TestCase):
    def test_only_reviewed_sites_no_paths_or_text(self):
        for good in ('managed_lifecycle_probe.py:12','attached_core.py:140>core.py:30','UNCLASSIFIED_REVIEWED_SITE'):
            self.assertTrue(builder.safe_failure_site(good))
        for bad in ('/Users/private/password:12','managed_lifecycle_probe.py:0','unreviewed.py:12','vault.py:10001',None,{},'secret'):
            self.assertFalse(builder.safe_failure_site(bad))

    def test_failing_process_never_becomes_success_and_bad_diagnostic_not_printed(self):
        with tempfile.TemporaryDirectory() as t:
            folder=Path(t)
            value={'schema':'wam-redacted-acceptance-failure/v1','platform':'windows-x64',
                'kind':'AssertionError','site':'/private/secret:12','mainnet_allowed':False}
            (folder/'q05-failure-test.json').write_text(json.dumps(value))
            stream=io.StringIO()
            with contextlib.redirect_stdout(stream),self.assertRaises(AssertionError):
                builder.require_frozen_success(subprocess.CompletedProcess([],2),folder,'EXPECTED_DENIAL')
            self.assertEqual(stream.getvalue(),'')
            value['site']='managed_lifecycle_probe.py:12'
            (folder/'q05-failure-test.json').write_text(json.dumps(value))
            with contextlib.redirect_stdout(stream),self.assertRaises(AssertionError):
                builder.require_frozen_success(subprocess.CompletedProcess([],2),folder,'EXPECTED_DENIAL')
            self.assertIn('managed_lifecycle_probe.py:12',stream.getvalue())

if __name__=='__main__':unittest.main()
