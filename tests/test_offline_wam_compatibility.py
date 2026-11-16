"""Public-vector lab only. No production derivation, profile IO or network."""
from hashlib import pbkdf2_hmac, sha512
import hmac
import unittest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
# Install the existing WSP provenance guard before importing pinned modules.
from wam_regtest import bip39_12
from wam_sp.hd import ExtendedPrivate, HARDENED, silent_key
from wam_sp.core import pub, hash160, address, decode_address
from wam_sp.codec import encode

N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
COIN_TYPE = 5718349  # SLIP0044 and exact Core wam-params.h; offline only.
PHRASE = 'abandon '*11 + 'about'  # Published BIP84 test mnemonic, not owner data.


def independent_public(seed, path):
    """Test reference: stdlib HMAC/scalar addition + OpenSSL EC, not WSP CKD."""
    digest=hmac.new(b'Bitcoin seed',seed,sha512).digest()
    scalar=int.from_bytes(digest[:32],'big');chain=digest[32:]
    assert 0 < scalar < N
    for index in path:
        public=ec.derive_private_key(scalar,ec.SECP256K1()).public_key().public_bytes(
            Encoding.X962,PublicFormat.CompressedPoint)
        data=(b'\0'+scalar.to_bytes(32,'big') if index&HARDENED else public)
        digest=hmac.new(chain,data+index.to_bytes(4,'big'),sha512).digest()
        tweak=int.from_bytes(digest[:32],'big');assert tweak < N
        scalar=(scalar+tweak)%N;assert scalar
        chain=digest[32:]
    return ec.derive_private_key(scalar,ec.SECP256K1()).public_key().public_bytes(
        Encoding.X962,PublicFormat.CompressedPoint)


class OfflineWamCompatibility(unittest.TestCase):
    def seed(self):
        # Published ASCII vector. NFKD behavior remains covered by Q06 tests.
        return pbkdf2_hmac('sha512',PHRASE.encode(),b'mnemonic',2048)

    def test_published_bip84_public_key_and_address_anchor_reference(self):
        path=(84|HARDENED,0|HARDENED,0|HARDENED,0,0)
        key=independent_public(self.seed(),path)
        self.assertEqual(key.hex(),'0330d54fd0dd420a6e5f8d3624f5f3482cae350f79d5f0753bf5beef9c2d91af3c')
        self.assertEqual(encode('bc',hash160(key),bech32m=False),
                         'bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu')

    def test_wam_and_test_coin_paths_differ_and_match_independent_engine(self):
        seed=self.seed();root=ExtendedPrivate.master(seed);publics=[]
        for coin in (1,COIN_TYPE):
            for purpose in (84,86):
                path=(purpose|HARDENED,coin|HARDENED,HARDENED,0,0)
                actual=root.derive(path).public
                self.assertEqual(actual,independent_public(seed,path))
                publics.append(actual)
            for role,branch in [('scan',1),('spend',0)]:
                path=(352|HARDENED,coin|HARDENED,HARDENED,branch|HARDENED,0)
                actual=pub(silent_key(seed,0,role,coin_type=coin))
                self.assertEqual(actual,independent_public(seed,path))
                publics.append(actual)
        self.assertEqual(len(set(publics)),8)
        self.assertEqual(bip39_12.PROFILE,'fusion-bip39-12-bip32-bip352-regtest-v1')

    def test_proposed_sp_namespaces_full_decode_long_payload_and_exact_network(self):
        # Globally known public fixtures. This does not publish operational HRPs.
        for hrp,length in [('wamsp',119),('twamsp',120),('wamrtsp',121)]:
            code=address(7,pub(11),hrp=hrp)
            self.assertEqual(len(code),length)
            self.assertEqual(tuple(k.format() for k in decode_address(code,hrp)),(pub(7),pub(11)))
            self.assertEqual(tuple(k.format() for k in decode_address(code.upper(),hrp)),(pub(7),pub(11)))
            for other in ('wam','twam','wamrt','wamsp','twamsp','wamrtsp'):
                if other!=hrp:
                    with self.assertRaises(ValueError):decode_address(code,other)
            for invalid in [code[:5].upper()+code[5:],code[:-1]+('q' if code[-1]!='q' else 'p'),
                            encode(hrp,pub(7)+pub(11),bech32m=False),
                            encode(hrp,pub(7)+pub(11),version=1),
                            encode(hrp,b'\0'*66),encode(hrp,pub(7)),
                            encode(hrp,pub(7)+pub(11)+b'\0')]:
                with self.assertRaises(ValueError):decode_address(invalid,hrp)


if __name__=='__main__':unittest.main()
