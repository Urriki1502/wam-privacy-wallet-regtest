"""REGTEST v0.1.11 mining observations; independent treasury/maturity rules.

No keys, RPC writes, consensus replacement or authority to spend. Callers must
supply owned/authenticated Core observations. Confirmed is not spendable.
"""
from dataclasses import dataclass
import re
from .v1_contracts import require_regtest, rpc_atoms, CoreWalletObservation

COIN=100_000_000
REGTEST_HALVING_INTERVAL=150
TREASURY_LAST_HEIGHT=400_000
COINBASE_WALLET_DEPTH=101


def _integer(value,low,high):
    if type(value) is not int or not low<=value<=high:raise ValueError('MINER_INTEGER_DENIED')
    return value


def _script(value):
    if type(value) is not str or not 2<=len(value)<=20000 or len(value)%2 or not re.fullmatch('[0-9a-f]+',value):
        raise ValueError('MINER_SCRIPT_DENIED')
    return value


def treasury_atoms(subsidy,height):
    _integer(subsidy,0,50*COIN);_integer(height,0,1_000_000)
    return subsidy*5//100 if 1<=height<=TREASURY_LAST_HEIGHT else 0


@dataclass(frozen=True)
class RewardSplit:
    subsidy_atoms:int
    treasury_atoms:int
    miner_atoms:int
    fees_atoms:int

    @classmethod
    def regtest(cls,height,fees=0):
        _integer(height,1,1_000_000);_integer(fees,0,22_000_000*COIN)
        epoch=(height-1)//REGTEST_HALVING_INTERVAL
        subsidy=(50*COIN)>>epoch if epoch<33 else 0
        treasury=treasury_atoms(subsidy,height)
        return cls(subsidy,treasury,subsidy-treasury+fees,fees)


@dataclass(frozen=True)
class CoinbaseAudit:
    height:int
    subsidy_atoms:int
    treasury_paid_atoms:int
    miner_total_atoms:int
    owned_miner_atoms:int
    fees_atoms:int

    @classmethod
    def from_core(cls,*,chain,genesis,block,treasury_info,owned_address_infos,fees=0):
        """Audit a fully owned miner coinbase, not an arbitrary block finder.

        The caller supplies Core-confirmed owned scripts for every expected
        miner output. A partially owned coinbase must be refused rather than
        showing its unowned remainder as spendable in the miner account.
        Treasury is never a miner-owned script, including when fees exist.
        """
        require_regtest(chain,genesis)
        try:
            height=block['height'];split=RewardSplit.regtest(height,fees)
            if (type(block) is not dict or type(treasury_info) is not dict or treasury_info['percent']!=5 or type(treasury_info['percent']) is not int
                    or treasury_info['start_height']!=1 or treasury_info['last_height']!=TREASURY_LAST_HEIGHT):raise ValueError
            treasury=_script(treasury_info['script'])
            if type(owned_address_infos) is not list or not 1<=len(owned_address_infos)<=1000:raise ValueError
            owned=set()
            for info in owned_address_infos:
                if type(info) is not dict or info.get('ismine') is not True:raise ValueError
                owned.add(_script(info['scriptPubKey']))
            if treasury in owned:raise ValueError('MINER_TREASURY_ACCOUNT_OVERLAP')
            coinbase=block['tx'][0]
            if type(coinbase) is not dict or type(coinbase['vin']) is not list or len(coinbase['vin'])!=1 or type(coinbase['vin'][0]) is not dict or type(coinbase['vin'][0].get('coinbase')) is not str:raise ValueError
            outputs=coinbase['vout']
            if type(outputs) is not list or not 1<=len(outputs)<=1000:raise ValueError
            total=paid=mine=0;seen=set()
            for output in outputs:
                index=_integer(output['n'],0,1000)
                if index in seen:raise ValueError
                seen.add(index);script=_script(output['scriptPubKey']['hex']);amount=rpc_atoms(output['value']);total+=amount
                if script==treasury:paid+=amount
                elif script in owned:mine+=amount
                elif amount!=0:raise ValueError('MINER_UNOWNED_REWARD_OUTPUT_DENIED')
            # Only a complete wallet-ownership proof may authorize accounting:
            # treasury receives subsidy only; all miner subsidy plus ALL fees
            # must be assigned to Core-authenticated scripts in this wallet.
            if (paid!=split.treasury_atoms or total!=split.subsidy_atoms+fees
                    or mine!=split.miner_atoms):raise ValueError
            return cls(height,split.subsidy_atoms,paid,total-paid,mine,fees)
        except (ValueError,KeyError,TypeError,IndexError,OverflowError,AttributeError):
            raise ValueError('MINER_COINBASE_AUDIT_DENIED') from None


@dataclass(frozen=True)
class MiningWalletBalance:
    trusted_atoms:int
    pending_untrusted_atoms:int
    immature_atoms:int
    available_atoms:int
    available_utxos:int

    @classmethod
    def from_core(cls,*,chain,genesis,wallet_info,balances,unspent,txouts,treasury_script):
        """Use wallet safe/spendable UTXOs plus independent Core gettxout.

        Locked outputs excluded by Core are not fabricated from trusted balance.
        This initial read model has no Fusion reservation/custody authority.
        """
        observed=CoreWalletObservation.from_rpc(chain=chain,genesis=genesis,wallet_info=wallet_info,balances=balances)
        try:
            treasury=_script(treasury_script)
            if type(unspent) is not list or type(txouts) is not dict or len(unspent)>10000:raise ValueError
            available=count=0;seen=set()
            for u in unspent:
                txid=u['txid'];vout=_integer(u['vout'],0,100000)
                if type(txid) is not str or not re.fullmatch('[0-9a-f]{64}',txid) or (txid,vout) in seen:raise ValueError
                seen.add((txid,vout));out=txouts[(txid,vout)]
                script=_script(u['scriptPubKey'])
                if script==treasury or script!=out['scriptPubKey']['hex']:raise ValueError
                amount=rpc_atoms(u['amount']);depth=_integer(u['confirmations'],0,1_000_000)
                if amount!=rpc_atoms(out['value']) or depth!=_integer(out['confirmations'],0,1_000_000) or type(out['coinbase']) is not bool:raise ValueError
                if any(type(u.get(k)) is not bool for k in ('spendable','solvable','safe')):raise ValueError
                if u['spendable'] and u['solvable'] and u['safe'] and (not out['coinbase'] or depth>=COINBASE_WALLET_DEPTH):
                    available+=amount;count+=1
            if available>observed.trusted_atoms:raise ValueError
            return cls(observed.trusted_atoms,observed.pending_untrusted_atoms,observed.immature_atoms,available,count)
        except (KeyError,TypeError,ValueError,OverflowError):raise ValueError('MINER_BALANCE_RECONCILIATION_DENIED') from None
