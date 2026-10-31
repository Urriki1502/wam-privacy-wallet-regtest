"""Q06 source-only onboarding/owner regression (not physical macOS UI E2E).

No fake Core success is reported as source-native or owned-Core acceptance.
"""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from mnemonic import Mnemonic
from wam_regtest.bip39_owner_backend import Bip39ReadOnlyBackend,Q06ReadOnlyError
from wam_regtest.bip39_12 import Bip39Regtest12Keys

SOURCE=Path(importlib.util.find_spec("wam_sp").origin).resolve().parents[2]
PASSWORD=b"Q06 standalone trial password"
PHRASE=Mnemonic("english").to_mnemonic(bytes(16))


class Q06OwnerBackendContracts(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp=tempfile.TemporaryDirectory(prefix="q06-owner-unit-")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.owner=SimpleNamespace(directory=self.root,root=self.root)
        self.backend=Bip39ReadOnlyBackend(self.root,Path("/synthetic-core"),SOURCE)
        self.backend._core=lambda:self.owner

    def test_disposable_native_anchor_created_only_after_core_supervisor(self):
        # Regression for the macOS frozen failure: the old Q06 runner
        # precreated a .keychain-db under a fresh CoreSupervisor root, whose
        # empty-namespace protection correctly rejected the new profile.
        order=[]
        anchor=self.root/"q06-disposable.keychain-db"
        def init_owner():
            order.append("core_supervisor")
            return self.owner
        def create_anchor(root):
            self.assertEqual(root,self.root)
            order.append("native_keychain")
            return anchor
        self.backend=Bip39ReadOnlyBackend(
            self.root,Path("/synthetic-core"),SOURCE,
            _anchor_factory=create_anchor)
        self.backend._core=init_owner
        def create_seed(owner,source,password,phrase,*,authorized,keychain):
            self.assertTrue(authorized)
            self.assertEqual(keychain,anchor)
            order.append("sealed_seed")
            return (self.root/("bip39-12-"+("a"*32)),
                    {"profile":"q06","account_id":"test-account",
                     "receive_code":"wamrtsp1public"})
        with patch("wam_regtest.bip39_seed_vault.create_owned_seed_container",
                   side_effect=create_seed):
            result=self.backend.execute("open",(PASSWORD,"restore",PHRASE),{})
        self.assertEqual(order,["core_supervisor","native_keychain","sealed_seed"])
        self.assertEqual(result["status"],"Q06_REGTEST_READ_ONLY_OWNER_OPENED")
        self.assertTrue(self.backend._anchor_ready)
        self.backend.execute("lock",(),{})

    def test_gui_create_receipt_shows_exact_twelve_words_only_once(self):
        with (patch("wam_regtest.bip39_12.generate_phrase",return_value=PHRASE),
              patch("wam_regtest.bip39_seed_vault.create_owned_seed_container",
                    return_value=(self.root/("bip39-12-"+("0"*32)),{"profile":"q06",
                        "account_id":"public-identity","receive_code":"wamrtsp1public"}))):
            result=self.backend.execute("open",(PASSWORD,"create",""),{})
        self.assertEqual(result["mnemonic_once"],PHRASE)
        self.assertEqual(len(result["mnemonic_once"].split()),12)
        self.assertEqual(result["receive_code"],"wamrtsp1public")
        self.assertFalse(result["signer_allowed"])
        self.assertFalse(result["broadcast_allowed"])
        self.assertFalse(result["mainnet_allowed"])
        self.assertFalse(self.backend.public_state()["locked"])
        with self.assertRaises(Q06ReadOnlyError):
            self.backend.execute("sign",(),{})
        with self.assertRaises(Q06ReadOnlyError):
            self.backend.execute("broadcast",(),{})
        self.backend.execute("lock",(),{})
        self.assertTrue(self.backend.public_state()["locked"])
        self.assertIsNone(self.backend._secret)

    def test_import_existing_mnemonic_requires_explicit_new_profile(self):
        with patch("wam_regtest.bip39_seed_vault.create_owned_seed_container",
                   return_value=(self.root/("bip39-12-"+("f"*32)),{
                       "profile":"q06","account_id":"new-profile-account",
                       "receive_code":"wamrtsp1newprofile"})) as create:
            result=self.backend.execute("open",(PASSWORD,"restore",PHRASE),{})
        create.assert_called_once()
        self.assertEqual(create.call_args.args[3],PHRASE)
        self.assertEqual(result["mnemonic_once"],"")
        self.assertTrue(result["receive_code"].startswith("wamrtsp1"))
        self.backend.execute("lock",(),{})

    def test_existing_bip39_open_does_not_import_or_rewrite_seed(self):
        folder=self.root/("bip39-12-"+("a"*32))
        folder.mkdir()
        # Actual pinned WSP key derivation; native seed file read is test-patched.
        with patch("wam_regtest.bip39_seed_vault.open_owned_seed_container",
                   side_effect=lambda *a,**kw:Bip39Regtest12Keys(
                       PHRASE,source=SOURCE,authorized_disposable=True)):
            result=self.backend.execute("open",(PASSWORD,"reopen",""),{})
        self.assertEqual(result["mnemonic_once"],"")
        self.assertEqual(result["receive_code"],self.backend._public["receive_code"])
        self.assertEqual(self.backend._seed_folder,folder)
        self.backend.execute("lock",(),{})

    def test_guard_refuses_q05_profile_ambiguous_seeds_and_wrong_modes(self):
        with self.assertRaises(Q06ReadOnlyError):
            self.backend.execute("open",(PASSWORD,"mainnet",""),{})
        with self.assertRaises(Q06ReadOnlyError):
            self.backend.execute("open",(b"short","create",""),{})
        with self.assertRaises(Q06ReadOnlyError):
            self.backend.execute("open",(PASSWORD,"reopen",""),{})
        (self.root/"wallet-vault").mkdir()
        (self.root/("bip39-12-"+("b"*32))).mkdir()
        with self.assertRaises(Q06ReadOnlyError):
            self.backend.execute("open",(PASSWORD,"reopen",""),{})
        self.assertIsNone(self.backend._seed_folder)


if __name__=="__main__":
    unittest.main()
