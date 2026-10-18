"""K-03 REGTEST-only, encrypted 64-byte BIP39/WSP signer keyring.

Never reinterpret legacy WSP Keyring 32-byte keys as BIP39. This adapter
implements the exact Keyring methods used by the pinned WSP scanner/Signer;
the authenticated native CheckpointVault retains its original lease, anchor,
SQLite, reservation and anti-rollback semantics on save/restore.

Only a 64-byte *derived seed*, NOT the mnemonic or mnemonic passphrase,
is stored under the existing scrypt/AES-GCM keys-purpose envelope, which is
itself sealed again inside the native-anchored recovery vault.
"""
from __future__ import annotations

import json
from .bip39_wallet import Bip39RegtestKeys
from .v1_contracts import (
    BIP39_PROFILE,derivation_profile_receipt,require_derivation_profile_receipt,
    REGTEST_COIN_TYPE,
)
from .wsp_live import REGTEST_GENESIS

FORMAT="wam-fusion-bip39-wsp-keyring/v1"
VERSION=4


class Bip39KeyringError(ValueError):
    pass


def _unique(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise Bip39KeyringError("BIP39_BACKUP_DUPLICATE_FIELD_DENIED")
        result[key]=value
    return result


class Bip39DurableKeyring:
    """Seed-scoped ScanAccount/Signer interface, no Keyring legacy fallback."""

    __slots__=("_seed","_closed","_account","_birthday")

    def __init__(self,seed,*,account=0,birthday=1):
        # All roles are derived from the same immutable versioned K-02 contract.
        contract=derivation_profile_receipt(BIP39_PROFILE,account)
        require_derivation_profile_receipt(contract,account=account)
        if (type(seed) is not bytes or len(seed)!=64
                or type(birthday) is not int or not 1<=birthday<2**31):
            raise Bip39KeyringError("BIP39_K03_SEED_SCOPE_DENIED")
        self._seed=bytearray(seed)
        self._account=account
        self._birthday=birthday
        self._closed=False

    @classmethod
    def from_phrase(cls,phrase,*,source,passphrase="",account=0,
                    authorized=False):
        if authorized is not True:
            raise Bip39KeyringError("BIP39_K03_EXPLICIT_CONSENT_REQUIRED")
        with Bip39RegtestKeys(phrase,source=source,passphrase=passphrase,
                              authorized_disposable=True) as keys:
            derivation_profile_receipt(BIP39_PROFILE,account)
            return cls(bytes(keys._seed),account=account)

    def __repr__(self):return "<Bip39DurableKeyring redacted>"

    def _key(self,role):
        if self._closed:
            raise Bip39KeyringError("BIP39_K03_LOCKED")
        if role not in ("scan","spend"):
            raise Bip39KeyringError("BIP39_K03_ROLE_DENIED")
        from wam_sp.hd import silent_key
        return silent_key(bytes(self._seed),self._account,role,
                          coin_type=REGTEST_COIN_TYPE)

    def accounts(self):
        from wam_sp.keystore import ScanAccount
        from wam_sp.core import pub
        return (ScanAccount(self._account,self._key("scan"),
                            pub(self._key("spend")),self._birthday),)

    def spend_secret(self,epoch):
        if type(epoch) is not int or epoch!=self._account:
            raise Bip39KeyringError("BIP39_K03_UNKNOWN_ACCOUNT")
        return self._key("spend")

    def backup(self,password):
        """Never leave seed plaintext in the native vault or Core RPC."""
        if self._closed:
            raise Bip39KeyringError("BIP39_K03_LOCKED")
        from wam_sp.keystore import seal
        record={
            "version":VERSION,
            "format":FORMAT,
            "profile":BIP39_PROFILE,
            "network":REGTEST_GENESIS,
            "account":self._account,
            "birthday":self._birthday,
            "derivation":derivation_profile_receipt(BIP39_PROFILE,self._account),
            "seed":self._seed.hex(),
            "mainnet_allowed":False,
            "legacy_wsp32_interpretable":False,
        }
        raw=json.dumps(record,sort_keys=True,separators=(",",":"),
                       ensure_ascii=True,allow_nan=False).encode("ascii")
        return seal(raw,password,b"keys")

    @classmethod
    def restore(cls,envelope,password):
        """Return only exact v4 REGTEST seed; no fallback to legacy format."""
        from wam_sp.keystore import unseal
        try:
            raw=unseal(envelope,password,b"keys")
            if not 400<=len(raw)<=4096:
                raise ValueError
            data=json.loads(raw.decode("ascii"),object_pairs_hook=_unique)
            if (type(data) is not dict
                    or set(data)!={
                        "version","format","profile","network","account",
                        "birthday","derivation","seed","mainnet_allowed",
                        "legacy_wsp32_interpretable"}
                    or type(data["version"]) is not int or data["version"]!=VERSION
                    or data["format"]!=FORMAT or data["profile"]!=BIP39_PROFILE
                    or data["network"]!=REGTEST_GENESIS
                    or data["mainnet_allowed"] is not False
                    or data["legacy_wsp32_interpretable"] is not False
                    or type(data["seed"]) is not str or len(data["seed"])!=128
                    or type(data["account"]) is not int
                    or type(data["birthday"]) is not int):
                raise ValueError
            require_derivation_profile_receipt(data["derivation"],
                                               account=data["account"])
            seed=bytes.fromhex(data["seed"])
            ring=cls(seed,account=data["account"],birthday=data["birthday"])
            # An encrypted backup must never silently change its original
            # BIP352 payment/scan/spend identity through profile drift.
            return ring
        except Exception:
            raise Bip39KeyringError("BIP39_K03_BACKUP_RESTORE_DENIED") from None

    def close(self):
        self._seed[:]=bytes(len(self._seed))
        self._closed=True

    def __enter__(self):return self
    def __exit__(self,*_):self.close()


def restore_keyring(envelope,password):
    """Dispatch only AFTER authenticated native recovery vault decrypt.

    Known legacy WSP versions 2/3 go to upstream Keyring.restore unchanged;
    BIP39 v4 is a distinct format. No 32->64 padding, truncation, hashing or
    automatic conversion, even if both formats yield a WSP receive code.
    """
    from wam_sp.keystore import Keyring,unseal
    try:
        raw=unseal(envelope,password,b"keys")
        if not 2<=len(raw)<=4096:raise ValueError
        data=json.loads(raw.decode("ascii"),object_pairs_hook=_unique)
        if type(data) is not dict or type(data.get("version")) is not int:
            raise ValueError
        version=data["version"]
        if version==VERSION:
            if data.get("format")!=FORMAT:
                raise ValueError
            return Bip39DurableKeyring.restore(envelope,password)
        if version in (2,3):
            return Keyring.restore(envelope,password)
        raise ValueError
    except Exception:
        raise Bip39KeyringError("BIP39_K03_KEY_FORMAT_DENIED") from None
