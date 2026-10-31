"""Q06 Stage A: disposable REGTEST-only 12-word BIP39 source adapter.

Not a persisted wallet, GUI onboarding, backup, payment signer or Q06 acceptance.
No legacy Keyring conversion, no mainnet and no secret-bearing diagnostics.
"""
from hashlib import sha256
import unicodedata

from mnemonic import Mnemonic

from .wsp_live import REGTEST_GENESIS, _pinned_source


PROFILE = "fusion-bip39-12-bip32-bip352-regtest-v1"
WORDLIST_SHA256 = "2f5eed53a4727b4bf8880d8f3f199efc90e58503646d9ff8eff3a2ed3b24dbda"


class Bip39TwelveError(ValueError):
    """Use fixed public error codes only, never include mnemonic material."""


def _english():
    reference = Mnemonic("english")
    canonical = ("\n".join(reference.wordlist) + "\n").encode("ascii")
    if len(reference.wordlist) != 2048 or sha256(canonical).hexdigest() != WORDLIST_SHA256:
        raise Bip39TwelveError("BIP39_12_WORDLIST_IDENTITY_DENIED")
    return reference


def normalize_phrase(phrase):
    if type(phrase) is not str or not 1 <= len(phrase) <= 1024:
        raise Bip39TwelveError("BIP39_12_PHRASE_INVALID")
    try:
        canonical = " ".join(unicodedata.normalize("NFKD", phrase).split())
        if len(canonical.split(" ")) != 12 or not _english().check(canonical):
            raise Bip39TwelveError("BIP39_12_PHRASE_INVALID")
    except (ValueError, UnicodeError):
        raise Bip39TwelveError("BIP39_12_PHRASE_INVALID") from None
    return canonical


def generate_phrase(*, authorized_disposable=False):
    if authorized_disposable is not True:
        raise Bip39TwelveError("BIP39_12_REGTEST_CONSENT_REQUIRED")
    return _english().generate(strength=128)


class Bip39Regtest12Keys:
    """Ephemeral seed adapter for pinned WSP. Not wallet storage/authority.

    BIP39 returns 64 bytes; use all bytes in native WSP BIP32 derivation.
    Explicit close is best-effort: CPython cannot guarantee RAM erasure.
    """
    __slots__ = ("_seed", "_closed")

    def __init__(self, phrase, *, source, passphrase="", profile=PROFILE,
                 authorized_disposable=False):
        if authorized_disposable is not True:
            raise Bip39TwelveError("BIP39_12_REGTEST_CONSENT_REQUIRED")
        if profile != PROFILE or type(profile) is not str:
            raise Bip39TwelveError("BIP39_12_PROFILE_DENIED")
        if type(passphrase) is not str or len(passphrase) > 1024:
            raise Bip39TwelveError("BIP39_12_PASSPHRASE_INVALID")
        _pinned_source(source)
        canonical = normalize_phrase(phrase)
        try:
            if len(unicodedata.normalize("NFKD", passphrase).encode("utf-8")) > 4096:
                raise ValueError
            seed = Mnemonic.to_seed(canonical, passphrase=passphrase)
        except (UnicodeError, ValueError):
            raise Bip39TwelveError("BIP39_12_PASSPHRASE_INVALID") from None
        if type(seed) is not bytes or len(seed) != 64:
            raise Bip39TwelveError("BIP39_12_SEED_LENGTH_DENIED")
        self._seed = bytearray(seed)
        self._closed = False

    def __repr__(self):
        return "<Bip39Regtest12Keys redacted>"

    def _key(self, account, role):
        if self._closed:
            raise Bip39TwelveError("BIP39_12_KEYS_CLOSED")
        if type(account) is not int or not 0 <= account < 16:
            raise Bip39TwelveError("BIP39_12_ACCOUNT_DENIED")
        if role not in ("scan", "spend"):
            raise Bip39TwelveError("BIP39_12_ROLE_DENIED")
        from wam_sp.hd import silent_key
        return silent_key(bytes(self._seed), account, role, coin_type=1)

    def scan_account(self, account=0, *, birthday=1):
        if type(birthday) is not int or not 1 <= birthday < 2**31:
            raise Bip39TwelveError("BIP39_12_BIRTHDAY_DENIED")
        from wam_sp.keystore import ScanAccount
        from wam_sp.core import pub
        return ScanAccount(account, self._key(account, "scan"),
                           pub(self._key(account, "spend")), birthday)

    def accounts(self):
        """Pinned WSP scanner/signer read interface, account zero only.

        No epoch rotation, labels, backup, or persistence until separate
        native anchored wallet profile qualification. No implicit key export.
        """
        return (self.scan_account(0),)

    def spend_secret(self, epoch):
        """Pinned WSP Signer compatibility for the single BIP39 account.

        This does not authorize a transaction: the Signer still enforces an
        independently approved proposal/PSBT and fee. Runtime is not wired.
        """
        if type(epoch) is not int or epoch != 0:
            raise Bip39TwelveError("BIP39_12_EPOCH_DENIED")
        return self._key(0, "spend")

    def public_metadata(self, account=0):
        a = self.scan_account(account)
        return {
            "profile": PROFILE, "chain": "regtest", "genesis": REGTEST_GENESIS,
            "mainnet_allowed": False, "production_qualified": False,
            "account": account, "account_id": a.account_id,
            "receive_code": a.payment_code(),
            "paths": {
                "scan": f"m/352'/1'/{account}'/1'/0",
                "spend": f"m/352'/1'/{account}'/0'/0",
            },
        }

    def close(self):
        if not self._closed:
            self._seed[:] = bytes(len(self._seed))
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
