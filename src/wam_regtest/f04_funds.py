"""F-04: native Core mining-account balance buckets, not a WSP balance.

The caller supplies authenticated Core RPC outputs from a disposable REGTEST
wallet. Core locks, WSP irreversible reservations and off-chain pool credits
are DIFFERENT sources of truth and cannot be inferred by subtraction.
No signing, unlock RPC or external node access is authorized here.
"""
from dataclasses import dataclass
import re

from .mining_account import MiningWalletBalance, COINBASE_WALLET_DEPTH
from .v1_contracts import require_regtest, rpc_atoms


class CoreFundsRefusal(ValueError):
    pass


def _outpoint(out):
    if (type(out) is not dict or type(out.get('txid')) is not str
            or re.fullmatch('[0-9a-f]{64}',out['txid']) is None
            or type(out.get('vout')) is not int
            or not 0<=out['vout']<2**32):
        raise ValueError
    return out['txid'],out['vout']


@dataclass(frozen=True)
class CoreFundsBuckets:
    available_atoms: int
    locked_core_atoms: int
    immature_atoms: int
    pending_untrusted_atoms: int
    trusted_atoms: int
    unattributed_trusted_atoms: int
    core_locked_utxos: int
    # Neither Core trust nor Core coin-locks are WSP spend authorization.
    wsp_reserved_atoms_known: bool = False
    pool_owed_atoms_known: bool = False
    signer_allowed: bool = False
    mainnet_allowed: bool = False

    @classmethod
    def from_core(cls, *, chain, genesis, balance, locked_outpoints,
                  locked_txouts, unlocked_outpoints, owned_script,
                  treasury_script):
        require_regtest(chain, genesis)
        try:
            if (type(balance) is not MiningWalletBalance or
                    type(locked_outpoints) is not list or
                    type(locked_txouts) is not dict or
                    type(unlocked_outpoints) is not list or
                    len(locked_outpoints)>512 or len(unlocked_outpoints)>512 or
                    type(owned_script) is not str or
                    not re.fullmatch('[0-9a-f]{4,20000}',owned_script) or
                    len(owned_script)%2 or type(treasury_script) is not str or
                    not re.fullmatch('[0-9a-f]{4,20000}',treasury_script) or
                    len(treasury_script)%2 or owned_script==treasury_script):
                raise ValueError
            if any(type(x) is not int or x<0 for x in
                   (balance.trusted_atoms,balance.available_atoms,
                    balance.immature_atoms,balance.pending_untrusted_atoms,
                    balance.available_utxos)):
                raise ValueError
            unlocked={_outpoint(x) for x in unlocked_outpoints}
            if len(unlocked)!=len(unlocked_outpoints):
                raise ValueError
            seen=set()
            locked=0
            for row in locked_outpoints:
                point=_outpoint(row)
                if point in seen or point in unlocked:
                    raise ValueError
                seen.add(point)
                utxo=locked_txouts[point]
                if (type(utxo) is not dict or
                        type(utxo.get('scriptPubKey')) is not dict or
                        utxo['scriptPubKey'].get('hex')!=owned_script or
                        utxo['scriptPubKey'].get('hex')==treasury_script or
                        type(utxo.get('coinbase')) is not bool or
                        type(utxo.get('confirmations')) is not int or
                        utxo['confirmations']<0 or
                        (utxo['coinbase'] and
                         utxo['confirmations']<COINBASE_WALLET_DEPTH)):
                    raise ValueError
                locked+=rpc_atoms(utxo['value'])
            if set(locked_txouts)!=seen:
                raise ValueError
            unattributed=balance.trusted_atoms-balance.available_atoms-locked
            if unattributed<0:
                raise ValueError
            return cls(balance.available_atoms,locked,balance.immature_atoms,
                       balance.pending_untrusted_atoms,balance.trusted_atoms,
                       unattributed,len(seen))
        except (KeyError,ValueError,TypeError,OverflowError,AttributeError):
            raise CoreFundsRefusal('F04_CORE_FUNDS_RECONCILIATION_DENIED') from None
