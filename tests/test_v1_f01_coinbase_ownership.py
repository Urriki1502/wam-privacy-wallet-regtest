"""F-01 adversarial subsidy/treasury ownership regressions.

Synthetic Core-shaped public fixtures are UNIT tests only. Exact Core
coinbase outputs and wallet ownership must be observed independently in
native signed/dev REGTEST E2E; neither this module nor a checksum grants
wallet signing or miner balance authority.
"""
from copy import deepcopy
from decimal import Decimal
import unittest

from wam_regtest.mining_account import CoinbaseAudit, COIN, RewardSplit, treasury_atoms
from wam_regtest.wsp_live import REGTEST_GENESIS

OWNED = "0014" + "11" * 20
TREASURY = "76a914" + "22" * 20 + "88ac"
ALIEN = "0014" + "33" * 20
ZERO = "6a"


def fixture(height=1, fees=141):
    split = RewardSplit.regtest(height, fees)
    def amount(atoms):
        return Decimal(atoms) / Decimal(COIN)
    return {
        "chain": "regtest",
        "genesis": REGTEST_GENESIS,
        "fees": fees,
        "treasury_info": {
            "percent": 5, "start_height": 1, "last_height": 400000,
            "script": TREASURY,
        },
        "owned_address_infos": [
            {"ismine": True, "scriptPubKey": OWNED},
        ],
        "block": {
            "height": height,
            "tx": [{
                "vin": [{"coinbase": "01"}],
                "vout": [
                    {"n": 0, "value": amount(split.miner_atoms),
                     "scriptPubKey": {"hex": OWNED}},
                    {"n": 1, "value": amount(split.treasury_atoms),
                     "scriptPubKey": {"hex": TREASURY}},
                ],
            }],
        },
    }


class F01MinerTreasuryOwnershipContracts(unittest.TestCase):
    def test_exact_real_rpc_shaped_fee_and_treasury_segregation(self):
        for height in (1, 150, 151, 200000, 200001, 400000, 400001):
            with self.subTest(height=height):
                request = fixture(height)
                split = RewardSplit.regtest(height, fees=141)
                row = CoinbaseAudit.from_core(**request)
                self.assertEqual(row.owned_miner_atoms, split.miner_atoms)
                self.assertEqual(row.treasury_paid_atoms, split.treasury_atoms)
                self.assertEqual(row.miner_total_atoms, split.miner_atoms)
                self.assertEqual(row.fees_atoms, 141)
                self.assertEqual(
                    row.miner_total_atoms + row.treasury_paid_atoms,
                    row.subsidy_atoms + 141)

    def test_partially_owned_coinbase_cannot_be_displayed_as_miner_funds(self):
        request = fixture()
        outputs = request["block"]["tx"][0]["vout"]
        outputs[0]["value"] -= Decimal("1")
        outputs.append({"n": 2, "value": Decimal("1"),
                        "scriptPubKey": {"hex": ALIEN}})
        with self.assertRaisesRegex(ValueError, "MINER_COINBASE_AUDIT_DENIED"):
            CoinbaseAudit.from_core(**request)

    def test_unowned_output_cannot_launder_fees_into_a_miner_balance(self):
        request = fixture(fees=100000)
        outputs = request["block"]["tx"][0]["vout"]
        outputs[0]["value"] -= Decimal("0.001")
        outputs.append({"n": 2, "value": Decimal("0.001"),
                        "scriptPubKey": {"hex": ALIEN}})
        with self.assertRaisesRegex(ValueError, "MINER_COINBASE_AUDIT_DENIED"):
            CoinbaseAudit.from_core(**request)

    def test_treasury_gets_subsidy_only_never_transaction_fees(self):
        request = fixture(fees=141)
        outputs = request["block"]["tx"][0]["vout"]
        outputs[0]["value"] -= Decimal("0.00000141")
        outputs[1]["value"] += Decimal("0.00000141")
        with self.assertRaisesRegex(ValueError, "MINER_COINBASE_AUDIT_DENIED"):
            CoinbaseAudit.from_core(**request)

    def test_unowned_zero_value_metadata_is_not_reward(self):
        request = fixture()
        request["block"]["tx"][0]["vout"].append(
            {"n": 2, "value": Decimal("0"), "scriptPubKey": {"hex": ZERO}})
        observation = CoinbaseAudit.from_core(**request)
        self.assertEqual(observation.owned_miner_atoms, 4750000141)

    def test_treasury_wallet_overlap_and_false_owner_are_denied(self):
        for corrupt in ("treasury_in_own", "owner_not_mine",
                        "missing_miner", "wrong_network", "fee_boolean"):
            with self.subTest(corrupt=corrupt):
                request = fixture()
                if corrupt == "treasury_in_own":
                    request["owned_address_infos"].append(
                        {"ismine": True, "scriptPubKey": TREASURY})
                elif corrupt == "owner_not_mine":
                    request["owned_address_infos"][0]["ismine"] = False
                elif corrupt == "missing_miner":
                    request["block"]["tx"][0]["vout"][0]["scriptPubKey"]["hex"] = ALIEN
                elif corrupt == "wrong_network":
                    request["chain"] = "main"
                else:
                    request["fees"] = True
                with self.assertRaises(ValueError):
                    CoinbaseAudit.from_core(**request)

    def test_treasury_cutoff_independent_of_subsidy_amount(self):
        for value in (50 * COIN, 25 * COIN, 1250000000, 1):
            self.assertEqual(treasury_atoms(value, 400000), value * 5 // 100)
            self.assertEqual(treasury_atoms(value, 400001), 0)
        self.assertEqual(RewardSplit.regtest(151).treasury_atoms, 125000000)
        self.assertEqual(RewardSplit.regtest(301).treasury_atoms, 62500000)
        # Production halving at 200001 cannot be inferred from REGTEST:
        # the genuine REGTEST interval is 150, not 200000.
        self.assertEqual(RewardSplit.regtest(200001).subsidy_atoms, 0)


if __name__ == "__main__":
    unittest.main()
