"""Ephemeral experimental BIP39 keys; no RC1 backup reinterpretation or mainnet.

Trezor reference BIP39 -> ALL 64 seed bytes -> pinned native WSP BIP32/BIP352.
This engine is not yet a persistent wallet or an anchored signing coordinator.
"""
from hashlib import sha256
import unicodedata
from mnemonic import Mnemonic
from .v1_contracts import (
    BIP39_PROFILE, derivation_paths, derivation_profile_receipt,
    require_derivation_profile_receipt, metadata,
)
from .wsp_live import _pinned_source

WORDLIST_SHA256 = '2f5eed53a4727b4bf8880d8f3f199efc90e58503646d9ff8eff3a2ed3b24dbda'


class MnemonicWalletError(ValueError):
    pass


def _english():
    reference=Mnemonic('english')
    raw=('\n'.join(reference.wordlist)+'\n').encode('ascii')
    if len(reference.wordlist)!=2048 or sha256(raw).hexdigest()!=WORDLIST_SHA256:
        raise MnemonicWalletError('BIP39_WORDLIST_IDENTITY_DENIED')
    return reference


def normalize_phrase(phrase):
    if type(phrase) is not str or not 1 <= len(phrase) <= 2048:
        raise MnemonicWalletError('BIP39_PHRASE_INVALID')
    canonical=' '.join(unicodedata.normalize('NFKD',phrase).split())
    if len(canonical.split(' ')) not in (12,24) or not _english().check(canonical):
        raise MnemonicWalletError('BIP39_PHRASE_INVALID')
    return canonical


def generate_phrase(words=24, *, authorized_disposable=False):
    if authorized_disposable is not True:
        raise MnemonicWalletError('BIP39_DISPOSABLE_REGTEST_CONSENT_REQUIRED')
    if type(words) is not int or words not in (12,24):
        raise MnemonicWalletError('BIP39_WORD_COUNT_DENIED')
    # Reference implementation calls secrets.token_bytes(128/256 // 8).
    return _english().generate(strength=128 if words==12 else 256)


class Bip39RegtestKeys:
    """Secret repr suppressed; close is best effort, not guaranteed memory erase.

    No implicit persistence, rotation, password/anchor reset or signing entrypoint.
    The old 32-byte Keyring is deliberately never constructed from this seed.
    """
    __slots__=('_seed','_closed')

    def __init__(self, phrase, *, source, passphrase='', profile=BIP39_PROFILE,
                 authorized_disposable=False):
        if authorized_disposable is not True:
            raise MnemonicWalletError('BIP39_DISPOSABLE_REGTEST_CONSENT_REQUIRED')
        derivation_paths(profile)
        _pinned_source(source)
        if type(passphrase) is not str or len(passphrase)>1024:
            raise MnemonicWalletError('BIP39_PASSPHRASE_INVALID')
        canonical=normalize_phrase(phrase)
        try:
            if len(unicodedata.normalize('NFKD',passphrase).encode('utf8'))>4096:
                raise ValueError
            seed=Mnemonic.to_seed(canonical, passphrase=passphrase)
        except (UnicodeError,ValueError):
            raise MnemonicWalletError('BIP39_PASSPHRASE_INVALID') from None
        if len(seed)!=64:
            raise MnemonicWalletError('BIP39_SEED_LENGTH_DENIED')
        self._seed=bytearray(seed)
        self._closed=False

    def __repr__(self):
        return '<Bip39RegtestKeys redacted>'

    def _key(self, account, role):
        if self._closed:
            raise MnemonicWalletError('BIP39_KEYS_CLOSED')
        profile=derivation_profile_receipt(BIP39_PROFILE,account)
        require_derivation_profile_receipt(profile,account=account)
        if role not in ('scan','spend'):
            raise MnemonicWalletError('BIP39_ROLE_DENIED')
        # Coin type and role are derived ONLY from the same versioned K-02
        # contract advertised for restoration. No hidden mainnet fallback.
        from wam_sp.hd import silent_key
        return silent_key(bytes(self._seed), account, role,
                          coin_type=profile['coin_type'])

    def scan_account(self, account=0, *, birthday=1):
        from wam_sp.keystore import ScanAccount
        from wam_sp.core import pub
        return ScanAccount(account,self._key(account,'scan'),pub(self._key(account,'spend')),birthday)

    def public_metadata(self, account=0):
        a=self.scan_account(account)
        receipt=derivation_profile_receipt(BIP39_PROFILE,account)
        require_derivation_profile_receipt(receipt,account=account)
        return {**metadata(BIP39_PROFILE), 'account':account,
                'paths':derivation_paths(BIP39_PROFILE,account),
                'derivation_contract':receipt,'account_id':a.account_id,
                'receive_code':a.payment_code()}

    def require_public_metadata(self, observed, account=0):
        """K-02 fail closed if a GUI/recovery claim describes a different wallet.

        Same cryptographic keys can never authorize a different chain/profile,
        account, scan/spend role or payment code through mutable metadata.
        """
        expected=self.public_metadata(account)
        if (type(observed) is not dict or set(observed)!=set(expected)
                or any(type(observed[key]) is not type(expected[key])
                       for key in expected)
                or observed!=expected):
            raise MnemonicWalletError('BIP39_PUBLIC_PROFILE_IDENTITY_DENIED')
        require_derivation_profile_receipt(observed['derivation_contract'],
                                          account=account)
        return expected

    def close(self):
        self._seed[:]=bytes(len(self._seed))
        self._closed=True

    def __enter__(self):return self
    def __exit__(self,*_):self.close()
