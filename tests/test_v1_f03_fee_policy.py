"""F-03 exact-atom fee policy and target-block tests; UNIT only."""
from dataclasses import replace
from decimal import Decimal
import unittest

from wam_regtest.f03_fee_policy import (
    CoreFeeWitness, FeePolicyRefusal, MAX_PAYMENT_FEE_ATOMS,
    WAM_TARGET_BLOCK_SECONDS, optional_core_estimate, target_confirmation_seconds,
    exact_spend_budget,
)


def actual(size=180, fee_atoms=10000):
    return dict(network_info={'relayfee':Decimal('0.00001000')},
        mempool_info={'mempoolminfee':Decimal('0.00001000')},
        entry={'vsize':size,'fees':{'base':Decimal(fee_atoms)/100000000}},
        actual_fee_atoms=fee_atoms)


class F03FeePolicyTests(unittest.TestCase):
    def test_wam_120_second_target_is_not_10_minute_bitcoin_constant(self):
        self.assertEqual(WAM_TARGET_BLOCK_SECONDS,120)
        for n in (1,2,6,12,100):
            self.assertEqual(target_confirmation_seconds(n),120*n)
        for n in (0,-1,True,1.0,101):
            with self.assertRaises(FeePolicyRefusal):
                target_confirmation_seconds(n)

    def test_measured_core_fee_rate_in_exact_atoms_per_1000_vbytes(self):
        witness=CoreFeeWitness.from_core(**actual())
        self.assertEqual(witness.relay_atoms_per_kvb,1000)
        self.assertEqual(witness.mempool_floor_atoms_per_kvb,1000)
        self.assertEqual(witness.minimum_fee_atoms,180)
        self.assertEqual(witness.observed_fee_atoms,10000)
        self.assertEqual(witness.observed_atoms_per_kvb_ceil,55556)
        self.assertEqual(witness.fee_cap_atoms,1_000_000)
        self.assertTrue(witness.mempool_entry_relay_eligible)
        self.assertFalse(witness.estimate_is_guarantee)
        self.assertFalse(witness.signer_allowed)

    def test_ceiling_rounding_and_mempool_floor_above_relay(self):
        p=actual(size=333,fee_atoms=1665)
        p['mempool_info']['mempoolminfee']=Decimal('0.00005000')
        row=CoreFeeWitness.from_core(**p)
        self.assertEqual(row.effective_floor_atoms_per_kvb,5000)
        self.assertEqual(row.minimum_fee_atoms,1665)
        p['actual_fee_atoms']=1664
        p['entry']['fees']['base']=Decimal(1664)/100000000
        with self.assertRaises(FeePolicyRefusal):
            CoreFeeWitness.from_core(**p)

    def test_fee_mismatch_huge_fee_noninteger_and_vsize_denied(self):
        for mode in ('mismatch','huge','bool','negative','size_bool',
                     'size_zero','size_huge','size_float','missing_fee'):
            with self.subTest(mode=mode):
                p=actual()
                if mode=='mismatch':p['actual_fee_atoms']+=1
                elif mode=='huge':
                    p['actual_fee_atoms']=MAX_PAYMENT_FEE_ATOMS+1
                    p['entry']['fees']['base']=Decimal('0.01000001')
                elif mode=='bool':p['actual_fee_atoms']=True
                elif mode=='negative':p['actual_fee_atoms']=-1
                elif mode=='size_bool':p['entry']['vsize']=True
                elif mode=='size_zero':p['entry']['vsize']=0
                elif mode=='size_huge':p['entry']['vsize']=400001
                elif mode=='size_float':p['entry']['vsize']=180.0
                else:p['entry']['fees'].pop('base')
                with self.assertRaises(FeePolicyRefusal):
                    CoreFeeWitness.from_core(**p)

    def test_relay_and_mempool_rate_denial_and_missing_schema(self):
        for bad in ('0','NaN','-1','0.10000000',None,True,'0.000000001'):
            for kind,field in (('network_info','relayfee'),('mempool_info','mempoolminfee')):
                with self.subTest(bad=bad,kind=kind):
                    p=actual()
                    p[kind][field]=bad
                    with self.assertRaises(FeePolicyRefusal):
                        CoreFeeWitness.from_core(**p)
        p=actual();p['network_info'].pop('relayfee')
        with self.assertRaises(FeePolicyRefusal):
            CoreFeeWitness.from_core(**p)

    def test_spend_budget_exact_inputs_fee_and_change(self):
        self.assertEqual(exact_spend_budget(100000,10000,[80000,50000]),20000)
        self.assertEqual(exact_spend_budget(100000,10000,[110000]),0)
        self.assertEqual(exact_spend_budget(330,1,[332]),1)
        for args in (
            (True,10000,[110000]),
            (100000,True,[110000]),
            (0,10000,[110000]),
            (329,10000,[110000]),
            (100000,0,[110000]),
            (100000,1000001,[1100000]),
            (100000,10000,[109999]),
            (100000,10000,[]),
            (100000,10000,[True,120000]),
            (100000,10000,[0,120000]),
            (100000,10000,[float(120000)]),
            (22_000_000*100_000_000,10000,[22_000_000*100_000_000]),
        ):
            with self.subTest(args=args):
                with self.assertRaises(FeePolicyRefusal):
                    exact_spend_budget(*args)

    def test_short_regtest_estimator_is_not_a_fee_guarantee(self):
        self.assertEqual(optional_core_estimate({'errors':['Insufficient data']}),(False,None))
        self.assertEqual(optional_core_estimate({}),(False,None))
        self.assertEqual(optional_core_estimate({'feerate':Decimal('0.00010000')}),(True,10000))
        for bad in ('NaN','0',1.0,None,True):
            if bad is None:continue
            with self.subTest(bad=bad):
                with self.assertRaises(FeePolicyRefusal):
                    optional_core_estimate({'feerate':bad})
        for obj in ([],None,{'errors':'bad'},{'errors':[42]}):
            with self.assertRaises(FeePolicyRefusal):
                optional_core_estimate(obj)


if __name__=="__main__":
    unittest.main()
