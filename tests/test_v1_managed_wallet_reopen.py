"""T05/Q05 encrypted original-wallet reopen contracts; no mock-Core PASS claim."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from wam_regtest.managed_wallet_reopen import (
    SCHEMA,CONTEXT,FILENAME,ManagedWalletReopenError,make,publish,read,
)
from wam_regtest.wallet_session import WalletSession,WalletSessionError


class OriginalWalletIdentityContracts(unittest.TestCase):
    def setUp(self):
        self.password=b"test-only-regtest-password"
        self.receipt={"wamd_sha256":"a"*64,"wam_cli_sha256":"b"*64}
        self.wallet_id="c"*32
        self.profile=make(self.wallet_id,self.receipt)

    def test_locator_binds_original_wallet_and_exact_pinned_core(self):
        self.assertEqual(self.profile["schema"],SCHEMA)
        self.assertEqual(self.profile["wallet_id"],self.wallet_id)
        self.assertFalse(self.profile["mainnet_allowed"])
        self.assertEqual(self.profile["network"],"regtest")
        self.assertNotEqual(self.profile,make(self.wallet_id,{
            **self.receipt,"wamd_sha256":"d"*64}))
        self.assertNotEqual(self.profile,make("e"*32,self.receipt))

    def test_profile_rejects_wrong_chain_fields_platform_and_invalid_ids(self):
        from wam_regtest.managed_wallet_reopen import _validate
        for changed in ({"mainnet_allowed":True},{"network":"main"},
                        {"genesis":"f"*64},{"wallet_id":"../wallet"},
                        {"wallet_id":True},{"core_sha256":"bad"},
                        {"cli_sha256":None},{"extra":"forbidden"},
                        {"schema":"unknown"}):
            with self.subTest(changed=changed),self.assertRaises(ManagedWalletReopenError):
                _validate({**self.profile,**changed})

    def test_storage_seals_create_only_with_pinned_recovery_purpose(self):
        from wam_sp.keystore import unseal
        class PrivateStore:
            def __init__(self):
                self.data={}
            def validate_directory(self,path):
                if path!=Path("/private-wallet-vault"):
                    raise ValueError("unsafe")
            def publish(self,path,name,data):
                if (path,name) in self.data:
                    raise ValueError("create-only")
                self.data[path,name]=data
            def read(self,path,name):
                return self.data[path,name]
        store=PrivateStore();directory=Path("/private-wallet-vault")
        with patch("wam_regtest.custody.storage",return_value=store):
            self.assertEqual(publish(directory,self.profile,self.password),self.profile)
            self.assertEqual(read(directory,self.password),self.profile)
            payload=store.data[directory,FILENAME]
            self.assertTrue(payload.startswith(b"WAMSP02\0"))
            self.assertNotIn(self.wallet_id.encode(),payload)
            with self.assertRaises(ManagedWalletReopenError):
                publish(directory,self.profile,self.password)
            with self.assertRaises(ManagedWalletReopenError):
                read(directory,b"incorrect-passphrase-xxxx")
            # Correct ciphertext cannot be opened under a DIFFERENT approved purpose.
            with self.assertRaises(Exception):
                unseal(payload,self.password,b"keys")

    def test_duplicate_json_fields_rejected_even_inside_valid_envelope(self):
        from wam_sp.keystore import seal
        from wam_regtest.managed_wallet_reopen import _pairs
        with self.assertRaises(ManagedWalletReopenError):
            json.loads('{"wallet_id":"a","wallet_id":"b"}',object_pairs_hook=_pairs)
        forged=('{"schema":"'+SCHEMA+'","schema":"'+SCHEMA+'"}').encode()
        class Store:
            def validate_directory(self,_):pass
            def read(self,_,name):
                self.name=name
                return seal(forged,b"test-only-regtest-password",CONTEXT)
        with patch("wam_regtest.custody.storage",return_value=Store()):
            with self.assertRaisesRegex(ManagedWalletReopenError,
                    "MANAGED_WALLET_DUPLICATE_FIELD_DENIED"):
                read(Path("/verified-private"),self.password)

    def test_reopen_requires_explicit_consent_and_native_owned_read_first(self):
        with self.assertRaisesRegex(WalletSessionError,
                "MANAGED_WALLET_REOPEN_CONSENT_REQUIRED"):
            WalletSession.reopen_managed(Path("/no-core"),Path("/no-chain"),
                Path("/no-wsp"),self.password,"unused",authorized=False)
        # Without actual ManagedReadRpc tied to an owned process, reject
        # before reading locator or creating SQLite, even if consented.
        with self.assertRaisesRegex(WalletSessionError,"WALLET_OWNED_HTTP_REQUIRED"):
            WalletSession.reopen_managed(Path("/no-core"),Path("/no-chain"),
                Path("/no-wsp"),self.password,"unused",authorized=True,
                read_rpc=object())

    def test_original_checkpoint_preflight_is_readonly_locked_no_balance(self):
        from contextlib import nullcontext
        from wam_regtest.managed_wallet_reopen import preflight_existing_checkpoint
        class Anchor:
            wallet_id="c"*32
            def lease(self):return nullcontext()
            def read(self):return (3,"f"*64)
        anchor=Anchor()
        class Vault:
            def __init__(self,folder,owned,source):
                self._expected=owned.read()
            def _load_payload(self,password,record):
                return {"wallet_id":anchor.wallet_id,"generation":record[0]}
        class Storage:
            def validate_directory(self,path):pass
        core=Path("/verified-core");datadir=Path("/private-chain")
        source=Path("/pinned-wsp")
        with (patch("wam_regtest.core.verified_core_paths",return_value=(
                    Path("/verified-core/wamd"),Path("/verified-core/wam-cli"),
                    {**self.receipt,"platform":"macos-arm64"})),
              patch("wam_regtest.wsp_live._pinned_source"),
              patch("wam_regtest.custody.platform_name",return_value="macos-arm64"),
              patch("wam_regtest.custody.storage",return_value=Storage()),
              patch("wam_regtest.custody.anchor",return_value=anchor),
              patch("wam_regtest.vault.CheckpointVault",Vault),
              patch("wam_regtest.managed_wallet_reopen.read",return_value=self.profile)):
            proof=preflight_existing_checkpoint(core,datadir,source,
                                                self.password,authorized=True)
            self.assertEqual(proof["status"],
                             "MANAGED_WALLET_ORIGINAL_CHECKPOINT_VERIFIED_LOCKED")
            self.assertFalse(proof["signer_allowed"])
            self.assertFalse(proof["broadcast_allowed"])
            self.assertFalse(proof["balance_verified"])
            self.assertTrue(proof["wallet_locked"])
            self.assertTrue(proof["original_native_anchor_verified"])
            with self.assertRaisesRegex(ManagedWalletReopenError,
                    "MANAGED_WALLET_PREFLIGHT_CONSENT_REQUIRED"):
                preflight_existing_checkpoint(core,datadir,source,self.password)
            with patch("wam_regtest.managed_wallet_reopen.read",
                       return_value={**self.profile,"wallet_id":"a"*32}):
                # A valid but DIFFERENT locator must not match the anchored
                # original wallet's ciphertext payload.
                with self.assertRaisesRegex(ManagedWalletReopenError,
                        "MANAGED_WALLET_CHECKPOINT_MISMATCH"):
                    preflight_existing_checkpoint(core,datadir,source,
                                                 self.password,authorized=True)
            with patch("wam_regtest.managed_wallet_reopen.read",
                       return_value={**self.profile,"core_sha256":"d"*64}):
                with self.assertRaisesRegex(ManagedWalletReopenError,
                        "MANAGED_WALLET_CORE_CHANGED_DENIED"):
                    preflight_existing_checkpoint(core,datadir,source,
                                                 self.password,authorized=True)

    def test_preflight_cannot_read_without_real_signed_core(self):
        from wam_regtest.managed_wallet_reopen import preflight_existing_checkpoint
        with patch("wam_regtest.core.verified_core_paths",
                   side_effect=ValueError("PRIVATE_CORE_PATH_CANARY")):
            with self.assertRaisesRegex(ManagedWalletReopenError,
                    "^MANAGED_WALLET_PREFLIGHT_DENIED$") as error:
                preflight_existing_checkpoint(Path("/unknown"),
                    Path("/unknown-chain"),Path("/unknown-source"),
                    self.password,authorized=True)
            self.assertNotIn("CANARY",str(error.exception))

    def test_disposable_wallet_never_publishes_reopen_locator_implicitly(self):
        import inspect
        source=inspect.getsource(WalletSession.create)
        self.assertNotIn("enable_managed_reopen(",source)
        self.assertNotIn("publish(",source)


if __name__=="__main__":
    unittest.main()
