"""F-07 pinned, public-only WAM legacy address parser regression tests.

The collision is SOURCE/OFFLINE reproducible. Live MAINNET node rejection
is NOT tested and must never be reported from these synthetic fixtures.
"""
from dataclasses import replace
import unittest

from wam_regtest.f07_address_parity import (
    inspect_legacy_public, verify_core_regtest_legacy,
    classify_collision_send_refusal, AddressParityRefusal, NETS,
    CORE_SOURCE_KEY_IO_V28_1, WAM_CHAINPARAMS_V011,
)

MAIN_P2PKH="WamAskWnsuS1LBhLhgGQSo9HACyE4aHLER"
MAIN_P2SH="waMSB1joxWLA9nFTHpNT9HHKpavsLW7WXG"
NORMAL_MAIN="WdMMqW1DcgWZ6HtyJuEMdce6QkKg4raGmE"
REG_P2PKH="TBDeDSETJdmttTFUwFVL8Qpw4SV87XAYEj"
REG_P2SH="tjtGH5pUR8i7GweABGcPgFzic8Fv8mYLvq"


class F07PublicParserParityTests(unittest.TestCase):
    def test_mainnet_collision_is_base58_valid_but_not_node_acceptance(self):
        self.assertEqual(len(CORE_SOURCE_KEY_IO_V28_1),40)
        self.assertEqual(len(WAM_CHAINPARAMS_V011),40)
        for value,kind in ((MAIN_P2PKH,'P2PKH'),(MAIN_P2SH,'P2SH')):
            with self.subTest(address=value):
                row=inspect_legacy_public(value,network='main')
                self.assertEqual(row.network,'main')
                self.assertEqual(row.kind,kind)
                self.assertTrue(row.checksum_valid)
                self.assertTrue(row.core_bech32_prefix_collision)
                self.assertFalse(row.offline_decoding_is_core_acceptance)
                self.assertFalse(row.signer_allowed)
                self.assertFalse(row.imported_key_deleted)
                self.assertEqual(
                    classify_collision_send_refusal(value),
                    'WALLET_F07_CORE_BASE58_HRP_COLLISION_SEND_DENIED')

    def test_noncolliding_mainnet_is_still_not_regtest_send(self):
        row=inspect_legacy_public(NORMAL_MAIN,network='main')
        self.assertFalse(row.core_bech32_prefix_collision)
        self.assertEqual(row.kind,'P2PKH')
        self.assertEqual(
            classify_collision_send_refusal(NORMAL_MAIN),
            'WALLET_F07_MAINNET_LEGACY_ON_REGTEST_DENIED')
        self.assertEqual(row.script_pub_key,
                         '76a914a101cf17c209638136abe19e14dc4e1c9987370f88ac')

    def test_regtest_public_addresses_have_valid_correct_scripts(self):
        cases=((REG_P2PKH,'P2PKH',
                '76a9140db2ff0f7efc0e50e889ad7bf4a6403a4f6ec87c88ac'),
               (REG_P2SH,'P2SH',
                'a914956b517757cc10cab509dbe6d4f0bc5e6c1e380987'))
        for addr,kind,script in cases:
            with self.subTest(addr=addr):
                row=inspect_legacy_public(addr,network='regtest')
                self.assertEqual(row.kind,kind)
                self.assertEqual(row.script_pub_key,script)
                self.assertFalse(row.core_bech32_prefix_collision)
                accepted=verify_core_regtest_legacy(addr,core_reply={
                    'isvalid':True,'scriptPubKey':script})
                self.assertTrue(accepted.address_accepted_by_core)
                self.assertTrue(accepted.expected_script_matches_core)
                self.assertFalse(accepted.spending_allowed)
                self.assertFalse(accepted.mainnet_runtime_qualified)

    def test_wrong_chain_wrong_checksum_case_change_are_refused(self):
        for address,network in (
            (MAIN_P2PKH,'regtest'),(MAIN_P2SH,'test'),
            (REG_P2PKH,'main'),(REG_P2SH,'main'),
            (MAIN_P2PKH[:-1]+'S','main'),
            (MAIN_P2SH.swapcase(),'main'),
            (MAIN_P2SH[:-1]+'0','main'),
            (MAIN_P2PKH,'unknown'),
        ):
            with self.subTest(address=address,network=network):
                with self.assertRaises(AddressParityRefusal):
                    inspect_legacy_public(address,network=network)

    def test_core_reply_must_match_native_script_and_validity(self):
        script=inspect_legacy_public(REG_P2PKH,network='regtest').script_pub_key
        for reply in (None,{},[],{'isvalid':False},
                      {'isvalid':True,'scriptPubKey':'0014'+'00'*20},
                      {'isvalid':1,'scriptPubKey':script},
                      {'isvalid':True,'scriptPubKey':script.upper()}):
            with self.subTest(reply=reply):
                with self.assertRaises(AddressParityRefusal):
                    verify_core_regtest_legacy(REG_P2PKH,core_reply=reply)

    def test_malformed_and_wsp_code_are_not_legacy_send_authority(self):
        for text in ("","wamrtsp1abcdefghijklmnop","wam1q1234",
                     "abc","Wam",None,123):
            with self.subTest(text=text):
                self.assertIsNone(classify_collision_send_refusal(text))
        for address in (True,123,None,'Wam','') :
            with self.assertRaises(AddressParityRefusal):
                inspect_legacy_public(address,network='main')


if __name__=='__main__':
    unittest.main()
