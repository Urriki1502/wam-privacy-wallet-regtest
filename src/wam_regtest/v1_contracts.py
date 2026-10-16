"""Versioned experimental wallet boundaries; never infer ownership from a suffix."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from .wsp_live import REGTEST_GENESIS

BIP39_PROFILE = 'fusion-bip39-bip32-bip352-regtest-v1'
CORE_PROFILE = 'wam-core-sqlite-descriptor-regtest-v1'
RC1_PROFILE = 'wsp1-rc1-unchanged'


class WalletContractError(ValueError):
    pass


def require_regtest(chain, genesis):
    if type(chain) is not str or type(genesis) is not str or (chain, genesis) != ('regtest', REGTEST_GENESIS):
        raise WalletContractError('V1_NETWORK_BINDING_DENIED')


def derivation_paths(profile, account=0):
    if profile != BIP39_PROFILE or type(profile) is not str:
        raise WalletContractError('V1_DERIVATION_PROFILE_DENIED')
    if type(account) is not int or not 0 <= account < 16:
        raise WalletContractError('V1_ACCOUNT_LIMIT')
    return {'spend': f"m/352'/1'/{account}'/0'/0", 'scan': f"m/352'/1'/{account}'/1'/0"}


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
