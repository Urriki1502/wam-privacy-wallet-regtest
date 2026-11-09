"""Integer atoms must not depend on a caller's Decimal context."""
from decimal import localcontext, ROUND_UP, Inexact
import unittest
from wam_regtest.amounts import parse_amount, _parse_atoms

class PaymentAmountPrecision(unittest.TestCase):
    def test_exact_amount_even_under_low_precision_decimal_context(self):
        with localcontext() as context:
            context.prec = 6
            context.rounding = ROUND_UP
            self.assertEqual(parse_amount('1.23456789'), 123456789)
            self.assertEqual(_parse_atoms('0.00000101', 1, 1000000), 101)
            self.assertEqual(parse_amount('22000000'), 2200000000000000)

    def test_decimal_inexact_trap_cannot_change_valid_input(self):
        with localcontext() as context:
            context.prec = 2
            context.traps[Inexact] = True
            self.assertEqual(parse_amount('1.23456789'), 123456789)

    def test_boundaries_and_malformed_inputs_never_round(self):
        for raw, expected in [('0.00000001',1),('0.000001',100),('0.01',1000000)]:
            self.assertEqual(_parse_atoms(raw,1,1000000),expected)
        self.assertEqual(parse_amount('0.00000330'),330)
        for raw in ['0','-1','+1',' 1','1 ','1e-8','NaN','Infinity','.1','1.',
                    '01','0.000000001','0.000003299','22000000.00000001',
                    '999999999','1,000','0.00000329']:
            with self.subTest(raw=raw),self.assertRaises(ValueError):
                parse_amount(raw)
        for raw in ['0','-0.00000001','0.000000001','0.01000001']:
            with self.subTest(raw=raw),self.assertRaises(ValueError):
                _parse_atoms(raw,1,1000000)

if __name__=='__main__':unittest.main(verbosity=2)
