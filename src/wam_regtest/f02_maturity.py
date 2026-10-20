"""F-02: Core-backed maturity witness for a FIRST disposable REGTEST coinbase.

Do not call on mainnet, imported wallets, merged accounts, or owner miner data.
This bounded proof consumes separate native Core gettxout and wallet balance
observations. It authorizes neither signing nor transaction broadcast.
"""
from dataclasses import dataclass
import re

from .mining_account import COIN, COINBASE_WALLET_DEPTH, MiningWalletBalance
from .v1_contracts import require_regtest, rpc_atoms


class CoinbaseMaturityRefusal(ValueError):
    """No secrets or mutable RPC output are ever included in this error."""


@dataclass(frozen=True)
class DisposableCoinbaseMaturity:
    depth: int
    first_coinbase_atoms: int
    immature_atoms: int
    available_atoms: int
    wallet_send_allowed_by_maturity: bool
    signer_allowed: bool = False
    broadcast_allowed: bool = False
    mainnet_allowed: bool = False

    @classmethod
    def from_core(cls, *, chain, genesis, height, origin_height, utxo,
                  wallet_balance, owned_script, miner_atoms):
        """The single newly-mined, unspent FIRST coinbase in isolated Core.

        Only depths 99/100/101 are covered. A positive 101 result is a
        *maturity observation*, not permission to initiate a real payment.
        """
        require_regtest(chain, genesis)
        try:
            if (type(height) is not int or type(origin_height) is not int
                    or origin_height!=1 or type(utxo) is not dict
                    or type(wallet_balance) is not MiningWalletBalance
                    or type(miner_atoms) is not int or miner_atoms!=4750000000
                    or type(owned_script) is not str
                    or not re.fullmatch('[0-9a-f]{4,20000}', owned_script)
                    or len(owned_script)%2):
                raise ValueError
            depth=height-origin_height+1
            if depth not in (99,100,101):
                raise ValueError
            if (type(utxo.get('confirmations')) is not int
                    or utxo['confirmations']!=depth
                    or utxo.get('coinbase') is not True
                    or type(utxo.get('scriptPubKey')) is not dict
                    or utxo['scriptPubKey'].get('hex')!=owned_script
                    or rpc_atoms(utxo['value'])!=miner_atoms):
                raise ValueError
            before=depth<COINBASE_WALLET_DEPTH
            if (wallet_balance.pending_untrusted_atoms!=0
                    or wallet_balance.immature_atoms!=(miner_atoms if before else 0)
                    or wallet_balance.trusted_atoms!=(0 if before else miner_atoms)
                    or wallet_balance.available_atoms!=(0 if before else miner_atoms)
                    or wallet_balance.available_utxos!=(0 if before else 1)):
                raise ValueError
            return cls(depth,miner_atoms,wallet_balance.immature_atoms,
                       wallet_balance.available_atoms,not before)
        except (KeyError,TypeError,ValueError,OverflowError,AttributeError):
            raise CoinbaseMaturityRefusal('F02_DISPOSABLE_COINBASE_MATURITY_DENIED') from None
