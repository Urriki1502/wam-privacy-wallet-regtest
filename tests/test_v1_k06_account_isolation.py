"""K-06 original Core vs WSP authority boundaries, publicly disposable keys.

This suite contains no live miner wallet, owner mnemonic, mocked Core E2E pass,
or private credentials. Native WSP Signer inputs use exact pinned upstream.
"""
from copy import deepcopy
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from mnemonic import Mnemonic

from wam_regtest.account_isolation import (
    AccountIsolationError,AccountRegistry,CoreAccount,WspAccount,
    require_native_wsp_accounts,
)
from wam_regtest.bip39_durable import Bip39DurableKeyring
from wam_regtest.v1_contracts import CORE_PROFILE,BIP39_PROFILE,RC1_PROFILE
from wam_regtest.wsp_live import REGTEST_GENESIS
from wam_sp.keystore import Keyring
from wam_sp.wallet import Signer

SOURCE=Path(importlib.util.find_spec("wam_sp").origin).resolve().parents[2]
CORE_INFO={"format":"sqlite","descriptors":True,"private_keys_enabled":True}
A={"descriptors":[
    {"desc":"wpkh([public-fingerprint/84h/1h/0h]PUBLIC_A/0/*)#00000000",
     "internal":False},
    {"desc":"wpkh([public-fingerprint/84h/1h/0h]PUBLIC_A/1/*)#11111111",
     "internal":True},
]}
B={"descriptors":[
    {"desc":"tr(PUBLIC_B/0/*)#22222222","internal":False},
    {"desc":"tr(PUBLIC_B/1/*)#33333333","internal":True},
]}
PARTIAL={"descriptors":[
    {"desc":A["descriptors"][0]["desc"],"internal":False},
    {"desc":"tr(PUBLIC_NEW)#44444444","internal":True},
]}


def core(name,descriptors,info=CORE_INFO,chain="regtest",genesis=REGTEST_GENESIS):
    return CoreAccount.from_core_public(
        name=name,chain=chain,genesis=genesis,wallet_info=info,
        descriptors=descriptors)


class K06AuthorityIsolation(unittest.TestCase):
    def test_core_wallets_have_separate_public_descriptor_identities(self):
        first=core("miner",A)
        second=core("legacy",B)
        registry=AccountRegistry(core=(first,second))
        summary=registry.public_summary()
        self.assertEqual(summary["core_wallet_count"],2)
        self.assertEqual(summary["wsp_wallet_count"],0)
        self.assertFalse(summary["balances_aggregated"])
        self.assertEqual(registry.require_authority(
            kind="core",wallet_id="miner"),first)
        self.assertNotEqual(first.descriptor_identity,second.descriptor_identity)
        self.assertEqual(first.profile,CORE_PROFILE)
        self.assertEqual(first.authority,"core-native-descriptor")
        self.assertFalse(first.fusion_signer_allowed)
        self.assertFalse(registry.require_authority(
            kind="core",wallet_id="legacy").fusion_signer_allowed)

    def test_core_duplicate_and_partial_overlap_fail_even_under_new_name(self):
        first=core("miner",A)
        for bad in (
            core("second-name",A),
            core("partially-overlapping",PARTIAL),
            core("miner",B),
        ):
            with self.subTest(name=bad.name):
                with self.assertRaises(AccountIsolationError):
                    AccountRegistry(core=(first,bad))
        for name,chain,genesis,info in (
            ("../wallet","regtest",REGTEST_GENESIS,CORE_INFO),
            ("mainnet","main",REGTEST_GENESIS,CORE_INFO),
            ("chain","regtest","0"*64,CORE_INFO),
            ("nondesc","regtest",REGTEST_GENESIS,{**CORE_INFO,"descriptors":False}),
            ("berkeley","regtest",REGTEST_GENESIS,{**CORE_INFO,"format":"bdb"}),
        ):
            with self.subTest(name=name):
                with self.assertRaises(AccountIsolationError):
                    core(name,B,info,chain,genesis)

    def test_legacy_wsp_32byte_keys_are_not_bip39_or_core(self):
        with Keyring(seed=b"\x11"*32) as ring:
            scanner=SimpleNamespace(accounts=ring.accounts())
            registered=require_native_wsp_accounts(ring,scanner,"a"*32)
            self.assertEqual(registered.public_summary()["wsp_wallet_count"],1)
            self.assertEqual(len(registered.wsp),1)
            wsp=registered.wsp[0]
            self.assertEqual(wsp.profile,RC1_PROFILE)
            self.assertEqual(wsp.authority,"wsp-bip352")
            self.assertEqual(wsp.account_id,scanner.accounts[0].account_id)
            self.assertIsInstance(Signer(ring),Signer)
            self.assertFalse(wsp.core_wallet_spend_allowed)
            with self.assertRaises(AccountIsolationError):
                registered.require_authority(
                    kind="core",wallet_id="a"*32)
            with self.assertRaises(AccountIsolationError):
                registered.require_authority(
                    kind="wsp",wallet_id="a"*32,
                    account_id=wsp.account_id,operation="sign")
            self.assertEqual(registered.require_authority(
                kind="wsp",wallet_id="a"*32,account_id=wsp.account_id,
                operation="scan"),wsp)

    def test_bip39_keyring_is_a_distinct_wsp_profile_with_same_native_signer(self):
        public_phrase=Mnemonic("english").to_mnemonic(bytes([0x42])*32)
        with Bip39DurableKeyring.from_phrase(
                public_phrase,source=SOURCE,passphrase="PUBLIC_K06_REGTEST",
                account=2,authorized=True) as ring:
            registry=require_native_wsp_accounts(
                ring,SimpleNamespace(accounts=ring.accounts()),"b"*32)
            self.assertEqual(registry.wsp[0].profile,BIP39_PROFILE)
            self.assertEqual(registry.wsp[0].epoch,2)
            self.assertIsInstance(Signer(ring),Signer)
            self.assertNotEqual(registry.wsp[0].profile,RC1_PROFILE)
            with self.assertRaises(AccountIsolationError):
                registry.require_authority(
                    kind="wsp",wallet_id="b"*32,
                    account_id=registry.wsp[0].account_id,operation="broadcast")

    def test_multiple_wsp_epochs_keep_distinct_scan_spend_and_owner_lease(self):
        with Keyring(seed=b"\x51"*32) as a,Keyring(seed=b"\x52"*32) as b:
            a.rotate(111);a.rotate(115)
            r1=require_native_wsp_accounts(
                a,SimpleNamespace(accounts=a.accounts()),"a"*32)
            r2=require_native_wsp_accounts(
                b,SimpleNamespace(accounts=b.accounts()),"b"*32)
            combined=AccountRegistry(wsp=r1.wsp+r2.wsp)
            self.assertEqual(combined.public_summary()["wsp_wallet_count"],2)
            self.assertEqual(combined.public_summary()["wsp_account_count"],4)
            self.assertEqual(len({x.account_id for x in combined.wsp}),4)
            self.assertEqual([x.epoch for x in r1.wsp],[0,1,2])
            self.assertEqual([x.epoch for x in r2.wsp],[0])
            with self.assertRaises(AccountIsolationError):
                AccountRegistry(wsp=r1.wsp+r1.wsp[:1])
            # Even two *different* native wallet IDs cannot claim the
            # same WSP scan/spend account; prevents duplicate ownership.
            clone=r1.wsp[0]
            impostor=WspAccount("c"*32,clone.account_id,clone.epoch,
                                clone.receive_code,clone.profile)
            with self.assertRaises(AccountIsolationError):
                AccountRegistry(wsp=r1.wsp+(impostor,))
            impostor_same_vault=WspAccount(
                clone.wallet_id,"f"*64,clone.epoch,
                clone.receive_code,clone.profile)
            with self.assertRaises(AccountIsolationError):
                AccountRegistry(wsp=r1.wsp+(impostor_same_vault,))

    def test_cross_type_balance_and_recovery_claim_never_grants_sign(self):
        with Keyring(seed=b"\x61"*32) as ring:
            wsp=require_native_wsp_accounts(
                ring,SimpleNamespace(accounts=ring.accounts()),"a"*32)
            registry=AccountRegistry(core=(core("mining",A),core("legacy",B)),
                                     wsp=wsp.wsp)
            public=registry.public_summary()
            self.assertEqual(public,{
                "chain":"regtest","core_wallet_count":2,"wsp_wallet_count":1,
                "wsp_account_count":1,"balances_aggregated":False,
                "cross_account_signing":False,"mainnet_allowed":False,
            })
            wsp_id=wsp.wsp[0].account_id
            for kind,wallet,account,operation in (
                ("core","mining",wsp_id,"read"),
                ("core","mining",None,"sign"),
                ("core","mining",None,"scan"),
                ("wsp","mining",wsp_id,"read"),
                ("wsp","a"*32,core("mining",A).descriptor_identity,"read"),
                ("wsp","a"*32,wsp_id,"sign"),
                ("wsp","a"*32,wsp_id,"broadcast"),
                ("wsp","a"*32,wsp_id,"import_core_dat"),
                ("fake","a"*32,wsp_id,"read"),
                ("wsp","a"*32,wsp_id,True),
            ):
                with self.subTest(kind=kind,operation=operation):
                    with self.assertRaises(AccountIsolationError):
                        registry.require_authority(
                            kind=kind,wallet_id=wallet,account_id=account,
                            operation=operation)

    def test_wrong_or_fabricated_native_signer_never_adopted(self):
        with Keyring(seed=b"\x21"*32) as ring,Keyring(seed=b"\x22"*32) as other:
            with self.assertRaises(AccountIsolationError):
                require_native_wsp_accounts(
                    ring,SimpleNamespace(accounts=other.accounts()),"a"*32)
            with self.assertRaises(AccountIsolationError):
                require_native_wsp_accounts(
                    ring,SimpleNamespace(accounts=ring.accounts()),True)
            with self.assertRaises(AccountIsolationError):
                require_native_wsp_accounts(
                    SimpleNamespace(accounts=ring.accounts),
                    SimpleNamespace(accounts=ring.accounts()),"a"*32)
            with self.assertRaises(AccountIsolationError):
                require_native_wsp_accounts(
                    ring,SimpleNamespace(accounts=ring.accounts()*2),"a"*32)
            with self.assertRaises(AccountIsolationError):
                require_native_wsp_accounts(
                    ring,SimpleNamespace(accounts=list(ring.accounts())),"a"*32)

if __name__=="__main__":
    unittest.main()
