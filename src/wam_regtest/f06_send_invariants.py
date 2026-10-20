"""F-06 reservation/PSBT exact-intent witness for the disposable REGTEST wallet.

Only locally held immutable proposal/review and verified private SQLite state.
This module never signs, changes a reservation, broadcasts, or releases inputs.
"""
from hashlib import sha256
import hmac
import re


class SendInvariantRefusal(ValueError):
    pass


def _outpoint(txid, vout):
    if (type(txid) is not str or not re.fullmatch('[0-9a-f]{64}', txid)
            or type(vout) is not int or not 0<=vout<2**32):
        raise ValueError
    return txid,vout


def require_exact_send_reservation(*, prepared, review, rows,
                                   mempool_spends, expected_state,
                                   signed_psbt=None):
    """Refuse if prepared inputs, anchored locks and exact review diverge.

    The calling coordinator invokes this under its owned session lock,
    immediately before the irreversible sign and pre-RPC broadcast stages.
    A failed check cannot be interpreted as permission to retry or unlock.
    """
    try:
        from wam_sp.psbt import PSBT
        if (type(expected_state) is not str
                or expected_state not in ('draft','signed')
                or type(rows) not in (tuple,list) or not 1<=len(rows)<=10000
                or type(mempool_spends) not in (tuple,list)
                or len(mempool_spends)>10000):
            raise ValueError
        proposal=prepared.proposal
        coins=proposal.coins
        intents=proposal.intents
        token=proposal.token
        if (type(prepared.psbt) is not bytes
                or not 1<=len(prepared.psbt)<=800000
                or type(token) is not str or not re.fullmatch('[0-9a-f]{32}',token)
                or type(coins) is not tuple or not 1<=len(coins)<=1000
                or type(intents) is not tuple or len(intents)!=1
                or type(review.atoms) is not int or review.atoms<330
                or type(review.fee) is not int or not 1<=review.fee<=1000000
                or type(review.change_atoms) is not int or review.change_atoms<0
                or type(review.input_count) is not int
                or review.input_count!=len(coins)
                or type(review.code) is not str
                or type(review.commitment) is not str
                or not re.fullmatch('[0-9a-f]{64}',review.commitment)
                or intents[0].code!=review.code
                or intents[0].atoms!=review.atoms
                or proposal.fee!=review.fee
                or not hmac.compare_digest(
                    sha256(prepared.psbt).hexdigest(),review.commitment)):
            raise ValueError
        selected=[]
        values=[]
        for c in coins:
            if (type(c) is not dict or type(c.get('atoms')) is not int
                    or not 1<=c['atoms']<=22_000_000*100000000):
                raise ValueError
            selected.append(_outpoint(c['txid'],c['vout']))
            values.append(c['atoms'])
        if len(set(selected))!=len(selected):
            raise ValueError
        total=sum(values)
        if (total>22_000_000*100000000 or
                total-review.atoms-review.fee!=review.change_atoms
                or (0<review.change_atoms<330)):
            raise ValueError
        anchored=[]
        for row in rows:
            if type(row) not in (tuple,list) or len(row)!=4:
                raise ValueError
            txid,vout,rowtoken,state=row
            if rowtoken!=token or state!=expected_state:
                raise ValueError
            anchored.append(_outpoint(txid,vout))
        if (len(set(anchored))!=len(anchored)
                or set(anchored)!=set(selected)):
            raise ValueError
        spent=[]
        for row in mempool_spends:
            if type(row) not in (tuple,list) or len(row)!=2:
                raise ValueError
            spent.append(_outpoint(*row))
        if set(selected).intersection(spent):
            raise ValueError
        psbt=PSBT.decode(prepared.psbt)
        if psbt.version!=2 or tuple(psbt.tx.inputs)!=tuple(selected):
            raise ValueError
        if expected_state=='signed':
            if type(signed_psbt) is not bytes:
                raise ValueError
            actual=PSBT.decode(signed_psbt)
            if (actual.version!=2 or
                    tuple(actual.tx.inputs)!=tuple(selected) or
                    actual.txid()!=psbt.txid()):
                raise ValueError
        elif signed_psbt is not None:
            raise ValueError
        return True
    except (KeyError,TypeError,ValueError,OverflowError,AttributeError,IndexError):
        raise SendInvariantRefusal('F06_EXACT_SEND_RESERVATION_DENIED') from None
