"""Public operator CLI tests; never run WAM Core or load wallet secrets."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest

from wam_regtest.persistent_cli import main
from wam_regtest.persistent_profile import create_disposable_profile

A='a'*64
B='b'*64
C='c'*64


@unittest.skipUnless(os.name=='posix','Windows persistent profile is explicitly unqualified')
class OperatorProfileCLIContracts(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='wam-t05-cli-')
        self.addCleanup(temp.cleanup)
        parent=Path(temp.name).resolve(strict=True)/'wam-fusion-regtest-profiles'
        parent.mkdir(mode=0o700)
        self.root,_=create_disposable_profile(parent,authorized=True,
            expected_genesis=A,expected_node_sha256=B,expected_cli_sha256=C)

    def arguments(self,*,genesis=A,lease=False):
        args=['--profile-root',str(self.root),'--genesis-sha256',genesis,
              '--node-sha256',B,'--cli-sha256',C,'--acknowledge-regtest-only']
        if lease:args.append('--require-single-writer')
        return args

    def test_readonly_operator_receipt_cannot_grant_core_execution(self):
        output=io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(self.arguments()),0)
        payload=json.loads(output.getvalue())
        self.assertEqual(payload['status'],'PUBLIC_PROFILE_PREFLIGHT_PASS')
        self.assertFalse(payload['persistent_core_e2e_pass'])
        self.assertFalse(payload['runtime_authorized'])
        self.assertFalse(payload['mainnet_allowed'])
        self.assertFalse(payload['cooperative_lease_observed'])
        self.assertNotIn(str(self.root),output.getvalue())
        self.assertFalse((self.root/'session.lock').exists())

    def test_optional_lease_proof_is_cooperative_only(self):
        output=io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(self.arguments(lease=True)),0)
        receipt=json.loads(output.getvalue())
        self.assertTrue(receipt['cooperative_lease_observed'])
        self.assertFalse(receipt['runtime_authorized'])

    def test_wrong_pin_is_denied_without_private_path_output(self):
        output=io.StringIO()
        with contextlib.redirect_stderr(output):
            self.assertEqual(main(self.arguments(genesis='f'*64)),2)
        self.assertEqual(output.getvalue().strip(),'PROFILE_TRUST_PINS_MISMATCH')
        self.assertNotIn(str(self.root),output.getvalue())

    def test_explicit_consent_is_mandatory(self):
        args=self.arguments()
        args.remove('--acknowledge-regtest-only')
        with contextlib.redirect_stderr(io.StringIO()) as result:
            self.assertEqual(main(args),2)
        self.assertFalse((self.root/'session.lock').exists())
