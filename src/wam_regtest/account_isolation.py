"""Issue #45 K-06: immutable, public-only Core/WSP account identity registry.

This is NOT a credential registry: it never holds Core RPC auth, WSP scan or
spend secrets, BIP39 seeds, descriptor private keys, wallet.dat or SQLite DBs.
It proves *account separation*, not possession of Core private keys. Wallet
ownership is proved separately by signed owned Core, native vault and root
witness/Keychain/Credential Manager; no public metadata grants spending.

A Core descriptor wallet, a legacy 32-byte WSP keyring and BIP39 WSP account
are THREE distinct authorities. Neither Core .dat nor WSP/BIP39 can recreate
keys of the other type, and balances/history must never be silently combined.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from .v1_contracts import (
    CORE_PROFILE, RC1_PROFILE, BIP39_PROFILE, require_regtest,
    core_descriptor_identity,
)
from .wsp_live import REGTEST_GENESIS

ACCOUNT_ID = re.compile(r"[0-9a-f]{64}\Z")
WALLET_ID = re.compile(r"[0-9a-f]{32}\Z")
CORE_WALLET_NAME = re.compile(r"[a-zA-Z0-9_-]{1,48}\Z")
MAX_CORE_WALLETS = 32
MAX_WSP_WALLETS = 32
MAX_WSP_ACCOUNTS = 16


class AccountIsolationError(ValueError):
    pass


def _fail(reason):
    raise AccountIsolationError(reason)


@dataclass(frozen=True)
class CoreAccount:
    """Only the *public* identity from Core's listdescriptors(false)."""

    name: str
    descriptor_identity: str
    descriptor_set: frozenset[tuple[str,bool]]
    network: str = "regtest"
    genesis: str = REGTEST_GENESIS
    profile: str = CORE_PROFILE
    authority: str = "core-native-descriptor"
    fusion_signer_allowed: bool = False

    @classmethod
    def from_core_public(cls, *, name, chain, genesis, wallet_info, descriptors):
        from .core_sqlite_import import _public_descriptor_set
        try:
            require_regtest(chain,genesis)
            if (type(name) is not str or not CORE_WALLET_NAME.fullmatch(name)
                    or type(wallet_info) is not dict
                    or wallet_info.get("format")!="sqlite"
                    or wallet_info.get("descriptors") is not True
                    or type(wallet_info.get("private_keys_enabled")) is not bool):
                raise ValueError
            public=_public_descriptor_set(descriptors)
            fingerprint=core_descriptor_identity(descriptors)
            if not public or not ACCOUNT_ID.fullmatch(fingerprint):
                raise ValueError
            return cls(name,fingerprint,public)
        except Exception:
            _fail("K06_CORE_PUBLIC_ACCOUNT_DENIED")


@dataclass(frozen=True)
class WspAccount:
    """WSP account identity, never a portable BIP39/Core ownership claim."""

    wallet_id: str
    account_id: str
    epoch: int
    receive_code: str
    profile: str
    network: str = "regtest"
    genesis: str = REGTEST_GENESIS
    authority: str = "wsp-bip352"
    core_wallet_spend_allowed: bool = False

    @classmethod
    def from_native_scan(cls, wallet_id, profile, account):
        from wam_sp.keystore import ScanAccount
        try:
            if (type(wallet_id) is not str or not WALLET_ID.fullmatch(wallet_id)
                    or type(profile) is not str or profile not in
                    (RC1_PROFILE,BIP39_PROFILE)
                    or type(account) is not ScanAccount
                    or type(account.epoch) is not int
                    or not 0<=account.epoch<MAX_WSP_ACCOUNTS
                    or type(account.account_id) is not str
                    or not ACCOUNT_ID.fullmatch(account.account_id)):
                raise ValueError
            code=account.payment_code()
            if (type(code) is not str or not code.startswith("wamrtsp1")
                    or not 75<=len(code)<=160):
                raise ValueError
            return cls(wallet_id,account.account_id,account.epoch,code,profile)
        except Exception:
            _fail("K06_WSP_PUBLIC_ACCOUNT_DENIED")


@dataclass(frozen=True)
class AccountRegistry:
    """One bounded immutable view, keyed by NATIVE AUTHORITY not display name.

    Duplicates across different named Core wallets, subsets/partial descriptor
    overlap, WSP account-clones under different vault IDs and mismatched WSP
    wallet/profile bindings are rejected. No external persistence: the trusted
    inputs are re-attested on every explicit unlock/reopen; this index does not
    replace native custody, Core's wallet registry, or a safe multi-writer CAS.
    """
    core: tuple[CoreAccount,...] = ()
    wsp: tuple[WspAccount,...] = ()

    def __post_init__(self):
        if (type(self.core) is not tuple or type(self.wsp) is not tuple
                or len(self.core)>MAX_CORE_WALLETS
                or len(self.wsp)>MAX_WSP_WALLETS*MAX_WSP_ACCOUNTS):
            _fail("K06_REGISTRY_SIZE_DENIED")
        names=set()
        identities=set()
        descriptors=set()
        for a in self.core:
            if (type(a) is not CoreAccount or a.network!="regtest"
                    or a.genesis!=REGTEST_GENESIS or a.profile!=CORE_PROFILE
                    or a.authority!="core-native-descriptor"
                    or a.fusion_signer_allowed is not False
                    or type(a.name) is not str
                    or not CORE_WALLET_NAME.fullmatch(a.name)
                    or type(a.descriptor_set) is not frozenset
                    or not a.descriptor_set
                    or type(a.descriptor_identity) is not str
                    or not ACCOUNT_ID.fullmatch(a.descriptor_identity)):
                _fail("K06_CORE_REGISTRY_SCOPE_DENIED")
            # Immutable direct record construction must not bypass the
            # descriptor identity attested by Core.listdescriptors(false).
            digest=sha256(json.dumps(sorted(a.descriptor_set),
                     separators=(",",":")).encode("ascii")).hexdigest()
            if digest!=a.descriptor_identity:
                _fail("K06_CORE_DESCRIPTOR_IDENTITY_DENIED")
            if (a.name in names or a.descriptor_identity in identities
                    or not descriptors.isdisjoint(a.descriptor_set)):
                _fail("K06_CORE_DESCRIPTOR_OVERLAP_DENIED")
            names.add(a.name)
            identities.add(a.descriptor_identity)
            descriptors.update(a.descriptor_set)
        wsp_ids=set()
        wallet_epochs=set()
        wallet_profiles={}
        wallet_counts={}
        for a in self.wsp:
            if (type(a) is not WspAccount or a.network!="regtest"
                    or a.genesis!=REGTEST_GENESIS or a.authority!="wsp-bip352"
                    or a.core_wallet_spend_allowed is not False
                    or type(a.wallet_id) is not str
                    or not WALLET_ID.fullmatch(a.wallet_id)
                    or type(a.account_id) is not str
                    or not ACCOUNT_ID.fullmatch(a.account_id)
                    or type(a.epoch) is not int
                    or not 0<=a.epoch<MAX_WSP_ACCOUNTS
                    or type(a.profile) is not str
                    or a.profile not in (RC1_PROFILE,BIP39_PROFILE)
                    or type(a.receive_code) is not str
                    or not a.receive_code.startswith("wamrtsp1")
                    or not 75<=len(a.receive_code)<=160):
                _fail("K06_WSP_REGISTRY_SCOPE_DENIED")
            if (a.account_id in wsp_ids
                    or (a.wallet_id,a.epoch) in wallet_epochs):
                _fail("K06_WSP_DUPLICATE_OWNER_DENIED")
            current=wallet_profiles.setdefault(a.wallet_id,a.profile)
            if current!=a.profile:
                _fail("K06_WSP_PROFILE_COLLISION_DENIED")
            wallet_counts[a.wallet_id]=wallet_counts.get(a.wallet_id,0)+1
            if wallet_counts[a.wallet_id]>MAX_WSP_ACCOUNTS:
                _fail("K06_WSP_WALLET_ACCOUNT_LIMIT")
            wsp_ids.add(a.account_id)
            wallet_epochs.add((a.wallet_id,a.epoch))
        if len(wallet_profiles)>MAX_WSP_WALLETS:
            _fail("K06_WSP_WALLET_LIMIT")

    def require_authority(self, *, kind, wallet_id, account_id=None,
                          operation="read"):
        """A public registry NEVER grants Core signing, WSP derivation or send.

        This is a read/route check only. Real sign authority remains with
        authenticated native Keyring + anchor lease and exact-intent approvals.
        """
        if (type(kind) is not str or type(wallet_id) is not str
                or type(operation) is not str or
                operation not in ("read","scan")):
            _fail("K06_CROSS_AUTHORITY_DENIED")
        if kind=="core":
            if account_id is not None:
                _fail("K06_CORE_WSP_CROSS_AUTHORITY_DENIED")
            match=[x for x in self.core if x.name==wallet_id]
            if len(match)!=1 or operation!="read":
                _fail("K06_CORE_ACCOUNT_ROUTE_DENIED")
            return match[0]
        if kind=="wsp":
            if type(account_id) is not str:
                _fail("K06_WSP_ACCOUNT_ROUTE_DENIED")
            match=[x for x in self.wsp if
                   x.wallet_id==wallet_id and x.account_id==account_id]
            if len(match)!=1:
                _fail("K06_WSP_ACCOUNT_ROUTE_DENIED")
            return match[0]
        _fail("K06_UNKNOWN_ACCOUNT_KIND_DENIED")

    def public_summary(self):
        """No amounts, addresses, Core wallet.dat, secrets or combined totals."""
        return {"chain":"regtest","core_wallet_count":len(self.core),
                "wsp_wallet_count":len({x.wallet_id for x in self.wsp}),
                "wsp_account_count":len(self.wsp),
                "balances_aggregated":False,
                "cross_account_signing":False,
                "mainnet_allowed":False}


def require_native_wsp_accounts(ring,scanner,wallet_id):
    """After native vault unlock: prove the scanner and real WSP signer agree.

    Reject fabricated ring types, duplicate epochs/IDs, swap of scan/spend
    keys or stolen public metadata before enabling managed Send/Sign. This
    function alone is NOT custody auth; caller must have proven native anchor,
    original encrypted checkpoint and authenticated owned Core first.
    """
    from wam_sp.keystore import Keyring
    from wam_sp.core import pub
    from .bip39_durable import Bip39DurableKeyring
    try:
        if type(ring) not in (Keyring,Bip39DurableKeyring):
            raise ValueError
        records=ring.accounts()
        scanned=scanner.accounts
        if (type(records) is not tuple or type(scanned) is not tuple
                or records!=scanned
                or not 1<=len(records)<=MAX_WSP_ACCOUNTS):
            raise ValueError
        profile=(BIP39_PROFILE if type(ring) is Bip39DurableKeyring
                 else RC1_PROFILE)
        found=[]
        for a in records:
            item=WspAccount.from_native_scan(wallet_id,profile,a)
            secret=ring.spend_secret(a.epoch)
            if (type(secret) is not int or
                    pub(secret)!=a.spend_public):
                raise ValueError
            found.append(item)
        return AccountRegistry(wsp=tuple(found))
    except Exception:
        _fail("K06_NATIVE_WSP_SIGNER_BINDING_DENIED")
