"""K-02 public deterministic derivation contracts; no live keys/funds/Core RPC."""
import copy
import importlib.util
from pathlib import Path
import unittest
from mnemonic import Mnemonic
from wam_sp.hd import ExtendedPrivate,HARDENED
from wam_regtest.bip39_wallet import Bip39RegtestKeys,MnemonicWalletError
from wam_regtest.v1_contracts import (
    BIP39_PROFILE,CORE_PROFILE,RC1_PROFILE,REGTEST_GENESIS,
    REGTEST_ACCOUNT_LIMIT,REGTEST_COIN_TYPE,
    derivation_paths,derivation_profile_receipt,
    require_derivation_profile_receipt,WalletContractError,
)

SOURCE=Path(importlib.util.find_spec('wam_sp').origin).resolve().parents[2]
# Independently committed checksums of canonical public test-only profile
# records for account indexes 0, 1 and 15. Mutation must require deliberate
# new profile/version and requalification, never silent backup recovery drift.
PROFILE_GOLDENS={
    0:"8a0dcc917ec5fd0ac8fd219f6fd3c615e323ace02886f3061d6b5b03c72c7e34",
    1:"3ef5ec19d2f78bb136bec45a923c85b17fb40441dbc2a7e821e50c32bd61a133",
    15:"3762436fb6dcb0717c68856de786b729996aa5321031c4c72e136c92120eb751",
}

class StableRegtestDerivation(unittest.TestCase):
    @staticmethod
    def keys(phrase,passphrase="TREZOR"):
        return Bip39RegtestKeys(phrase,source=SOURCE,passphrase=passphrase,
                               authorized_disposable=True)

    def test_versioned_paths_and_fingerprints_are_frozen_for_all_accounts(self):
        self.assertEqual(REGTEST_COIN_TYPE,1)
        self.assertEqual(REGTEST_ACCOUNT_LIMIT,16)
        unique=set()
        for account in range(REGTEST_ACCOUNT_LIMIT):
            receipt=derivation_profile_receipt(BIP39_PROFILE,account)
            self.assertEqual(receipt['schema'],
                             'wam-fusion-regtest-bip352-derivation/v1')
            self.assertEqual(receipt['version'],1)
            self.assertEqual(receipt['purpose'],352)
            self.assertEqual(receipt['coin_type'],1)
            self.assertEqual(receipt['spend_role'],0)
            self.assertEqual(receipt['scan_role'],1)
            self.assertEqual(receipt['chain'],'regtest')
            self.assertEqual(receipt['genesis'],REGTEST_GENESIS)
            self.assertIs(receipt['legacy_wsp32_interpretable'],False)
            self.assertIs(receipt['production_qualified'],False)
            self.assertIs(receipt['mainnet_allowed'],False)
            self.assertEqual(receipt['paths']['scan'],
                             f"m/352'/1'/{account}'/1'/0")
            self.assertEqual(receipt['paths']['spend'],
                             f"m/352'/1'/{account}'/0'/0")
            self.assertEqual(require_derivation_profile_receipt(
                receipt,account=account),receipt)
            self.assertNotIn(receipt['fingerprint_sha256'],unique)
            unique.add(receipt['fingerprint_sha256'])
            if account in PROFILE_GOLDENS:
                self.assertEqual(receipt['fingerprint_sha256'],
                                 PROFILE_GOLDENS[account])
        self.assertEqual(len(unique),16)

    def test_wrong_mainnet_coin_account_and_legacy_profiles_fail_closed(self):
        for invalid in (True,False,None,-1,16,2**32,'0'):
            with self.subTest(account=invalid):
                with self.assertRaises(WalletContractError):
                    derivation_profile_receipt(BIP39_PROFILE,invalid)
        for wrong in ('mainnet','bip39',CORE_PROFILE,RC1_PROFILE,'',None):
            with self.subTest(profile=wrong):
                with self.assertRaises(WalletContractError):
                    derivation_profile_receipt(wrong,0)

    def test_mutating_any_public_profile_identity_refuses_even_with_checksum(self):
        original=derivation_profile_receipt(BIP39_PROFILE,1)
        mutations=(
            ('profile','fusion-mainnet-test'),
            ('version',2),
            ('chain','main'),
            ('genesis','f'*64),
            ('coin_type',0),
            ('coin_type',3),
            ('coin_type',True),  # True == 1 in Python: explicitly reject.
            ('account',True),
            ('mainnet_allowed',0),  # False == 0, but typed receipt MUST deny.
            ('version',True),
            ('spend_role',1),
            ('scan_role',0),
            ('account',0),
            ('account_limit_exclusive',2**31),
            ('mainnet_allowed',True),
            ('legacy_wsp32_interpretable',True),
            ('fingerprint_sha256','0'*64),
        )
        for key,value in mutations:
            with self.subTest(field=key):
                wrong=copy.deepcopy(original)
                wrong[key]=value
                with self.assertRaisesRegex(
                        WalletContractError,'^V1_DERIVATION_RECEIPT_DENIED$'):
                    require_derivation_profile_receipt(wrong,account=1)
        wrong=copy.deepcopy(original)
        wrong['paths']['spend']="m/352'/0'/1'/0'/0"
        with self.assertRaises(WalletContractError):
            require_derivation_profile_receipt(wrong,account=1)
        wrong=copy.deepcopy(original);wrong['public-extra']='unsigned-value'
        with self.assertRaises(WalletContractError):
            require_derivation_profile_receipt(wrong,account=1)

    def test_true_bip39_seed_to_native_scan_key_and_restore_per_account(self):
        # Deterministic PUBLIC 24-word entropy, never a private user mnemonic.
        phrase=Mnemonic('english').to_mnemonic(bytes([0x42])*32)
        with self.keys(phrase) as first,self.keys(phrase) as restored:
            root=ExtendedPrivate.master(bytes(first._seed))
            observed=set()
            for account in (0,1,15):
                report=first.public_metadata(account)
                self.assertEqual(report['derivation_contract'],
                                 derivation_profile_receipt(BIP39_PROFILE,account))
                self.assertEqual(first.require_public_metadata(report,account),report)
                self.assertEqual(restored.require_public_metadata(report,account),report)
                self.assertEqual(restored.public_metadata(account),report)
                expected=root.derive((
                    352|HARDENED,1|HARDENED,account|HARDENED,
                    1|HARDENED,0))
                self.assertEqual(first.scan_account(account).scan_secret,
                                 int.from_bytes(expected.secret,'big'))
                self.assertNotIn(report['receive_code'],observed)
                observed.add(report['receive_code'])
            tampered=copy.deepcopy(first.public_metadata(1))
            tampered['account']=0
            with self.assertRaisesRegex(
                    MnemonicWalletError,'^BIP39_PUBLIC_PROFILE_IDENTITY_DENIED$'):
                first.require_public_metadata(tampered,1)
            tampered=copy.deepcopy(first.public_metadata(1))
            tampered['derivation_contract']['coin_type']=0
            with self.assertRaises(MnemonicWalletError):
                first.require_public_metadata(tampered,1)
            tampered=copy.deepcopy(first.public_metadata(1))
            tampered['account']=True
            with self.assertRaises(MnemonicWalletError):
                first.require_public_metadata(tampered,1)
            with self.assertRaises(MnemonicWalletError):
                first._key(1,'unapproved-role')
        with self.assertRaises(MnemonicWalletError):
            first.public_metadata(0)

if __name__=="__main__":
    unittest.main()
