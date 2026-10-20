"""F-10: bounded coexistence of owned REGTEST Core mining and wallet RPC.

This executes against ONLY the caller's freshly owned, disposable Core node
after wallet/mining fixtures. It never attaches to an external miner, changes
wam.conf, adopts a user datadir, stops or restarts Core, or grants spend access.
Core generatetoaddress is an internal mining fixture; it is NOT evidence that
the separate released wam-miner executable is qualified alongside the GUI.
"""
from concurrent.futures import ThreadPoolExecutor,TimeoutError as FutureTimeout
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
import threading
import time

from .v1_contracts import require_regtest
from .wsp_live import REGTEST_GENESIS

F10_BLOCKS=4
F10_MAX_SECONDS=100


class MinerCoexistenceRefusal(ValueError):
    pass


@dataclass(frozen=True)
class OwnedMinerCoexistence:
    status: str
    generated_blocks: int
    wallet_reads_verified: int
    longpoll_witnesses: int
    original_core_config_unchanged: bool
    core_owner_scope: str
    no_external_miner_process_started: bool
    no_node_restart_or_stop: bool
    no_wallet_mutation_by_reader: bool
    wallet_identity_continued: bool
    resource_limit_seconds: int
    external_solo_miner_binary_qualified: bool = False
    queue_64_operator_option_qualified: bool = False
    sunset_400001_real_miner_qualified: bool = False


def prove_owned_core_miner_coexistence(*, rpc, read, wallet, datadir,
                                       miner_address, sleep=None):
    """Observe Core mining while an independent Core longpoll is pending.

    A native 4-block production-code Core generator is used on the PRIVATE
    fixture's chain, not a separate miner process. Every block is checked by
    the authenticated read-only wallet transport; no wallet writes occur.
    """
    try:
        if (not callable(rpc) or read is None or not callable(read.call)
                or not callable(wallet) or type(datadir) is not type(Path())
                or not datadir.is_absolute() or not datadir.is_dir()
                or type(miner_address) is not str
                or not 15<=len(miner_address)<=120):
            raise ValueError
        pause=time.sleep if sleep is None else sleep
        if not callable(pause):raise ValueError
        require_regtest('regtest',read.call('getblockhash',[0]))
        before=read.call('getblockchaininfo')
        if (type(before) is not dict or before.get('chain')!='regtest'
                or type(before.get('blocks')) is not int
                or before['blocks']<101
                or type(before.get('bestblockhash')) is not str
                or not re.fullmatch('[0-9a-f]{64}',before['bestblockhash'])
                or rpc('getconnectioncount')!=0):
            raise ValueError
        config=datadir/'wam.conf'
        original=sha256(config.read_bytes()).digest()
        identity=wallet('getwalletinfo')
        if (type(identity) is not dict or
                identity.get('walletname')!='test' or
                identity.get('descriptors') is not True):
            raise ValueError
        start=time.monotonic()
        completed=reads=witnesses=0
        height=before['blocks']
        for _ in range(F10_BLOCKS):
            started=threading.Event()
            def longpoll():
                started.set()
                return rpc('waitfornewblock','12000',timeout=25)
            with ThreadPoolExecutor(max_workers=1) as pool:
                future=pool.submit(longpoll)
                if not started.wait(3):
                    raise ValueError
                # Give the native Core waitfornewblock RPC a chance to reach
                # the server before miner requests the next block. This
                # bounded handshake is NOT proof of full solo-miner process
                # coexistence or queue saturation.
                pause(.35)
                hashes=rpc('generatetoaddress','1',miner_address,timeout=60)
                if (type(hashes) is not list or len(hashes)!=1
                        or type(hashes[0]) is not str
                        or not re.fullmatch('[0-9a-f]{64}',hashes[0])):
                    raise ValueError
                observed=future.result(timeout=26)
            height+=1
            completed+=1
            if (type(observed) is not dict
                    or observed.get('hash')!=hashes[0]
                    or type(observed.get('height')) is not int
                    or observed['height']!=height):
                raise ValueError
            witnesses+=1
            core=read.call('getblockchaininfo')
            if (type(core) is not dict or core.get('chain')!='regtest'
                    or core.get('blocks')!=height
                    or core.get('bestblockhash')!=hashes[0]
                    or read.call('getblockcount')!=height
                    or read.call('getbestblockhash')!=hashes[0]):
                raise ValueError
            reads+=3
            active=wallet('getwalletinfo')
            if (type(active) is not dict
                    or active.get('walletname')!=identity['walletname']
                    or active.get('descriptors') is not True):
                raise ValueError
            if sha256(config.read_bytes()).digest()!=original:
                raise ValueError
            if time.monotonic()-start>F10_MAX_SECONDS:
                raise ValueError
        if (rpc('getconnectioncount')!=0
                or sha256(config.read_bytes()).digest()!=original
                or height!=read.call('getblockcount')
                or read.call('getblockhash',[0])!=REGTEST_GENESIS):
            raise ValueError
        return OwnedMinerCoexistence(
            status='F10_OWNED_CORE_MINING_AND_WALLET_READ_PASS',
            generated_blocks=completed,
            wallet_reads_verified=reads,
            longpoll_witnesses=witnesses,
            original_core_config_unchanged=True,
            core_owner_scope='ephemeral-owned-regtest',
            no_external_miner_process_started=True,
            no_node_restart_or_stop=True,
            no_wallet_mutation_by_reader=True,
            wallet_identity_continued=True,
            resource_limit_seconds=F10_MAX_SECONDS)
    except (ValueError,TypeError,KeyError,AttributeError,OSError,
            OverflowError,FutureTimeout):
        raise MinerCoexistenceRefusal('F10_OWNED_MINING_COEXISTENCE_DENIED') from None
