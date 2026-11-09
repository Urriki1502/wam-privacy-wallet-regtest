"""Phase 3 source contracts: Q10 metadata vs runtime, Q13 exact payment HRP.

Public BIP39 test mnemonic only. No profile IO, Core, custody or signer authority.
"""
from hashlib import pbkdf2_hmac
import importlib.util
from pathlib import Path
import unittest

from wam_regtest import bip39_12
from wam_regtest.bip39_12 import Bip39Regtest12Keys
from wam_regtest.recovery_metadata import PATHS, VERSION, validate_public_metadata
from wam_regtest.wsp_live import REGTEST_GENESIS
from wam_sp.codec import encode
from wam_sp.core import HRP, address, decode_address, pub
from wam_sp.hd import HARDENED
from wam_sp.wallet import Intent
from test_offline_wam_compatibility import PHRASE, independent_public

SOURCE = Path(importlib.util.find_spec('wam_sp').origin).resolve().parents[2]


def parse(path):
    assert path.startswith('m/')
    return tuple(int(p[:-1]) | HARDENED if p.endswith("'") else int(p) for p in path[2:].split('/'))


class RecoveryMetadataMatchesRuntime(unittest.TestCase):
    def setUp(self):
        self.keys = Bip39Regtest12Keys(PHRASE, source=SOURCE, authorized_disposable=True)
        self.addCleanup(self.keys.close)
        self.public = self.keys.public_metadata()

    def test_paths_are_the_real_runtime_derivation_by_independent_reference(self):
        self.assertEqual(self.public['paths'], PATHS)
        seed = pbkdf2_hmac('sha512', PHRASE.encode(), b'mnemonic', 2048)
        for role in ('scan', 'spend'):
            self.assertEqual(pub(self.keys._key(0, role)),
                             independent_public(seed, parse(PATHS[role])), role)

    def test_network_hrp_birthday_and_labels_match_what_runtime_scans(self):
        account = self.keys.accounts()[0]
        self.assertEqual(HRP, 'wamrtsp')
        self.assertEqual(self.public['genesis'], REGTEST_GENESIS)
        self.assertEqual(decode_address(self.public['receive_code'], HRP)[0].format(),
                         pub(self.keys._key(0, 'scan')))
        # Runtime always scans from height 1 and allocates no labels, so a
        # recovery hint can never narrow the scan window or skip a label.
        self.assertEqual(account.birthday, 1)
        self.assertEqual(account.labels, ())
        hint = validate_public_metadata({'version': VERSION,
            'chain': {'network': 'regtest', 'genesis': REGTEST_GENESIS},
            'birthday': 1, 'mining_descriptors': None, 'paths': dict(PATHS),
            'hrp': HRP, 'label_high_water_mark': 0})
        self.assertEqual((hint['birthday'], hint['label_high_water_mark']), (account.birthday, len(account.labels)))
        self.assertEqual(self.public['profile'], 'fusion-bip39-12-bip32-bip352-regtest-v1')


class PaymentIntentExactHrp(unittest.TestCase):
    """Fusion prepare() validates recipients only through WSP Intent.validate."""

    def test_only_full_exact_regtest_sp_hrp_is_payable(self):
        good = address(7, pub(11), hrp='wamrtsp')
        Intent(good, 330).validate()
        Intent(good.upper(), 330).validate()  # BIP173/350 whole-string uppercase.
        payload = pub(7) + pub(11)
        denied = {
            'mainnet_sp': address(7, pub(11), hrp='wamsp'),
            'testnet_sp': address(7, pub(11), hrp='twamsp'),
            'bip352_reference_sp': address(7, pub(11), hrp='sp'),
            'confusable_longer_hrp': encode('wamrtspx', payload),
            'confusable_shorter_hrp': encode('wamrts', payload),
            'segwit_regtest_v0': encode('wamrt', bytes(20), bech32m=False),
            'segwit_regtest_v1': encode('wamrt', bytes(32), version=1),
            'mixed_case': good[:9].upper() + good[9:],
            'bad_checksum': good[:-1] + ('q' if good[-1] != 'q' else 'p'),
            'bech32_not_bech32m': encode('wamrtsp', payload, bech32m=False),
            'sp_version_1': encode('wamrtsp', payload, version=1),
            'truncated_payload': encode('wamrtsp', payload[:-1]),
            'extended_payload': encode('wamrtsp', payload + b'\x00'),
            'invalid_point': encode('wamrtsp', b'\x02' + bytes(32) + pub(11)),
            'empty': '',
        }
        for name, code in denied.items():
            with self.subTest(case=name), self.assertRaises(ValueError):
                Intent(code, 330).validate()

    def test_lengths_of_proposed_namespaces(self):
        self.assertEqual([len(address(7, pub(11), hrp=h)) for h in ('wamsp', 'twamsp', 'wamrtsp')],
                         [119, 120, 121])


if __name__ == '__main__':
    unittest.main()
