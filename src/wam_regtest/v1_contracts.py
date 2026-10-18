"""Versioned experimental wallet boundaries; never infer ownership from a suffix."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from .wsp_live import REGTEST_GENESIS

BIP39_PROFILE = 'fusion-bip39-bip32-bip352-regtest-v1'
CORE_PROFILE = 'wam-core-sqlite-descriptor-regtest-v1'
RC1_PROFILE = 'wsp1-rc1-unchanged'

# K-02: one immutable *experimental REGTEST* derivation contract. These are
# BIP352's purpose, Bitcoin testnet/regtest coin type and native WSP role
# indices, NOT a DEV-approved WAM mainnet SLIP-44/derivation decision.
DERIVATION_SCHEMA = 'wam-fusion-regtest-bip352-derivation/v1'
DERIVATION_VERSION = 1
REGTEST_BIP352_PURPOSE = 352
REGTEST_COIN_TYPE = 1
REGTEST_ACCOUNT_LIMIT = 16
REGTEST_SPEND_ROLE = 0
REGTEST_SCAN_ROLE = 1


class WalletContractError(ValueError):
    pass


def require_regtest(chain, genesis):
    if type(chain) is not str or type(genesis) is not str or (chain, genesis) != ('regtest', REGTEST_GENESIS):
        raise WalletContractError('V1_NETWORK_BINDING_DENIED')


def derivation_paths(profile, account=0):
    if type(profile) is not str or profile != BIP39_PROFILE:
        raise WalletContractError('V1_DERIVATION_PROFILE_DENIED')
    if type(account) is not int or not 0 <= account < REGTEST_ACCOUNT_LIMIT:
        raise WalletContractError('V1_ACCOUNT_LIMIT')
    path = lambda role: (
        f"m/{REGTEST_BIP352_PURPOSE}'/{REGTEST_COIN_TYPE}'/"
        f"{account}'/{role}'/0")
    return {'spend': path(REGTEST_SPEND_ROLE),
            'scan': path(REGTEST_SCAN_ROLE)}


def derivation_profile_receipt(profile, account=0):
    """K-02 public REGTEST mapping, including a canonical drift-detection SHA.

    SHA is an identity checksum, NOT a trust anchor or authorization to
    reconstruct a wallet. Caller must still verify the seed-derived identity,
    immutable native custody, chain and profile before any K-03 wallet use.
    """
    paths=derivation_paths(profile,account)
    record={
        'schema': DERIVATION_SCHEMA,
        'version': DERIVATION_VERSION,
        'profile': BIP39_PROFILE,
        'chain': 'regtest',
        'genesis': REGTEST_GENESIS,
        'purpose': REGTEST_BIP352_PURPOSE,
        'coin_type': REGTEST_COIN_TYPE,
        'account': account,
        'account_limit_exclusive': REGTEST_ACCOUNT_LIMIT,
        'spend_role': REGTEST_SPEND_ROLE,
        'scan_role': REGTEST_SCAN_ROLE,
        'paths': paths,
        'legacy_wsp32_interpretable': False,
        'mainnet_allowed': False,
        'production_qualified': False,
    }
    raw=json.dumps(record,sort_keys=True,separators=(',',':'),
                   ensure_ascii=True,allow_nan=False).encode('ascii')
    return {**record,'fingerprint_sha256':sha256(raw).hexdigest()}


def require_derivation_profile_receipt(value, *, account=0):
    """Never silently fall back to another coin type, role or account index."""
    expected=derivation_profile_receipt(BIP39_PROFILE,account)
    if (type(value) is not dict or set(value)!=set(expected)
            or any(type(value[key]) is not type(expected[key])
                   for key in expected)
            or type(value.get('paths')) is not dict
            or set(value['paths'])!=set(expected['paths'])
            or any(type(value['paths'][role]) is not str
                   for role in expected['paths'])
            or value!=expected):
        # Python considers True == 1 and False == 0. A derived wallet
        # identity MUST NOT accept boolean-as-integer/account/coin aliases.
        raise WalletContractError('V1_DERIVATION_RECEIPT_DENIED')
    return expected


def metadata(profile):
    if type(profile) is not str or profile not in (BIP39_PROFILE, CORE_PROFILE, RC1_PROFILE):
        raise WalletContractError('V1_ACCOUNT_PROFILE_DENIED')
    return {'schema': 1, 'profile': profile, 'chain': 'regtest', 'genesis': REGTEST_GENESIS,
            'production_qualified': False, 'mainnet_allowed': False}


def rpc_atoms(value):
    # Never use float arithmetic or accept booleans/nonfinite/unbounded amounts.
    if type(value) not in (int, float, str, Decimal):
        raise WalletContractError('V1_CORE_AMOUNT_DENIED')
    try:
        amount = Decimal(str(value)) * 100_000_000
        if not amount.is_finite() or amount != amount.to_integral_value() or not 0 <= amount <= 22_000_000 * 100_000_000:
            raise ValueError
        return int(amount)
    except (ValueError, InvalidOperation):
        raise WalletContractError('V1_CORE_AMOUNT_DENIED') from None


@dataclass(frozen=True)
class CoreWalletObservation:
    """Core's trusted bucket is NOT asserted to be confirmed/spendable UTXOs.

    It may include trusted unconfirmed change. Reserved/spendable/confirmed
    projections require separate verified UTXO/lock and height observations.
    """
    trusted_atoms: int
    pending_untrusted_atoms: int
    immature_atoms: int
    private_keys_enabled: bool

    @classmethod
    def from_rpc(cls, *, chain, genesis, wallet_info, balances):
        require_regtest(chain, genesis)
        try:
            if (type(wallet_info) is not dict or wallet_info.get('format') != 'sqlite'
                    or wallet_info.get('descriptors') is not True
                    or type(wallet_info.get('private_keys_enabled')) is not bool):
                raise ValueError
            mine = balances['mine']
            return cls(rpc_atoms(mine['trusted']), rpc_atoms(mine['untrusted_pending']),
                       rpc_atoms(mine['immature']), wallet_info['private_keys_enabled'])
        except (KeyError, TypeError, ValueError):
            raise WalletContractError('V1_CORE_WALLET_COMPATIBILITY_DENIED') from None


def core_descriptor_identity(reply):
    """Call only with pinned Core listdescriptors false; never serialize reply.

    Ignore mutable timestamp/range/next_index and the Core wallet's local name.
    This account-set identity is for duplicate detection, not network attestation.
    """
    from hashlib import sha256
    import json
    try:
        descriptors=reply['descriptors']
        if type(descriptors) is not list or not 1 <= len(descriptors) <= 1000:
            raise ValueError
        records=[]
        for d in descriptors:
            if (type(d) is not dict or type(d.get('desc')) is not str
                    or not 1 <= len(d['desc']) <= 10000 or type(d.get('internal')) is not bool):
                raise ValueError
            records.append((d['desc'],d['internal']))
        return sha256(json.dumps(sorted(set(records)),separators=(',',':')).encode()).hexdigest()
    except (KeyError,TypeError,ValueError):
        raise WalletContractError('V1_CORE_DESCRIPTOR_IDENTITY_DENIED') from None


def require_unique_core_identity(identity, existing):
    import re
    if type(identity) is not str or not re.fullmatch('[0-9a-f]{64}',identity):
        raise WalletContractError('V1_CORE_DESCRIPTOR_IDENTITY_DENIED')
    if identity in existing:
        raise WalletContractError('V1_DUPLICATE_CORE_ACCOUNT_DENIED')
