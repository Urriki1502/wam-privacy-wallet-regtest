"""Fixed owned-Core test wallet reads. No attach, keys, writes or spend authority."""
from dataclasses import dataclass
import re
from .mining_account import MiningWalletBalance, RewardSplit
from .json_rpc import RpcError
from .wsp_live import REGTEST_GENESIS

MAX_MINING_UTXOS = 512


def mining_params(method, params):
    if type(method) is not str or type(params) is not list:
        raise RpcError('RPC_MINING_READ_SCOPE_DENIED')
    if method in ('getwalletinfo', 'getbalances', 'getdevfeeinfo'):
        valid = not params
    elif method == 'listunspent':
        valid = len(params) == 1 and type(params[0]) is int and params[0] == 0
    elif method == 'getaddressinfo':
        valid = (len(params) == 1 and type(params[0]) is str
                 and re.fullmatch('[a-zA-Z0-9]{20,120}', params[0]))
    elif method == 'gettxout':
        valid = (len(params) == 3 and type(params[0]) is str
                 and re.fullmatch('[0-9a-f]{64}', params[0]) and type(params[1]) is int
                 and 0 <= params[1] < 2**32 and params[2] is True)
    else:
        raise RpcError('RPC_MINING_READ_SCOPE_DENIED')
    if not valid:raise RpcError('RPC_MINING_PARAMS_DENIED')


def mining_result(method, value):
    valid = type(value) is dict
    if method == 'listunspent':
        valid = type(value) is list and len(value) <= MAX_MINING_UTXOS
    elif method == 'getwalletinfo':
        valid = valid and value.get('walletname') == 'test'
    elif method == 'getaddressinfo':
        valid = valid and type(value.get('ismine')) is bool
    if not valid:raise RpcError('RPC_MINING_RESULT_DENIED')
    return value


@dataclass(frozen=True)
class MiningSnapshot:
    height: int
    tip: str
    balance: MiningWalletBalance
    next_reward: RewardSplit


def read_mining_snapshot(rpc):
    """Called under shared transport lock; chain changes discard the whole read.

    The fixed wallet was created in the fresh owned datadir, never imported or
    selected by a caller. Private descriptors/keys are never requested.
    Core UTXO spend eligibility is separate from Fusion/WSP reservations.
    """
    def read(method, params=None):
        return rpc._request(method, [] if params is None else params, mining=True)
    try:
        chain = rpc.attest()
        tip = rpc._request('getbestblockhash', [])
        info = read('getwalletinfo')
        treasury = read('getdevfeeinfo')
        if (type(treasury.get('percent')) is not int or treasury['percent'] != 5
                or type(treasury.get('start_height')) is not int or treasury['start_height'] != 1
                or type(treasury.get('last_height')) is not int or treasury['last_height'] != 400000):
            raise ValueError
        ownership = read('getaddressinfo', [treasury['address']])
        if ownership['ismine'] is not False or ownership.get('iswatchonly', False) is not False:
            raise ValueError
        balances = read('getbalances')
        unspent = read('listunspent', [0])
        outputs = {}
        for u in unspent:
            owner = read('getaddressinfo', [u['address']])
            if owner['ismine'] is not True or owner.get('scriptPubKey') != u['scriptPubKey']:
                raise ValueError
            out = read('gettxout', [u['txid'], u['vout'], True])
            if out.get('bestblock') != tip:raise ValueError
            outputs[(u['txid'], u['vout'])] = out
        balance = MiningWalletBalance.from_core(chain=chain['chain'], genesis=REGTEST_GENESIS,
            wallet_info=info, balances=balances, unspent=unspent, txouts=outputs,
            treasury_script=treasury['script'])
        if (read('getbalances') != balances or read('listunspent', [0]) != unspent
                or rpc.attest()['blocks'] != chain['blocks']
                or rpc._request('getbestblockhash', []) != tip):
            raise RpcError('RPC_MINING_CHAIN_CHANGED')
        return MiningSnapshot(chain['blocks'], tip, balance, RewardSplit.regtest(chain['blocks']+1))
    except RpcError:raise
    except (ValueError, KeyError, TypeError, AttributeError, OverflowError):
        raise RpcError('RPC_MINING_RECONCILIATION_DENIED') from None
