"""F-09: bounded genuine-Core persistent read stability acceptance.

Call ONLY with an already authenticated, owned and disposable WAM v0.1.11
REGTEST ManagedReadRpc. This module has no daemon lifecycle, credentials,
write RPC, disk mutation, key or signer access. A short CI soak cannot prove
hours/days uptime, hostile disk pressure, multi-node sync or physical memory
budgets; these remain PENDING until actually observed.
"""
from dataclasses import asdict,dataclass
import re
import time

from .v1_contracts import require_regtest

F09_BUDGET_VERSION='F09_V1_64_CYCLES_180S'
F09_CYCLES=64
F09_TOTAL_DEADLINE_SECONDS=180
F09_SINGLE_CYCLE_SECONDS=12


class OperationalSoakRefusal(ValueError):
    pass


@dataclass(frozen=True)
class OperationalSoakEvidence:
    status: str
    budget_version: str
    chain: str
    source: str
    cycles_completed: int
    read_only_rpc_calls: int
    verified_tip_height: int
    total_milliseconds: int
    worst_cycle_milliseconds: int
    stable_tip: bool
    no_core_mutations: bool
    no_wallet_keys_or_balances_read: bool
    long_hours_days_qualified: bool = False
    multi_node_peer_sync_qualified: bool = False
    low_disk_crash_memory_pressure_qualified: bool = False
    real_large_history_rescan_qualified: bool = False


def verify_owned_core_read_soak(*, call, expected_genesis, height,
                                tip, cycles=F09_CYCLES, monotonic=None):
    """64 sequential real HTTP requests per RPC, no synthetic E2E receipt.

    A corrupt/missing/late response, tip drift, Core node busy, or RPC
    exception fails closed. No retry and no implicit daemon restart.
    """
    try:
        if (not callable(call) or type(expected_genesis) is not str
                or not re.fullmatch('[0-9a-f]{64}',expected_genesis)
                or type(height) is not int or not 1<=height<=1000000
                or type(tip) is not str
                or not re.fullmatch('[0-9a-f]{64}',tip)
                or type(cycles) is not int or cycles!=F09_CYCLES):
            raise ValueError
        if monotonic is None:monotonic=time.monotonic
        if not callable(monotonic):raise ValueError
        from .wsp_live import REGTEST_GENESIS
        require_regtest('regtest',expected_genesis)
        if expected_genesis!=REGTEST_GENESIS:
            raise ValueError
        start=monotonic()
        if type(start) not in (float,int):raise ValueError
        worst=0.0
        for _ in range(F09_CYCLES):
            mark=monotonic()
            chain=call('getblockchaininfo')
            blockcount=call('getblockcount')
            best=call('getbestblockhash')
            elapsed=monotonic()-mark
            total=monotonic()-start
            if (type(chain) is not dict or chain.get('chain')!='regtest'
                    or type(chain.get('blocks')) is not int
                    or chain['blocks']!=height
                    or chain.get('bestblockhash')!=tip
                    or type(blockcount) is not int or blockcount!=height
                    or type(best) is not str or best!=tip
                    or type(elapsed) not in (float,int) or elapsed<0
                    or type(total) not in (float,int) or total<0
                    or elapsed>F09_SINGLE_CYCLE_SECONDS
                    or total>F09_TOTAL_DEADLINE_SECONDS):
                raise ValueError
            worst=max(worst,elapsed)
        total=monotonic()-start
        if type(total) not in (float,int) or total<0 or total>F09_TOTAL_DEADLINE_SECONDS:
            raise ValueError
        return OperationalSoakEvidence(
            status='F09_GENUINE_CORE_BOUNDED_READ_SOAK_PASS',
            budget_version=F09_BUDGET_VERSION,
            chain='regtest',source='owned-http',
            cycles_completed=F09_CYCLES,
            read_only_rpc_calls=3*F09_CYCLES,
            verified_tip_height=height,
            total_milliseconds=round(total*1000),
            worst_cycle_milliseconds=round(worst*1000),
            stable_tip=True,no_core_mutations=True,
            no_wallet_keys_or_balances_read=True)
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError,OSError):
        raise OperationalSoakRefusal('F09_BOUNDED_CORE_READ_DENIED') from None
