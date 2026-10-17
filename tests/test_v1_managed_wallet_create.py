"""Create-once managed WSP onboarding contracts (not fake Core E2E)."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock,patch
import unittest

from wam_regtest.managed_wallet_create import (
    ManagedWalletCreateError,create_managed_wallet,
)
from wam_regtest.wsp_live import REGTEST_GENESIS


class ManagedCreateContracts(unittest.TestCase):
    def setUp(self):
        self.t=TemporaryDirectory(prefix="wam-regtest-new-wallet-")
        self.addCleanup(self.t.cleanup)
        base=Path(self.t.name).resolve()
        self.root=base/"wam-fusion-core-0123456789abcdef"
        self.root.mkdir()
        (self.root/"chain").mkdir()
        self.core=base/"pinned-core"
        self.source=base/"wsp"
        self.password=b"regtest-only-disposable-create"

    def call(self,**kwargs):
        return create_managed_wallet(self.root,self.core,self.source,
                                     self.password,**kwargs)

    def test_creation_requires_explicit_consent_and_private_inputs(self):
        with self.assertRaisesRegex(ManagedWalletCreateError,
                                    "CREATE_CONSENT_REQUIRED"):
            self.call()
        with self.assertRaisesRegex(ManagedWalletCreateError,
                                    "CREATE_INPUT_DENIED"):
            create_managed_wallet(self.root,Path("not-absolute"),self.source,
                                  self.password,authorized=True)
        with self.assertRaisesRegex(ManagedWalletCreateError,
                                    "CREATE_INPUT_DENIED"):
            create_managed_wallet(self.root,self.core,self.source,b"short",
                                  authorized=True)
        self.assertFalse((self.root/"chain"/"wallet-vault").exists())

    def test_existing_vault_prevents_seed_generation_or_network_adoption(self):
        folder=self.root/"chain"/"wallet-vault"
        folder.mkdir()
        sentinel=folder/"snapshot-000000001.enc"
        sentinel.write_bytes(b"UNTRUSTED_RETAIN_UNMODIFIED")
        receipt={"wamd_sha256":"a"*64,"wam_cli_sha256":"b"*64,
                 "platform":"macos-arm64"}
        profile={"network":"regtest","genesis":REGTEST_GENESIS,
                 "core_sha256":receipt["wamd_sha256"],
                 "cli_sha256":receipt["wam_cli_sha256"]}
        status={"state":"ready","core_process_owned":True,"height":101}
        with (patch("wam_regtest.wsp_live._pinned_source"),
              patch("wam_regtest.supervisor_client.control",return_value=status),
              patch("wam_regtest.core_supervisor._profile_read",
                    return_value=profile),
              patch("wam_regtest.core.verified_core_paths",
                    return_value=(None,None,receipt)),
              patch("wam_regtest.custody.storage",return_value=Mock()),
              patch("wam_regtest.custody.platform_name",
                    return_value="macos-arm64"),
              patch("wam_regtest.managed_scan_client.ManagedScanRpc") as rpc,
              patch("wam_sp.keystore.Keyring") as keyring):
            with self.assertRaisesRegex(ManagedWalletCreateError,
                                        "ALREADY_OR_UNCERTAIN"):
                self.call(authorized=True)
            rpc.assert_not_called()
            keyring.assert_not_called()
        self.assertEqual(sentinel.read_bytes(),b"UNTRUSTED_RETAIN_UNMODIFIED")

    def test_pre_existing_runtime_is_never_removed(self):
        runtime=self.root/"chain"/"wallet-runtime.sqlite"
        runtime.write_bytes(b"UNOWNED_RUNTIME")
        receipt={"wamd_sha256":"a"*64,"wam_cli_sha256":"b"*64,
                 "platform":"macos-arm64"}
        profile={"network":"regtest","genesis":REGTEST_GENESIS,
                 "core_sha256":receipt["wamd_sha256"],
                 "cli_sha256":receipt["wam_cli_sha256"]}
        status={"state":"ready","core_process_owned":True,"height":101}
        with (patch("wam_regtest.wsp_live._pinned_source"),
              patch("wam_regtest.supervisor_client.control",return_value=status),
              patch("wam_regtest.core_supervisor._profile_read",
                    return_value=profile),
              patch("wam_regtest.core.verified_core_paths",
                    return_value=(None,None,receipt)),
              patch("wam_regtest.custody.storage",return_value=Mock()),
              patch("wam_regtest.custody.platform_name",
                    return_value="macos-arm64"),
              patch("wam_regtest.managed_scan_client.ManagedScanRpc") as rpc):
            with self.assertRaisesRegex(ManagedWalletCreateError,
                                        "RUNTIME_EXISTS_DENIED"):
                self.call(authorized=True)
            rpc.assert_not_called()
        self.assertEqual(runtime.read_bytes(),b"UNOWNED_RUNTIME")


if __name__=="__main__":
    unittest.main()
