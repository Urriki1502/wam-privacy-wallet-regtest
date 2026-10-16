"""Public Trezor vectors only. Failures never format mnemonic or seed values."""
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import unittest
from mnemonic import Mnemonic
from mnemonic.mnemonic import b58encode
from wam_sp.hd import ExtendedPrivate, HARDENED
from wam_regtest.bip39_wallet import Bip39RegtestKeys, MnemonicWalletError, generate_phrase, normalize_phrase
from wam_regtest.v1_contracts import BIP39_PROFILE, WalletContractError

SOURCE=Path(importlib.util.find_spec('wam_sp').origin).resolve().parents[2]
VECTORS=json.loads((Path(__file__).parent/'data/bip39_reference.json').read_text())['vectors']

class Bip39Compatibility(unittest.TestCase):
    def keys(self,phrase,**kw):
        return Bip39RegtestKeys(phrase,source=SOURCE,authorized_disposable=True,**kw)

    def test_all_16_published_12_and_24_word_seed_and_bip32_vectors(self):
        for i,v in enumerate(VECTORS):
            phrase=Mnemonic('english').to_mnemonic(bytes.fromhex(v['entropy']))
            with self.keys(phrase,passphrase='TREZOR') as keys:
                self.assertTrue(len(keys._seed)==64 and bytes(keys._seed).hex()==v['seed'],f'BIP39_VECTOR_{i}_DENIED')
                root=ExtendedPrivate.master(bytes(keys._seed))
                payload=bytes.fromhex('0488ade4')+bytes(9)+root.chain_code+b'\x00'+root.secret
                xprv=b58encode(payload+sha256(sha256(payload).digest()).digest()[:4])
                self.assertTrue(xprv==v['xprv'],f'BIP32_ROOT_VECTOR_{i}_DENIED')
                # Native explicit path independently checks the profile role mapping.
                expected=root.derive((352|HARDENED,1|HARDENED,HARDENED,1|HARDENED,0))
                account=keys.scan_account()
                self.assertTrue(account.scan_secret==int.from_bytes(expected.secret,'big'),f'BIP352_PATH_{i}_DENIED')
                with self.keys(phrase,passphrase='TREZOR') as restored:
                    self.assertTrue(keys.public_metadata()==restored.public_metadata(),f'RESTORE_{i}_DENIED')
                self.assertTrue(account.payment_code()==v['receive_code'],f'CROSS_OS_RECEIVE_CODE_{i}_DENIED')

    def test_nfkd_phrase_whitespace_and_optional_passphrase(self):
        phrase=Mnemonic('english').to_mnemonic(bytes(16))
        wide=''.join(chr(ord(c)+0xfee0) if 'a'<=c<='z' else '\u3000' for c in phrase)
        self.assertTrue(normalize_phrase('\n '+wide+' \t')==phrase,'NFKD_PHRASE_DENIED')
        with self.keys(wide,passphrase='caf\u00e9') as a,self.keys(phrase,passphrase='cafe\u0301') as b:
            self.assertTrue(a.public_metadata()==b.public_metadata(),'NFKD_PASSPHRASE_DENIED')
        with self.keys(phrase) as a,self.keys(phrase,passphrase='different-public-test-passphrase') as b:
            self.assertTrue(a.public_metadata()!=b.public_metadata(),'PASSPHRASE_MUST_CHANGE_WALLET')

    def test_csprng_generation_and_roundtrip(self):
        for count in (12,24):
            a=generate_phrase(count,authorized_disposable=True);b=generate_phrase(count,authorized_disposable=True)
            self.assertTrue(a!=b and len(a.split())==count and normalize_phrase(a)==a,'GENERATION_DENIED')
            with self.keys(a) as original,self.keys(a) as restored:
                self.assertTrue(original.public_metadata()==restored.public_metadata(),'GENERATED_RESTORE_DENIED')

    def test_invalid_input_redaction_and_explicit_profile_consent(self):
        phrase=Mnemonic('english').to_mnemonic(bytes(16))
        for bad in ['',None,b'not text',' '.join(['abandon']*12),' '.join(['notaword']*24),Mnemonic('english').to_mnemonic(bytes(24))]:
            with self.assertRaises(MnemonicWalletError):normalize_phrase(bad)
        for count in (True,13,15,18,21,None):
            with self.assertRaises(MnemonicWalletError):generate_phrase(count,authorized_disposable=True)
        with self.assertRaises(MnemonicWalletError):generate_phrase(12)
        with self.assertRaises(MnemonicWalletError):Bip39RegtestKeys(phrase,source=SOURCE)
        with self.assertRaises(WalletContractError):self.keys(phrase,profile='mainnet')
        for invalid_passphrase in (None,'\ud800'):
            with self.assertRaises(MnemonicWalletError):self.keys(phrase,passphrase=invalid_passphrase)
        keys=self.keys(phrase)
        self.assertTrue(repr(keys)=='<Bip39RegtestKeys redacted>','SECRET_REPR_DENIED')
        keys.close();self.assertTrue(len(keys._seed)==64 and not any(keys._seed),'CLOSE_SEED_BUFFER_DENIED')
        with self.assertRaises(MnemonicWalletError):keys.public_metadata()
        with self.keys(phrase) as keys:
            for account in (-1,True,16):
                with self.assertRaises(WalletContractError):keys.scan_account(account)
