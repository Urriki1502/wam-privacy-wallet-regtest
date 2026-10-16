import unittest
from wam_regtest.v1_contracts import *

class WalletBoundaries(unittest.TestCase):
    def test_exact_network_and_versioned_paths(self):
        require_regtest('regtest', REGTEST_GENESIS)
        self.assertEqual(derivation_paths(BIP39_PROFILE)['scan'], "m/352'/1'/0'/1'/0")
        for chain, genesis in [('main', REGTEST_GENESIS), ('regtest', '0'*64), (True, REGTEST_GENESIS)]:
            with self.assertRaises(WalletContractError): require_regtest(chain, genesis)
        for profile in ['bip39', 'mainnet', RC1_PROFILE, CORE_PROFILE, None]:
            with self.assertRaises(WalletContractError): derivation_paths(profile)
        for account in [True, -1, 16, 2**31]:
            with self.assertRaises(WalletContractError): derivation_paths(BIP39_PROFILE, account)

    def test_account_models_remain_distinct(self):
        self.assertEqual(len({metadata(p)['profile'] for p in [BIP39_PROFILE, CORE_PROFILE, RC1_PROFILE]}), 3)
        for p in [BIP39_PROFILE, CORE_PROFILE, RC1_PROFILE]:
            self.assertIs(metadata(p)['mainnet_allowed'], False)

    def test_core_observation_does_not_infer_descriptor_from_sqlite(self):
        info={'format':'sqlite','descriptors':True,'private_keys_enabled':True}
        balances={'mine':{'trusted':'1.00000001','untrusted_pending':0,'immature':50}}
        value=CoreWalletObservation.from_rpc(chain='regtest',genesis=REGTEST_GENESIS,wallet_info=info,balances=balances)
        self.assertEqual(value.trusted_atoms,100000001); self.assertEqual(value.immature_atoms,5000000000)
        for bad in [{**info,'descriptors':False},{**info,'format':'bdb'},{**info,'private_keys_enabled':1}]:
            with self.assertRaises(WalletContractError):CoreWalletObservation.from_rpc(chain='regtest',genesis=REGTEST_GENESIS,wallet_info=bad,balances=balances)
        self.assertFalse(hasattr(value,'confirmed_atoms'))
        for amount in [True, 'NaN', 'Infinity', '-1', '0.000000001', '22000001', object()]:
            with self.assertRaises(WalletContractError):rpc_atoms(amount)

    def test_duplicate_public_descriptor_identity_ignores_local_names_and_indices(self):
        original={'wallet_name':'first','descriptors':[{'desc':'wpkh(PUBLIC_TEST_KEY)#checksum','internal':False,'next_index':1}]}
        copy={'wallet_name':'second','descriptors':[{'desc':'wpkh(PUBLIC_TEST_KEY)#checksum','internal':False,'next_index':100}]}
        identity=core_descriptor_identity(original)
        self.assertEqual(identity,core_descriptor_identity(copy))
        with self.assertRaises(WalletContractError):require_unique_core_identity(identity,{identity})
        require_unique_core_identity(identity,set())
