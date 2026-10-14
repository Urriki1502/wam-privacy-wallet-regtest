"""Fail-closed wallet contracts, not real E2E acceptance."""
from pathlib import Path
import unittest
from wam_regtest.operational_gui import parse_amount
from wam_regtest.wallet_session import WalletSession,WalletSessionError,WalletCoreCli
from wam_regtest.wsp_live import RealWspScanError
from wam_regtest.core import smoke_real_core,CoreSmokeError


class WalletSessionContracts(unittest.TestCase):
    def test_disposable_consent_before_key_core_or_storage_operations(self):
        with self.assertRaisesRegex(WalletSessionError,'WALLET_DISPOSABLE_CONSENT_DENIED'):
            WalletSession.create(Path('/unknown'),Path('/unknown'),Path('/unknown'),b'', '',authorized=False)
        with self.assertRaisesRegex(CoreSmokeError,'CORE_DISPOSABLE_WALLET_SCOPE_DENIED'):
            smoke_real_core(Path('/unknown'),explicit_consent=True,wallet_e2e=True)

    def test_cross_session_recovery_requires_disposable_consent(self):
        with self.assertRaisesRegex(WalletSessionError,'WALLET_DISPOSABLE_CONSENT_DENIED'):
            WalletSession.from_backup(Path('/unknown'),Path('/unknown'),Path('/unknown'),
                Path('/unknown'),'wallet.enc',b'', '',authorized=False)

    def test_integer_atoms_without_float_rounding(self):
        self.assertEqual(parse_amount('0.00100000'),100000)
        self.assertEqual(parse_amount('0.00000330'),330)
        for value in ('0.00000329','0.000003301','NaN','Infinity','-1','22000001','1e999','1e9999999','+'+'1','1,000','0.000000001',None):
            with self.assertRaises(ValueError):
                parse_amount(value)

    def test_balance_display_preserves_last_atom_at_supply_boundary(self):
        from wam_regtest.wallet_read import format_wam
        self.assertEqual(format_wam(22_000_000*100_000_000-1,grouped=True),'21,999,999.99999999')
        self.assertEqual(format_wam(1),'0.00000001')

    def test_write_wrapper_never_authorizes_unknown_rpc(self):
        rpc=WalletCoreCli(Path('/unknown-cli'),Path('/unknown-dir'))
        for method in ('dumpprivkey','sendtoaddress','walletpassphrase','importprivkey','stop'):
            with self.assertRaises(RealWspScanError):
                rpc.call(method,[])


if __name__=='__main__':
    unittest.main()
