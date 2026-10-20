"""F-03: exact-atom Core mempool relay and observed fee policy.

REGTEST only. Reads authenticated Core observations; never estimates a
guaranteed inclusion time, chooses a transaction fee, or grants signing.
"""
from dataclasses import dataclass
from .v1_contracts import rpc_atoms

WAM_TARGET_BLOCK_SECONDS=120  # pinned upstream v0.1.11 wam-params.h
MAX_PAYMENT_FEE_ATOMS=1_000_000  # existing wallet GUI hard cap, 0.01 WAM


class FeePolicyRefusal(ValueError):
    pass


def _rate(value):
    # WAM Core RPC reports WAM/kilovbyte, not fee per transaction.
    atoms=rpc_atoms(value)
    if not 1<=atoms<=MAX_PAYMENT_FEE_ATOMS:
        raise FeePolicyRefusal('F03_CORE_FEE_RATE_DENIED')
    return atoms


def target_confirmation_seconds(depth):
    """A TARGET interval, not a confirmation deadline or ETA guarantee."""
    if type(depth) is not int or not 1<=depth<=100:
        raise FeePolicyRefusal('F03_CONFIRMATION_TARGET_DENIED')
    return depth*WAM_TARGET_BLOCK_SECONDS


@dataclass(frozen=True)
class CoreFeeWitness:
    relay_atoms_per_kvb: int
    mempool_floor_atoms_per_kvb: int
    effective_floor_atoms_per_kvb: int
    tx_vsize: int
    minimum_fee_atoms: int
    observed_fee_atoms: int
    observed_atoms_per_kvb_ceil: int
    fee_cap_atoms: int
    mempool_entry_relay_eligible: bool
    target_block_seconds: int = WAM_TARGET_BLOCK_SECONDS
    estimate_is_guarantee: bool = False
    signer_allowed: bool = False
    mainnet_allowed: bool = False

    @classmethod
    def from_core(cls, *, network_info, mempool_info, entry, actual_fee_atoms):
        try:
            if (type(network_info) is not dict or type(mempool_info) is not dict
                    or type(entry) is not dict
                    or type(entry.get('fees')) is not dict):
                raise ValueError
            relay=_rate(network_info['relayfee'])
            mempool=_rate(mempool_info['mempoolminfee'])
            size=entry['vsize']
            if type(size) is not int or not 1<=size<=400_000:
                raise ValueError
            fee=rpc_atoms(entry['fees']['base'])
            if (type(actual_fee_atoms) is not int
                    or not 0<actual_fee_atoms<=MAX_PAYMENT_FEE_ATOMS
                    or fee!=actual_fee_atoms):
                raise ValueError
            floor=max(relay,mempool)
            required=(floor*size+999)//1000
            if fee<required:
                raise ValueError
            return cls(relay,mempool,floor,size,required,fee,
                       (fee*1000+size-1)//size,MAX_PAYMENT_FEE_ATOMS,True)
        except (ValueError,KeyError,TypeError,OverflowError,AttributeError):
            raise FeePolicyRefusal('F03_CORE_FEE_POLICY_DENIED') from None


def optional_core_estimate(result):
    """Estimator is permitted to be unavailable on a short isolated chain.

    Do not substitute the configured fallback fee for a live market estimate.
    Return (available, rate_atoms_per_kvb | None); never report certainty.
    """
    if type(result) is not dict:
        raise FeePolicyRefusal('F03_ESTIMATE_REPLY_DENIED')
    if 'feerate' not in result or result['feerate'] is None:
        if ('errors' in result and
                (type(result['errors']) is not list
                 or any(type(x) is not str for x in result['errors']))):
            raise FeePolicyRefusal('F03_ESTIMATE_REPLY_DENIED')
        return False,None
    try:
        return True,_rate(result['feerate'])
    except (ValueError,TypeError):
        raise FeePolicyRefusal('F03_ESTIMATE_REPLY_DENIED') from None
