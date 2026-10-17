"""Negative input/consent contracts for independent process public scan probe."""
from pathlib import Path
import subprocess
import sys
import unittest

from wam_regtest.managed_scan_probe import (
    run,main,IndependentScanProbeError,
)


class PublicIndependentScannerScope(unittest.TestCase):
    def test_never_bootstraps_or_attaches_without_explicit_consent(self):
        root=Path.cwd()/"wam-fusion-core-0123456789abcdef"
        source=Path.cwd()/"wsp-upstream"
        with self.assertRaisesRegex(IndependentScanProbeError,
                "Q05_PUBLIC_SCAN_CONSENT_REQUIRED"):
            run(root,source,max_blocks=3)
        self.assertEqual(main(["--root",str(root),"--wsp-source",
                               str(source),"--max-blocks","3"]),2)

    def test_wrong_scanner_scope_rejected_before_wsp_import_or_sqlite(self):
        root=Path.cwd()/"wam-fusion-core-0123456789abcdef"
        source=Path.cwd()/"wsp-upstream"
        for arg in (
            {"max_blocks":0},{"max_blocks":101},
            {"max_blocks":3,"expected_before":-1},
            {"max_blocks":3,"expected_before":True},
        ):
            with self.subTest(arg=arg):
                with self.assertRaisesRegex(IndependentScanProbeError,
                        "Q05_PUBLIC_SCAN_SCOPE_DENIED"):
                    run(root,source,authorized=True,**arg)

    def test_no_user_wallet_or_implicit_rpc_process_mutation(self):
        import inspect
        from wam_regtest import managed_scan_probe
        src=inspect.getsource(managed_scan_probe.run)
        self.assertNotIn("WalletSession.create",src)
        self.assertNotIn("CoreSupervisor(",src)
        self.assertNotIn("sendrawtransaction",src)
        self.assertNotIn("generatetoaddress",src)
        self.assertNotIn("Signer(",src)


if __name__=="__main__":
    unittest.main()
