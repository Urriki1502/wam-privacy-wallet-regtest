"""F-02 immutable maturity-witness contracts; public synthetic fixtures only.

A passing contract test is NOT evidence of a real WAM Core wallet send.
Native REGTEST acceptance separately runs an isolated Core at 99/100/101.
"""
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
import unittest

from wam_regtest.f02_maturity import (
    CoinbaseMaturityRefusal, DisposableCoinbaseMaturity,
)
from wam_regtest.mining_account import MiningWalletBalance
from wam_regtest.wsp_live import REGTEST_GENESIS

SCRIPT = '0014'+'44'*20
ATOM = 4750000000


def observed(depth):
    immature = depth < 101
    return {
        'chain': 'regtest',
        'genesis': REGTEST_GENESIS,
        'height': depth,
        'origin_height': 1,
        'utxo': {
            'coinbase': True,
            'confirmations': depth,
            'scriptPubKey': {'hex': SCRIPT},
            'value': Decimal('47.5'),
        },
        'wallet_balance': MiningWalletBalance(
            trusted_atoms=0 if immature else ATOM,
            pending_untrusted_atoms=0,
            immature_atoms=ATOM if immature else 0,
            available_atoms=0 if immature else ATOM,
            available_utxos=0 if immature else 1,
        ),
        'owned_script': SCRIPT,
        'miner_atoms': ATOM,
    }


class F02MaturityBoundaryContracts(unittest.TestCase):
    def test_99_and_100_immature_only_101_available(self):
        for depth in (99,100,101):
            with self.subTest(depth=depth):
                proof=DisposableCoinbaseMaturity.from_core(**observed(depth))
                self.assertEqual(proof.depth,depth)
                self.assertEqual(proof.first_coinbase_atoms,ATOM)
                self.assertEqual(proof.immature_atoms,ATOM if depth<101 else 0)
                self.assertEqual(proof.available_atoms,0 if depth<101 else ATOM)
                self.assertIs(proof.wallet_send_allowed_by_maturity,depth==101)
                self.assertFalse(proof.signer_allowed)
                self.assertFalse(proof.broadcast_allowed)
                self.assertFalse(proof.mainnet_allowed)

    def test_confirmations_must_be_from_same_core_height(self):
        for depth,claimed in ((99,100),(100,101),(101,100),(101,102)):
            with self.subTest(depth=depth,claimed=claimed):
                data=observed(depth)
                data['utxo']['confirmations']=claimed
                with self.assertRaises(CoinbaseMaturityRefusal):
                    DisposableCoinbaseMaturity.from_core(**data)

    def test_early_spendable_or_trusted_wallet_is_denied(self):
        for depth in (99,100):
            for change in (
                {'available_atoms':ATOM},
                {'available_utxos':1},
                {'trusted_atoms':ATOM},
                {'immature_atoms':0},
                {'pending_untrusted_atoms':100},
            ):
                with self.subTest(depth=depth,change=change):
                    data=observed(depth)
                    data['wallet_balance']=replace(
                        data['wallet_balance'],**change)
                    with self.assertRaises(CoinbaseMaturityRefusal):
                        DisposableCoinbaseMaturity.from_core(**data)

    def test_mature_requires_wallet_balance_and_actual_utxo(self):
        for change in (
            {'available_atoms':0},
            {'available_utxos':0},
            {'immature_atoms':ATOM},
            {'trusted_atoms':0},
        ):
            with self.subTest(change=change):
                data=observed(101)
                data['wallet_balance']=replace(data['wallet_balance'],**change)
                with self.assertRaises(CoinbaseMaturityRefusal):
                    DisposableCoinbaseMaturity.from_core(**data)

    def test_wrong_genesis_coinbase_flag_amount_script_refused(self):
        for field,value in (
            ('genesis','f'*64),
            ('chain','main'),
            ('origin_height',2),
            ('origin_height',True),
            ('height',True),
            ('miner_atoms',ATOM+1),
        ):
            with self.subTest(field=field):
                data=observed(101)
                data[field]=value
                with self.assertRaises(ValueError):
                    DisposableCoinbaseMaturity.from_core(**data)
        for field,value in (
            ('coinbase',False),
            ('coinbase',1),
            ('value',Decimal('50')),
            ('confirmations',101.0),
            ('scriptPubKey',{'hex':'0014'+'55'*20}),
        ):
            with self.subTest(field=field):
                data=observed(101)
                data['utxo'][field]=value
                with self.assertRaises(CoinbaseMaturityRefusal):
                    DisposableCoinbaseMaturity.from_core(**data)

    def test_no_other_depth_or_balance_schema_is_accepted(self):
        for depth in (0,1,98,102,150,151):
            data=observed(depth)
            with self.subTest(depth=depth):
                with self.assertRaises(CoinbaseMaturityRefusal):
                    DisposableCoinbaseMaturity.from_core(**data)
        data=observed(101)
        data['wallet_balance']={'trusted_atoms':ATOM}
        with self.assertRaises(CoinbaseMaturityRefusal):
            DisposableCoinbaseMaturity.from_core(**data)


if __name__=='__main__':
    unittest.main()
