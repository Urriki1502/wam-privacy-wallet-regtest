"""Explicit Shared-only scanner reconciliation; never transaction replay.

Original native generations and retained runtimes stay intact. A stronger
canonical branch is observed through the SAME owned signed Core. The only
adopted wallet state is the latest authenticated checkpoint, independently
resynced with WSP. Unanchored irreversible reservations cannot disappear.
"""
from hashlib import sha256
import json
import os
import re
import secrets
import sqlite3

from . import custody
from .bip39_native_checkpoint import (
    _directory,_native,_scanner_anchor_record,_checkpoint_filename,_checkpoint_names,
    _read_authenticated_candidate,_owned_tip,_require_confirmed_descendant,
    _publish_advanced_candidate,
)
from .bip39_seed_vault import _owned_password,_owner_binding,_exact_namespace,open_owned_seed_container
from .bip39_scanner_checkpoint import decode_candidate,require_irreversible_preserved
from .managed_wallet_checkpoint import _owned
from .managed_wallet_session import RuntimeGuard
from .shared_regtest import SharedRegtestProfile,peer_status

SCHEMA='wam-q06-shared-reconciliation/v1'
RUNTIME=re.compile(r'wallet-runtime-recovery-[0-9a-f]{16}\.sqlite\Z')
RECORD=re.compile(r'reconciliation-[0-9]{9}\.enc\Z')


class ReconciliationError(ValueError):pass


def _shared(owner):
    _owned(owner)
    if type(getattr(owner,'shared_profile',None)) is not SharedRegtestProfile:
        raise ReconciliationError('Q06_RECONCILIATION_SHARED_ONLY')


def _runtimes(owner):
    paths=sorted(p for p in owner.directory.iterdir() if RUNTIME.fullmatch(p.name))
    if len(paths)>32:raise ReconciliationError('Q06_RECONCILIATION_RUNTIME_LIMIT')
    return paths


def _runtime_evidence(path):
    """Read-only protected bytes; never adopt tables, keys or signing data."""
    guard=RuntimeGuard(path)
    connection=None
    try:
        before=os.fstat(guard.fd)
        if any(path.with_name(path.name+s).exists() or path.with_name(path.name+s).is_symlink()
               for s in ('-journal','-wal','-shm')):
            raise ReconciliationError('Q06_RECONCILIATION_RUNTIME_BUSY')
        if os.fstat(guard.fd).st_size>128*1024*1024:
            raise ReconciliationError('Q06_RECONCILIATION_RUNTIME_LIMIT')
        digest=sha256()
        while True:
            chunk=os.read(guard.fd,65536)
            if not chunk:break
            digest.update(chunk)
        connection=sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1',uri=True)
        rows=connection.execute('SELECT txid,vout,token,state,created FROM reservations').fetchmany(100001)
        if len(rows)>100000 or len(rows)!=len({(r[0],r[1]) for r in rows}):
            raise ReconciliationError('Q06_RECONCILIATION_RESERVATIONS_INVALID')
        guard.check()
        after=os.fstat(guard.fd)
        if any(getattr(before,k)!=getattr(after,k) for k in ('st_size','st_mtime_ns','st_ctime_ns')):
            raise ReconciliationError('Q06_RECONCILIATION_RUNTIME_CHANGED')
        return digest.hexdigest(),{(r[0],r[1]):tuple(r[2:]) for r in rows}
    finally:
        if connection is not None:connection.close()
        guard.close()


def _approved(owner,seed_id,folder,anchor,source,password):
    """Authenticated receipts authorize retaining exact old bytes only.

    A prepared receipt is inert until its target is in the monotonic native
    checkpoint history; it never adopts a pending generation after a crash.
    """
    directory=owner.directory/'q06-reconciliations'
    if not directory.exists() and not directory.is_symlink():return {}
    storage=custody.storage();storage.validate_directory(directory)
    paths=list(directory.iterdir())
    if len(paths)>4096 or any(not RECORD.fullmatch(p.name) for p in paths):
        raise ReconciliationError('Q06_RECONCILIATION_RECEIPT_NAMESPACE')
    from wam_sp.keystore import unseal
    current=_scanner_anchor_record(anchor.read())
    approved={}
    for path in paths:
        data=json.loads(unseal(storage.read(directory,path.name),password,b'recovery'))
        if (type(data) is not dict or set(data)!={'schema','owner_binding','seed_id','parent','target','tip','branch','runtimes'}
                or data['schema']!=SCHEMA or data['owner_binding']!=_owner_binding(owner)
                or data['seed_id']!=seed_id or type(data['runtimes']) is not dict
                or len(data['runtimes'])>32
                or data['branch'] not in ('confirmed-descendant','owned-core-validated-stronger-branch')
                or type(data['tip']) is not list or len(data['tip'])!=2
                or type(data['tip'][0]) is not int or not 0<=data['tip'][0]<=1000000
                or type(data['tip'][1]) is not str or not re.fullmatch('[0-9a-f]{64}',data['tip'][1])):
            raise ReconciliationError('Q06_RECONCILIATION_RECEIPT_DENIED')
        parent=_scanner_anchor_record(data['parent']);target=_scanner_anchor_record(data['target'])
        if target[0]!=parent[0]+1 or path.name!=f'reconciliation-{target[0]:09d}.enc':
            raise ReconciliationError('Q06_RECONCILIATION_RECEIPT_DENIED')
        if current[0]<target[0]:
            raise ReconciliationError('Q06_RECONCILIATION_PENDING_NATIVE_CAS')
        for record in (parent,target):
            if sha256(storage.read(folder,_checkpoint_filename(record[0]))).hexdigest()!=record[1]:
                raise ReconciliationError('Q06_RECONCILIATION_NATIVE_HISTORY_CHANGED')
        for name,digest in data['runtimes'].items():
            if (not RUNTIME.fullmatch(name) or type(digest) is not str
                    or not re.fullmatch('[0-9a-f]{64}',digest)
                    or name in approved and approved[name]!=digest):
                raise ReconciliationError('Q06_RECONCILIATION_RUNTIME_CHANGED')
            approved[name]=digest
    return approved


def require_reconciled_runtimes(owner,seed_folder,source,password,paths,*,keychain=None):
    """Open may skip only exact retained bytes covered by a committed receipt."""
    _shared(owner)
    seed_id,folder=_directory(owner,seed_folder)
    _,anchor=_native(folder,seed_id,source,keychain)
    with anchor.lease():
        approved=_approved(owner,seed_id,folder,anchor,source,password)
        for path in paths:
            digest,_=_runtime_evidence(path)
            if approved.get(path.name)!=digest:
                raise ReconciliationError('Q06_RECONCILIATION_RUNTIME_UNAPPROVED')
            lock=path.with_name(path.name+'.scan.lock')
            if lock.exists() or lock.is_symlink():
                guard=RuntimeGuard(lock)
                guard.check();guard.close()


def _branch(owner,old,tip):
    info=owner.read.call('getblockchaininfo')
    if info.get('chain')!='regtest' or (info.get('blocks'),info.get('bestblockhash'))!=tip:
        raise ReconciliationError('Q06_RECONCILIATION_TIP_CHANGED')
    if tip[0]>=old[0] and owner.read.call('getblockhash',[old[0]])==old[1]:
        _require_confirmed_descendant(owner,old,tip)
        return 'confirmed-descendant'
    block=owner.read.call('getblock',[old[1],2])
    def work(value):
        if type(value) is not str or not re.fullmatch('[0-9a-f]{64}',value):
            raise ReconciliationError('Q06_RECONCILIATION_WORK_DENIED')
        return int(value,16)
    if (block.get('hash')!=old[1] or block.get('height')!=old[0]
            or block.get('confirmations')!=-1 or tip[0]<=old[0]
            or work(info.get('chainwork'))<=work(block.get('chainwork'))):
        raise ReconciliationError('Q06_RECONCILIATION_STRONGER_BRANCH_REQUIRED')
    return 'owned-core-validated-stronger-branch'


def reconcile_shared(owner,seed_folder,source,password,*,authorized=False,keychain=None):
    _owned_password(owner,source,password,authorized)
    _shared(owner);peer_status(owner.directory,require_connected=True)
    seed_id,folder=_directory(owner,seed_folder)
    scanner=guard=rpc=None
    good=False
    phase='SEED_AUTH'
    try:
        with open_owned_seed_container(owner,seed_folder,source,password,authorized=True,keychain=keychain) as keys:
            phase='NATIVE_AUTH'
            storage,anchor=_native(folder,seed_id,source,keychain)
            with anchor.lease():
                original=_scanner_anchor_record(anchor.read())
                _exact_namespace(folder,_checkpoint_names(original[0]))
                candidate,data=_read_authenticated_candidate(storage,anchor,folder,original,seed_id,_owner_binding(owner),keys,password)
                phase='CHAIN_PROOF'
                tip=_owned_tip(owner)
                branch=_branch(owner,(data['height'],data['tip']),tip)
                approved=_approved(owner,seed_id,folder,anchor,source,password)
                phase='RESTORE_AUTHENTICATED'
                from wam_sp.scanner import Scanner
                from .wallet_session import WalletCoreCli
                from .bip39_spend_session import _reservation_map,_remove_known_scanner_lock
                temporary=owner.directory/('q06-reconcile-'+secrets.token_hex(16))
                custody.create_directory(temporary)
                target=temporary/'wallet-runtime.sqlite'
                import sys
                if sys.platform=='win32':
                    from .windows_private_storage import create_managed_runtime
                    create_managed_runtime(target)
                scanner=Scanner(target,keys.accounts());guard=RuntimeGuard(target)
                decode_candidate(keys,scanner,candidate,password.decode('utf-8'),owner_binding=_owner_binding(owner))
                held=_reservation_map(scanner)
                runtimes={}
                phase='RETAINED_RUNTIMES'
                for path in _runtimes(owner):
                    digest,rows=_runtime_evidence(path)
                    if path.name in approved:
                        if approved[path.name]!=digest:raise ReconciliationError('Q06_RECONCILIATION_RUNTIME_CHANGED')
                    else:require_irreversible_preserved(rows,held)
                    runtimes[path.name]=digest
                phase='CANONICAL_RESCAN'
                rpc=WalletCoreCli(owner.cli,owner.directory);rpc.attest()
                scanner.sync(rpc);scanner.assert_current()
                require_irreversible_preserved(held,_reservation_map(scanner))
                if scanner.store.tip()!=tip or _owned_tip(owner)!=tip or anchor.read()!=original:
                    raise ReconciliationError('Q06_RECONCILIATION_TIP_OR_ANCHOR_CHANGED')
                peer_status(owner.directory,require_connected=True)
                phase='PREPARE_RECEIPT'
                receipts=owner.directory/'q06-reconciliations'
                if not receipts.exists():custody.create_directory(receipts)
                def prepare(parent,new):
                    from wam_sp.keystore import seal
                    record=dict(schema=SCHEMA,owner_binding=_owner_binding(owner),seed_id=seed_id,
                                parent=parent,target=new,tip=tip,branch=branch,runtimes=runtimes)
                    raw=json.dumps(record,sort_keys=True,separators=(',',':')).encode('ascii')
                    storage.publish(receipts,f'reconciliation-{new[0]:09d}.enc',seal(raw,password,b'recovery'))
                phase='PUBLISH_NATIVE'
                result=_publish_advanced_candidate(owner,seed_folder,scanner,source,password,keys,folder,
                    seed_id,{'generation':original[0]},tip,keychain,anchor_override=anchor,before_publish=prepare)
                guard.check();_owned(owner)
                good=True
                return dict(result,status='Q06_SHARED_RECONCILIATION_VERIFIED',branch=branch,
                            retained_runtime_count=len(runtimes),automatic_broadcast=False,
                            signing_authorized=False,reservations_preserved=True)
    except Exception as error:
        if os.environ.get('WAM_RECONCILIATION_DIAGNOSTICS')=='1':
            args=error.args
            code=args[0] if len(args)==1 and type(args[0]) is str and re.fullmatch('[A-Z0-9_]{1,96}',args[0]) else 'INTERNAL_DENIED'
            print('Q06_RECONCILIATION_DENIED_STAGE='+phase+';CATEGORY='+code,flush=True)
        raise ReconciliationError('Q06_SHARED_RECONCILIATION_DENIED') from None
    finally:
        if scanner is not None:scanner.close()
        if rpc is not None and getattr(rpc,'_transport',None) is not None:rpc._transport.close()
        if guard is not None:
            if good:
                _remove_known_scanner_lock(target);guard.remove_owned();temporary.rmdir()
            else:guard.close()
