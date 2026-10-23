"""Q05 managed original-wallet snapshot safety contracts.

These are negative/contract fixtures, NOT live Core/frozen acceptance. The
real-Core scanner IPC E2E remains a separate explicit qualification gate.
"""
from contextlib import ExitStack,nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
import tempfile
import unittest

from wam_regtest.managed_wallet_reopen import make
from wam_regtest.managed_wallet_snapshot import (
    ManagedWalletSnapshotError,read_managed_wallet_snapshot,
)
from wam_regtest.wallet_read import WalletReadSnapshot


class ManagedOriginalWalletSnapshotContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="wam-q05-read-")
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()/"wam-fusion-core-0123456789abcdef"
        self.root.mkdir()
        (self.root/"chain").mkdir()
        (self.root/"chain"/"wallet-vault").mkdir()
        self.core=Path(self.temp.name).resolve()/"original-signed-core"
        self.source=Path(self.temp.name).resolve()/"pinned-wsp"
        self.password=b"disposable-regtest-only-password"
        self.receipt={"wamd_sha256":"a"*64,"wam_cli_sha256":"b"*64}
        self.profile=make("c"*32,self.receipt)
        self.status={"state":"ready","height":101,
                     "core_process_owned":True,"chain":"regtest",
                     "mainnet_allowed":False}
        self.record=(4,"f"*64)
        self.anchor=SimpleNamespace(wallet_id="c"*32,
                                     read=Mock(return_value=self.record),
                                     lease=lambda: nullcontext())
        self.account=Mock()
        self.account.payment_code.return_value="wamrtsp1public-fixture"
        self.accounts=(self.account,)
        self.ring=Mock()
        self.ring.accounts.return_value=self.accounts
        self.scanner=Mock()
        # unittest.mock reserves assert_* names; the real WSP scanner has
        # an explicit assert_current() method, not a mock assertion helper.
        self.scanner.assert_current=Mock()
        self.scanner.accounts=self.accounts
        self.scanner.store.tip.return_value=(101,"d"*64)
        self.scanner.sync.return_value=SimpleNamespace(blocks=0,rollback=0)
        self.scanner.coins.return_value=[{"txid":"f"*64}]
        self.rpc=Mock()
        self.rpc.attest.return_value={"chain":"regtest","blocks":101}
        def chain(method,params=None):
            return {"getblockcount":101,"getbestblockhash":"d"*64,
                    "getblockhash":"d"*64}[method]
        self.rpc.call.side_effect=chain
        self.vault=Mock()
        self.vault._expected=self.record
        self.vault.restore.return_value=(self.ring,self.scanner)
        self.wallet=Mock()
        self.wallet.balance.return_value={"confirmed_atoms":27000}
        self.wallet.history.return_value=[{
            "txid":"e"*64,"height":99,"confirmations":3,
            "credit":27000,"debit":0,
        }]
        self.runtime_lease=Mock()

    def fixture(self,*,statuses=None,verified=None):
        stack=ExitStack()
        result={"status":"MANAGED_WALLET_ORIGINAL_CHECKPOINT_VERIFIED_LOCKED",
                "supervisor_authenticated":True,
                "supervisor_core_identity_verified":True,
                "wallet_locked":True,
                "signer_allowed":False,"broadcast_allowed":False}
        if verified is not None:result=verified
        preflight=stack.enter_context(patch(
            "wam_regtest.managed_wallet_snapshot.verify_locked_wallet",
            return_value=result))
        control=stack.enter_context(patch("wam_regtest.supervisor_client.control",
            side_effect=statuses or [self.status,self.status]))
        stack.enter_context(patch("wam_regtest.core.verified_core_paths",
            return_value=(self.core/"wamd",self.core/"wam-cli",self.receipt)))
        # This pre-existing test intentionally injects Mock() ScanAccounts,
        # not genuine WSP secret/public pairs. The NEW K-06 native signer
        # contract is exercised independently with actual pinned WSP Keyring
        # and BIP39 keyrings in test_v1_k06_account_isolation.py and real E2E.
        native=stack.enter_context(patch(
            "wam_regtest.account_isolation.require_native_wsp_accounts",
            return_value=Mock()))
        store=Mock()
        stack.enter_context(patch("wam_regtest.custody.storage",return_value=store))
        stack.enter_context(patch("wam_regtest.custody.anchor",return_value=self.anchor))
        # This source-only fixture has no real keyring/anchor/owner envelope.
        # Native process contention is separately tested without these mocks
        # and by the genuine Q05 multi-process Core/GUI/frozen probe.
        stack.enter_context(patch('wam_regtest.runtime_recovery.RuntimeLease',return_value=self.runtime_lease))
        stack.enter_context(patch('wam_regtest.runtime_recovery.enroll'))
        stack.enter_context(patch("wam_regtest.managed_wallet_snapshot.read_locator",
                                  return_value=self.profile))
        vaultclass=stack.enter_context(patch("wam_regtest.vault.CheckpointVault",
                                            return_value=self.vault))
        rpcclass=stack.enter_context(patch(
            "wam_regtest.managed_scan_client.ManagedScanRpc",return_value=self.rpc))
        walletclass=stack.enter_context(patch("wam_sp.wallet.Wallet",return_value=self.wallet))
        return stack,preflight,control,vaultclass,rpcclass,walletclass

    def call(self,**kwargs):
        return read_managed_wallet_snapshot(
            self.root,self.core,self.source,self.password,
            authorized_readonly=True,**kwargs)

    def test_exact_original_wallet_snapshot_disables_signing_and_demo_identity(self):
        stack,preflight,control,vaultclass,rpcclass,walletclass=self.fixture()
        with stack:
            result=self.call()
            self.assertIs(type(result),WalletReadSnapshot)
            self.assertEqual(result.height,101)
            self.assertEqual(result.tip,"d"*64)
            self.assertEqual(result.receive_code,"wamrtsp1public-fixture")
            self.assertEqual(result.confirmed_atoms,27000)
            self.assertEqual(len(result.history),1)
            self.assertEqual(result.confirmed_utxos,1)
            self.assertFalse(result.synthetic_rpc)
            self.assertFalse(result.demo_account_only)
            self.assertFalse(result.signer_allowed)
            self.assertFalse(result.broadcast_allowed)
            self.assertFalse(result.mainnet_allowed)
            self.vault.restore.assert_called_once_with(
                self.root/"chain"/"wallet-runtime.sqlite",self.password,native_private_runtime=True)
            self.runtime_lease.close.assert_called_once()
            self.vault.save.assert_not_called()
            self.rpc.close.assert_called_once()
            self.ring.close.assert_called_once()
            self.scanner.close.assert_called_once()
            preflight.assert_called_once()
            walletclass.assert_called_once_with(self.scanner)
            self.assertEqual(control.call_count,2)
            self.assertTrue(rpcclass.call_args.kwargs["authorized_readonly"])

    def test_optional_local_checkpoint_save_is_separate_explicit_consent(self):
        self.scanner.sync.return_value=SimpleNamespace(blocks=3,rollback=0)
        stack,*_=self.fixture()
        with stack:
            self.call()
            self.vault.save.assert_not_called()
        self.vault.save.reset_mock()
        stack,*_=self.fixture()
        with stack:
            self.call(authorized_persist_checkpoint=True)
            self.vault.save.assert_called_once_with(
                self.ring,self.scanner,self.password)

    def test_missing_consent_invalid_types_do_not_touch_custody_or_network(self):
        with self.assertRaisesRegex(ManagedWalletSnapshotError,"READ_CONSENT_REQUIRED"):
            read_managed_wallet_snapshot(self.root,self.core,self.source,self.password)
        with self.assertRaisesRegex(ManagedWalletSnapshotError,"PERSIST_CONSENT_DENIED"):
            self.call(authorized_persist_checkpoint=1)
        with self.assertRaisesRegex(ManagedWalletSnapshotError,"READ_INPUT_DENIED"):
            read_managed_wallet_snapshot(self.root,Path("relative"),self.source,
                                         self.password,authorized_readonly=True)

    def test_supervisor_status_drift_denies_snapshot_after_real_scan(self):
        changed={**self.status,"height":102}
        stack,*_=self.fixture(statuses=[self.status,changed])
        with stack,self.assertRaisesRegex(ManagedWalletSnapshotError,
                                          "CHAIN_OR_OWNER_CHANGED"):
            self.call()
        self.scanner.close.assert_called_once()
        self.ring.close.assert_called_once()
        self.rpc.close.assert_called_once()
        self.vault.save.assert_not_called()

    def test_untrusted_preflight_denies_before_scanner_or_decryption(self):
        bad={"status":"fake","supervisor_authenticated":True,
             "supervisor_core_identity_verified":True,
             "wallet_locked":True,"signer_allowed":False,"broadcast_allowed":False}
        stack,_,_,vaultclass,rpcclass,_=self.fixture(verified=bad)
        with stack,self.assertRaisesRegex(ManagedWalletSnapshotError,
                                          "PREFLIGHT_UNVERIFIED"):
            self.call()
        vaultclass.assert_not_called()
        rpcclass.assert_not_called()

    def test_wrong_core_digest_denied_before_native_anchor_restore(self):
        stack,*_=self.fixture()
        with stack,patch("wam_regtest.managed_wallet_snapshot.read_locator",
                         return_value={**self.profile,"core_sha256":"e"*64}):
            with self.assertRaisesRegex(ManagedWalletSnapshotError,
                                        "PROFILE_MISMATCH"):
                self.call()
        self.vault.restore.assert_not_called()

    def test_swapped_wallet_locator_without_its_native_anchor_fails_closed(self):
        # A wallet_id identifies a SEPARATE native anchor. There is no
        # assumption that make(wallet_id, receipt) proves that wallet exists.
        # Native anti-rollback existence is an independent mandatory gate.
        original="c"*32
        def anchor_for(wallet_id,keychain):
            if wallet_id!=original:
                raise ValueError("NATIVE_UNKNOWN_ANCHOR_FIXTURE")
            return self.anchor
        stack,*_=self.fixture()
        with stack,patch("wam_regtest.managed_wallet_snapshot.read_locator",
                         return_value={**self.profile,"wallet_id":"e"*32}),patch(
                         "wam_regtest.custody.anchor",side_effect=anchor_for):
            with self.assertRaisesRegex(ManagedWalletSnapshotError,
                                        "^MANAGED_WALLET_SNAPSHOT_UNVERIFIED$"):
                self.call()
        self.vault.restore.assert_not_called()

    def test_existing_unexplained_plaintext_runtime_is_never_removed(self):
        runtime=self.root/"chain"/"wallet-runtime.sqlite"
        runtime.write_bytes(b"UNOWNED_PLAINTEXT_SENTINEL")
        self.vault.restore.side_effect=ValueError("VAULT_FRESH_RUNTIME_REQUIRED")
        stack,*_=self.fixture()
        with stack,self.assertRaisesRegex(ManagedWalletSnapshotError,
                                          "^MANAGED_WALLET_SNAPSHOT_UNVERIFIED$"):
            self.call()
        self.assertEqual(runtime.read_bytes(),b"UNOWNED_PLAINTEXT_SENTINEL")
        self.vault.save.assert_not_called()

    def test_error_redaction_prevents_private_credential_echo(self):
        self.rpc.attest.side_effect=RuntimeError("PRIVATE_PASSWORD_CANARY")
        stack,*_=self.fixture()
        with stack,self.assertRaisesRegex(ManagedWalletSnapshotError,
                                          "^MANAGED_WALLET_SNAPSHOT_UNVERIFIED$") as err:
            self.call()
        self.assertNotIn("CANARY",str(err.exception))


if __name__=="__main__":
    unittest.main()
