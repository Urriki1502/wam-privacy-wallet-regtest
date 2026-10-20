"""F-05 read-only status for an already-known disposable REGTEST transaction.

WSP confirmed history and Core's mempool are independent observations. Core
mempool presence NEVER implies a confirmed silent receive or spendability.
An absent transaction is UNKNOWN, not automatically dropped/conflicted.
No RPC writes, retries, unreserving or broadcast authority.
"""
from dataclasses import dataclass
import re
from .v1_contracts import require_regtest
from .wallet_read import HistoryRow


class TxHistoryRefusal(ValueError):
    pass


@dataclass(frozen=True)
class KnownTransactionState:
    classification: str
    confirmation_depth: int
    observed_in_mempool: bool
    verified_wsp_history: bool
    irreversible_reservation: bool
    automatic_rebroadcast_allowed: bool = False
    reservation_release_allowed: bool = False
    unconfirmed_silent_receive_detected: bool = False
    spend_authorized: bool = False
    mainnet_allowed: bool = False


def classify_known_transaction(*, chain, genesis, height, txid,
                               mempool_txids, history, reservation_state,
                               prior_confirmed=False, broadcast_submitted=False):
    """Classify only a tx already produced/approved in an owned test session.

    This is a snapshot status, not a reliable broadcast ledger or an RPC
    authority. Callers must authenticate Core and obtain a verified WSP scan.
    """
    try:
        require_regtest(chain, genesis)
        if (type(height) is not int or not 1<=height<=1_000_000
                or type(txid) is not str
                or re.fullmatch('[0-9a-f]{64}',txid) is None
                or type(mempool_txids) not in (list,tuple)
                or len(mempool_txids)>100000
                or any(type(x) is not str
                       or re.fullmatch('[0-9a-f]{64}',x) is None
                       for x in mempool_txids)
                or len(set(mempool_txids))!=len(mempool_txids)
                or type(history) not in (list,tuple)
                or len(history)>100000
                or type(reservation_state) is not str
                or reservation_state not in ('none','draft','signed','uncertain','broadcast')
                or type(prior_confirmed) is not bool
                or type(broadcast_submitted) is not bool):
            raise ValueError
        # Only this already-authorized, known outgoing TX is observable.
        if reservation_state=='none' and not broadcast_submitted and not prior_confirmed:
            raise ValueError
        relevant=[]
        for row in history:
            if (type(row) is not HistoryRow or type(row.txid) is not str
                    or re.fullmatch('[0-9a-f]{64}',row.txid) is None
                    or type(row.block_height) is not int
                    or type(row.confirmations) is not int
                    or type(row.credit_atoms) is not int
                    or type(row.debit_atoms) is not int
                    or min(row.credit_atoms,row.debit_atoms)<0):
                raise ValueError
            if row.txid==txid:
                if (not 1<=row.block_height<=height
                        or row.confirmations!=height-row.block_height+1
                        or row.confirmations<1):
                    raise ValueError
                relevant.append(row)
        if len(relevant)>1:
            # Multiple WSP account history rows must be reconciled
            # independently; never silently deduplicate a payment.
            raise ValueError
        in_mempool=txid in mempool_txids
        if relevant and in_mempool:
            raise ValueError
        if relevant:
            status='confirmed'
            depth=relevant[0].confirmations
        elif reservation_state=='uncertain':
            status=('uncertain_mempool_observed' if in_mempool
                    else 'uncertain_not_observed')
            depth=0
        elif prior_confirmed:
            status=('reorged_mempool_observed' if in_mempool
                    else 'reorged_not_observed')
            depth=0
        elif in_mempool:
            status='mempool_observed'
            depth=0
        elif reservation_state=='draft':
            status='draft'
            depth=0
        elif reservation_state=='signed':
            status='signed_not_broadcast'
            depth=0
        else:
            status='submitted_not_observed'
            depth=0
        irreversible=reservation_state in ('signed','uncertain','broadcast')
        return KnownTransactionState(status,depth,in_mempool,bool(relevant),irreversible)
    except (ValueError,TypeError,KeyError,OverflowError,AttributeError):
        raise TxHistoryRefusal('F05_TRANSACTION_OBSERVATION_DENIED') from None
