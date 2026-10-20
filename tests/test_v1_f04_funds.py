"""F-04 negative money-category tests; public Core-shaped fixtures only."""
from dataclasses import replace
from decimal import Decimal
import unittest

from wam_regtest.f04_funds import CoreFundsBuckets,CoreFundsRefusal
from wam_regtest.mining_account import MiningWalletBalance
from wam_regtest.wsp_live import REGTEST_GENESIS

OWN='0014'+'ab'*20
TREASURY='76a914'+'ee'*20+'88ac'
TXID='d'*64
AMOUNT=123456789


def scene(locked=True):
    balance=MiningWalletBalance(
        trusted_atoms=AMOUNT, pending_untrusted_atoms=0,
        immature_atoms=4750000000, available_atoms=0 if locked else AMOUNT,
        available_utxos=0 if locked else 1)
    point={'txid':TXID,'vout':2}
    utxo={'value':Decimal('1.23456789'),
          'scriptPubKey':{'hex':OWN},
          'coinbase':False,'confirmations':1}
    return dict(chain='regtest',genesis=REGTEST_GENESIS,balance=balance,
                locked_outpoints=[point] if locked else [],
                locked_txouts={(TXID,2):utxo} if locked else {},
                unlocked_outpoints=[] if locked else [point],
                owned_script=OWN,treasury_script=TREASURY)


class F04FundsContracts(unittest.TestCase):
    def test_locked_core_money_is_not_available_or_immature(self):
        result=CoreFundsBuckets.from_core(**scene())
        self.assertEqual(result.locked_core_atoms,AMOUNT)
        self.assertEqual(result.available_atoms,0)
        self.assertEqual(result.immature_atoms,4750000000)
        self.assertEqual(result.pending_untrusted_atoms,0)
        self.assertEqual(result.core_locked_utxos,1)
        self.assertEqual(result.unattributed_trusted_atoms,0)
        self.assertFalse(result.wsp_reserved_atoms_known)
        self.assertFalse(result.pool_owed_atoms_known)
        self.assertFalse(result.signer_allowed)

    def test_unlock_moves_to_core_eligible_not_new_money(self):
        before=CoreFundsBuckets.from_core(**scene(True))
        after=CoreFundsBuckets.from_core(**scene(False))
        self.assertEqual(before.locked_core_atoms,after.available_atoms)
        self.assertEqual(after.locked_core_atoms,0)
        self.assertEqual(before.trusted_atoms,after.trusted_atoms)
        self.assertEqual(after.immature_atoms,before.immature_atoms)

    def test_trusted_difference_is_not_guessed_as_a_lock(self):
        args=scene(False)
        args['balance']=replace(args['balance'],
                                trusted_atoms=AMOUNT+1000)
        result=CoreFundsBuckets.from_core(**args)
        self.assertEqual(result.unattributed_trusted_atoms,1000)
        self.assertEqual(result.locked_core_atoms,0)

    def test_pending_is_separate_and_not_assumed_spendable(self):
        args=scene(False)
        args['balance']=replace(args['balance'],
                                pending_untrusted_atoms=123000)
        result=CoreFundsBuckets.from_core(**args)
        self.assertEqual(result.pending_untrusted_atoms,123000)
        self.assertEqual(result.available_atoms,AMOUNT)
        self.assertEqual(result.locked_core_atoms,0)

    def test_foreign_or_treasury_locked_outputs_refused(self):
        for bad in (TREASURY,'0014'+'cd'*20):
            with self.subTest(bad=bad):
                args=scene()
                args['locked_txouts'][(TXID,2)]['scriptPubKey']['hex']=bad
                with self.assertRaises(CoreFundsRefusal):
                    CoreFundsBuckets.from_core(**args)

    def test_coinbase_before_maturity_cannot_be_locked_as_eligible(self):
        args=scene()
        args['locked_txouts'][(TXID,2)]['coinbase']=True
        args['locked_txouts'][(TXID,2)]['confirmations']=100
        with self.assertRaises(CoreFundsRefusal):
            CoreFundsBuckets.from_core(**args)

    def test_duplicate_overlap_missing_or_wrong_value_refused(self):
        for mode in ('duplicate','overlap','missing','inflated','wrong_network',
                     'wrong_type','negative','bool_vout','old_coinbase'):
            with self.subTest(mode=mode):
                args=scene()
                if mode=='duplicate':
                    args['locked_outpoints']*=2
                elif mode=='overlap':
                    args['unlocked_outpoints'].append({'txid':TXID,'vout':2})
                elif mode=='missing':
                    args['locked_txouts']={}
                elif mode=='inflated':
                    args['locked_txouts'][(TXID,2)]['value']=Decimal('2')
                elif mode=='wrong_network':
                    args['chain']='main'
                elif mode=='wrong_type':
                    args['locked_outpoints']='all'
                elif mode=='negative':
                    args['balance']=replace(args['balance'],trusted_atoms=-1)
                elif mode=='bool_vout':
                    args['locked_outpoints'][0]['vout']=True
                else:
                    args['locked_txouts'][(TXID,2)]['coinbase']=True
                    args['locked_txouts'][(TXID,2)]['confirmations']=99
                with self.assertRaises(CoreFundsRefusal):
                    CoreFundsBuckets.from_core(**args)

    def test_unattributed_does_not_auto_unlock_or_release_reservations(self):
        args=scene(True)
        args['balance']=replace(args['balance'],trusted_atoms=AMOUNT+7)
        result=CoreFundsBuckets.from_core(**args)
        self.assertEqual(result.unattributed_trusted_atoms,7)
        self.assertEqual(result.available_atoms,0)
        self.assertFalse(result.wsp_reserved_atoms_known)


if __name__=='__main__':
    unittest.main()
