"""Create/reopen a native checkpoint ONLY inside the original owned Core process.

No GUI/control protocol, password transport, funding, mining or spending API.
Selectively adapts historical Q05 create/reopen, keeping current native vault,
32-byte Keyring and Q03 owned RPC rather than importing the stacked branch.
"""
from hashlib import sha256
import hmac
import json
from pathlib import Path
import re
import secrets
import subprocess

from . import custody
from .history_pages import HISTORY_OFFSET_MAX,HISTORY_PAGE_LIMIT
from .history_pages import complete_history
from .supervisor_protocol import _distinct
from .supervisor_store import create_once,read_exact
from .wsp_live import PINNED_WSP_COMMIT,REGTEST_GENESIS,_pinned_source

SCHEMA='wam-q05-native-wallet-reference/v1'


class ManagedWalletError(ValueError):pass


def _canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':')).encode('ascii')


def _owned(owner):
    from .core_supervisor import CoreSupervisor
    from .rpc_scope import identity
    process=getattr(owner,'process',None)
    scope=identity(owner.directory) if type(owner) is CoreSupervisor else None
    if (type(owner) is not CoreSupervisor or type(process) is not subprocess.Popen
            or process.poll() is not None or owner._faulted or not owner._registered
            or owner.binding is None or owner.binding.process is not process
            or scope is None or scope.binding.process is not process):
        raise ManagedWalletError('MANAGED_WALLET_ORIGINAL_OWNER_REQUIRED')
    owner._check_profile();owner._check_core();owner.journal._read()
    last=owner.journal.events[-1]
    if (last['state']!='RUNNING' or last['owner']!=owner.journal.owner
            or last['core_pid']!=process.pid):
        raise ManagedWalletError('MANAGED_WALLET_RUNNING_JOURNAL_REQUIRED')
    status=owner.status()
    if not status['core_process_owned'] or status['state'] not in ('ready','syncing'):
        raise ManagedWalletError('MANAGED_WALLET_OWNED_CORE_UNVERIFIED')


def _inputs(owner,source,password,authorized):
    if authorized is not True:
        raise ManagedWalletError('MANAGED_WALLET_EXPLICIT_CONSENT_REQUIRED')
    if (type(source) is not type(Path()) or not source.is_absolute()
            or type(password) is not bytes or not 12<=len(password)<=1024):
        raise ManagedWalletError('MANAGED_WALLET_INPUT_DENIED')
    _owned(owner);_pinned_source(source)


def _reference(owner,wallet_id):
    return {'schema':SCHEMA,'wallet_id':wallet_id,'network':REGTEST_GENESIS,
            'profile_sha256':sha256(_canonical(owner.profile)).hexdigest(),
            'wsp_source_commit':PINNED_WSP_COMMIT,'mainnet_allowed':False}


def _publish_reference(owner,wallet_id):
    row=_reference(owner,wallet_id)
    secret=read_exact(owner.root,'supervisor.token',length=32)
    row['mac']=hmac.digest(secret,SCHEMA.encode()+b'\n'+_canonical(row),'sha256').hex()
    create_once(owner.root,'supervisor.wallet',_canonical(row))


def _read_reference(owner):
    try:
        row=json.loads(read_exact(owner.root,'supervisor.wallet').decode('ascii'),
                       object_pairs_hook=_distinct)
        if (type(row) is not dict or set(row)!=set(_reference(owner,''))|{'mac'}
                or type(row['wallet_id']) is not str
                or not re.fullmatch('[0-9a-f]{32}',row['wallet_id'])):raise ValueError
        mac=row.pop('mac');expected=_reference(owner,row['wallet_id'])
        secret=read_exact(owner.root,'supervisor.token',length=32)
        if (row!=expected or row['mainnet_allowed'] is not False
                or type(mac) is not str or not re.fullmatch('[0-9a-f]{64}',mac)
                or not hmac.compare_digest(mac,hmac.digest(secret,
                    SCHEMA.encode()+b'\n'+_canonical(row),'sha256').hex())):raise ValueError
        return row['wallet_id']
    except (OSError,ValueError,TypeError,KeyError,UnicodeError):
        raise ManagedWalletError('MANAGED_WALLET_REFERENCE_UNVERIFIED') from None


def _runtime(owner):
    path=owner.directory/'wallet-runtime.sqlite'
    if any(path.with_name(path.name+suffix).exists()
            or path.with_name(path.name+suffix).is_symlink()
            for suffix in ('','-journal','-wal','-shm')):
        raise ManagedWalletError('MANAGED_WALLET_EXISTING_RUNTIME_DENIED')
    return path


def publication_ambiguity(owner,source,*,authorized=False):
    """Read-only interrupted-publication evidence. Never repair or adopt files."""
    if authorized is not True:
        raise ManagedWalletError('MANAGED_WALLET_EXPLICIT_CONSENT_REQUIRED')
    if type(source) is not type(Path()) or not source.is_absolute():
        raise ManagedWalletError('MANAGED_WALLET_INPUT_DENIED')
    _owned(owner);_pinned_source(source)
    runtime=owner.directory/'wallet-runtime.sqlite'
    folder=owner.directory/'wallet-vault'
    sidecars=tuple(suffix for suffix in ('','-journal','-wal','-shm')
                   if runtime.with_name(runtime.name+suffix).exists()
                   or runtime.with_name(runtime.name+suffix).is_symlink())
    ciphertexts=()
    if folder.is_dir() and not folder.is_symlink():
        ciphertexts=tuple(sorted(p.name for p in folder.iterdir()
                                 if p.is_file() and p.name.startswith('snapshot-')
                                 and p.name.endswith('.enc')))
    reference=(owner.root/'supervisor.wallet').exists()
    return {'schema':SCHEMA,'automatic_recovery_allowed':False,
            'anchor_advancement_allowed':False,'runtime_suffixes':sidecars,
            'orphan_or_present_ciphertext':ciphertexts,
            'wallet_reference_present':reference,
            'checkpoint_open_blocked':bool(sidecars),
            'required_action':'Authenticated operator reconciliation; do not delete '
                              'unknown SQLite, orphan ciphertext or advance the native anchor.'}


def _require_matching_tip(scanner,rpc):
    height,tip=scanner.store.tip()
    if (height,tip)!=(rpc.call('getblockcount'),rpc.call('getbestblockhash')):
        raise ManagedWalletError('MANAGED_WALLET_CHAIN_CHANGED')
    return height,tip


def _history_page(wallet,limit,offset):
    # Public Wallet.history starts a nested BEGIN IMMEDIATE and cannot share a snapshot.
    try:
        page=wallet._history(limit,offset)
    except ValueError:
        raise ManagedWalletError('MANAGED_WALLET_HISTORY_INCONSISTENT') from None
    if type(page) is not list or len(page)>limit:
        raise ManagedWalletError('MANAGED_WALLET_HISTORY_INCONSISTENT')
    return page


class _HistoryDenied(ManagedWalletError):
    def __init__(self,code):
        super().__init__('MANAGED_WALLET_'+code)


def reservation_fingerprint(rows):
    """Hash reservation rows in caller order. Never drop a signed or uncertain row."""
    digest=sha256();count=0;states=set()
    for row in rows:
        try:
            materialized=list(row)
            if len(materialized)!=5:
                raise ValueError
            digest.update(_canonical(materialized)+b'\n')
            states.add(materialized[3])
        except (TypeError,ValueError,IndexError):
            raise ManagedWalletError('MANAGED_WALLET_RESERVATION_INCONSISTENT') from None
        count+=1
    try:
        ordered=sorted(states)
    except TypeError:
        raise ManagedWalletError('MANAGED_WALLET_RESERVATION_INCONSISTENT') from None
    return count,digest.hexdigest(),ordered


def _fingerprint_history(wallet,height,*,collect=False):
    """Hash every history row in the caller's SQLite transaction; never truncate."""
    declared=wallet.db.execute('SELECT count(*) FROM history').fetchone()[0]
    count,digest,rows=complete_history(
        lambda limit,offset:_history_page(wallet,limit,offset),
        declared,height,collect=collect,error=_HistoryDenied)
    return (count,digest,rows) if collect else (count,digest)


def _locked_observation(ring,scanner,rpc,vault,wallet):
    height,tip=_require_matching_tip(scanner,rpc)
    with scanner.store.transaction():
        scanner.assert_current()
        locked_height,locked_tip=scanner.store.tip()
        if (locked_height,locked_tip)!=(height,tip):
            raise ManagedWalletError('MANAGED_WALLET_CHAIN_CHANGED')
        history_count,history_sha256=_fingerprint_history(wallet,height)
        reservation_count,reservation_sha256,states=reservation_fingerprint(wallet.db.execute(
            'SELECT txid,vout,token,state,created FROM reservations ORDER BY txid,vout'))
        # balance() would BEGIN IMMEDIATE again; stay on this snapshot.
        balance=wallet._balance(1)
    _require_matching_tip(scanner,rpc)
    return {'wallet_id':vault.anchor.wallet_id,'height':height,'tip':tip,
            'payment_code':ring.accounts()[-1].payment_code(),
            'confirmed_atoms':balance['confirmed_atoms'],'reserved_atoms':balance['reserved_atoms'],
            'available_atoms':balance['available_atoms'],
            'reservation_count':reservation_count,'reservation_states':states,
            'reservation_sha256':reservation_sha256,
            'history_count':history_count,'history_sha256':history_sha256,
            'checkpoint':list(vault._expected or ()),
            'wallet_locked':True,'signer_allowed':False,'broadcast_allowed':False,
            'mainnet_allowed':False}


def _snapshot(ring,scanner,rpc,vault):
    from wam_sp.wallet import Wallet
    scanner.sync(rpc);scanner.assert_current()
    return _locked_observation(ring,scanner,rpc,vault,Wallet(scanner))


def _close_owned_runtime(ring,scanner,runtime):
    scanner.close();ring.close()
    # Only the fresh runtime created by THIS call can be removed after an
    # anchored save. Unexpected sidecars remain quarantined, never swept.
    if any(runtime.with_name(runtime.name+s).exists()
           or runtime.with_name(runtime.name+s).is_symlink() for s in ('-journal','-wal','-shm')):
        raise ManagedWalletError('MANAGED_WALLET_RUNTIME_CLOSE_UNCERTAIN')
    runtime.unlink()


def checkpoint(owner,source,password,*,authorized=False,keychain=None,create=False):
    """Explicit one-shot create or authenticated reopen/resync; return locked.

    The native anchor lease covers restore/sync/save on one thread. Failure
    preserves the vault, journal and runtime for explicit reconciliation.
    This function is not exposed over the unencrypted control protocol.
    """
    _inputs(owner,source,password,authorized)
    if type(create) is not bool:raise ManagedWalletError('MANAGED_WALLET_MODE_DENIED')
    from .vault import CheckpointVault
    from .wallet_session import WalletCoreCli
    from wam_sp.keystore import Keyring
    from wam_sp.scanner import Scanner
    runtime=_runtime(owner);folder=owner.directory/'wallet-vault'
    if create:
        if (folder.exists() or folder.is_symlink()
                or (owner.root/'supervisor.wallet').exists()
                or (owner.root/'supervisor.wallet').is_symlink()):
            raise ManagedWalletError('MANAGED_WALLET_EXISTS_OR_UNCERTAIN')
        wallet_id=secrets.token_hex(16)
    else:
        wallet_id=_read_reference(owner)
        custody.storage().validate_directory(folder)
    ring=scanner=rpc=None
    try:
        rpc=WalletCoreCli(owner.cli,owner.directory);rpc.attest()
        anchor=custody.anchor(wallet_id,keychain)
        with anchor.lease():
            if create:
                if anchor.read() is not None:
                    raise ManagedWalletError('MANAGED_WALLET_ANCHOR_EXISTS')
                custody.create_directory(folder)
            vault=CheckpointVault(folder,anchor,source)
            if create:
                ring=Keyring();ring.backup(password)
                scanner=Scanner(runtime,ring.accounts())
            else:
                ring,scanner=vault.restore(runtime,password)
            before=vault._expected
            result=_snapshot(ring,scanner,rpc,vault)
            # Publish an authenticated checkpoint before deleting plaintext.
            # Resync may reconcile legitimate chain movement, never broadcast.
            vault.save(ring,scanner,password)
            result['checkpoint']=list(vault._expected)
            if anchor.read()!=vault._expected or (not create and before is None):
                raise ManagedWalletError('MANAGED_WALLET_ANCHOR_UNVERIFIED')
            _owned(owner)
            if create:_publish_reference(owner,wallet_id)
            _close_owned_runtime(ring,scanner,runtime)
            ring=scanner=None
            return result
    except (OSError,ValueError,RuntimeError):
        raise ManagedWalletError('MANAGED_WALLET_CHECKPOINT_DENIED') from None
    finally:
        if scanner is not None:scanner.close()
        if ring is not None:ring.close()
        if rpc is not None and getattr(rpc,'_transport',None) is not None:
            rpc._transport.close()
