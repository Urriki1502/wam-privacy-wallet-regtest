"""Explicit original-owner checkpoint recovery, preserving old ambiguous bytes.

Copies ONLY the current native-anchor ciphertext into a fresh same-wallet
container. Existing vault.save/anchor CAS advances normally; no orphan is
promoted, unknown SQLite removed, keyring regenerated or Core PID adopted.
Pending reference transactions stay locked, never automatically completed.
"""
from hashlib import sha256
import hmac
import json
import re
import secrets
import sys
import base64
import os
import sqlite3
import time

from . import custody
from .managed_wallet_checkpoint import (
    ManagedWalletError,_canonical,_inputs,_read_reference,_runtime,_snapshot,
    _owned,_close_owned_runtime,durable_core_checkpoint,
)
from .supervisor_identity import directory_identity
from .supervisor_protocol import _distinct
from .supervisor_store import create_once,read_exact

SCHEMA='wam-native-wallet-recovery-reference/v1'
MAX_EVENTS=100000
PREFIX='supervisor.recovery.'


def _logical_checkpoint(payload,password,identity=None):
    """Authenticate bounded WSP state in memory; never instantiate its keys."""
    from wam_sp.keystore import unseal
    from wam_sp.state import decode_checkpoint
    raw=unseal(base64.b64decode(payload['checkpoint'],validate=True),password,b'checkpoint')
    if identity is None:
        data=json.loads(raw,object_pairs_hook=_distinct)
        identity=data['identity']  # Native-anchored payload is authoritative.
    data=decode_checkpoint(raw,identity)
    if data.get('schema')!=3:raise ManagedWalletError('MANAGED_RECOVERY_SOURCE_AMBIGUOUS')
    keys=json.loads(unseal(base64.b64decode(payload['keys'],validate=True),password,b'keys'),
                    object_pairs_hook=_distinct)
    return data,sha256(_canonical(keys)).digest()


def _table_rows(tables):
    # Ignore SQLite's physical row order, never row values or duplicate rows.
    return {name:sorted(_canonical(row) for row in rows) for name,rows in tables.items()}


def _require_runtime_matches_anchor(path,expected):
    """Read-only native-pinned SQL; no journal recovery, migration or removal."""
    from .managed_wallet_session import RuntimeGuard
    from wam_sp.store import SCHEMA,TABLES
    if any(path.with_name(path.name+s).exists() or path.with_name(path.name+s).is_symlink()
           for s in ('-journal','-wal','-shm')):
        raise ManagedWalletError('MANAGED_RECOVERY_SOURCE_AMBIGUOUS')
    guard=RuntimeGuard(path);db=memory=None
    try:
        before=os.fstat(guard.fd)
        if not 1<=before.st_size<=1024**3:
            raise ManagedWalletError('MANAGED_RECOVERY_SOURCE_AMBIGUOUS')
        db=sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1',uri=True,timeout=5)
        # Some supported Python builds omit extension loading entirely.
        # Where the API exists, explicitly keep it disabled.
        if hasattr(db,'enable_load_extension'):db.enable_load_extension(False)
        db.execute('PRAGMA query_only=ON')
        db.execute('PRAGMA trusted_schema=OFF');db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH,32*1024*1024)
        deadline=time.monotonic()+5
        db.set_progress_handler(lambda: int(time.monotonic()>deadline),1000)
        memory=sqlite3.connect(':memory:');memory.executescript(SCHEMA)
        sql="SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
        if db.execute(sql).fetchall()!=memory.execute(sql).fetchall():
            raise ManagedWalletError('MANAGED_RECOVERY_SOURCE_AMBIGUOUS')
        actual={};total=0
        db.execute('BEGIN')
        meta=dict(db.execute('SELECT key,value FROM meta'))
        if (db.execute('PRAGMA user_version').fetchone()[0]!=3
                or meta.get('identity')!=expected['identity'] or meta.get('profile')!='WSP-1'):
            raise ManagedWalletError('MANAGED_RECOVERY_SOURCE_AMBIGUOUS')
        for table in TABLES:
            rows=[]
            for row in db.execute('SELECT * FROM '+table+' LIMIT 200001'):
                encoded=_canonical(list(row));total+=len(encoded)
                if len(rows)>=200000 or total>32*1024*1024:
                    raise ManagedWalletError('MANAGED_RECOVERY_SOURCE_AMBIGUOUS')
                rows.append(encoded)
            actual[table]=sorted(rows)
        if actual!=_table_rows(expected['tables']):
            raise ManagedWalletError('MANAGED_RECOVERY_UNANCHORED_STATE_DIVERGED')
        guard.check();after=os.fstat(guard.fd)
        if (any(getattr(before,k)!=getattr(after,k) for k in ('st_size','st_mtime_ns','st_ctime_ns'))
                or any(path.with_name(path.name+s).exists() or path.with_name(path.name+s).is_symlink()
                       for s in ('-journal','-wal','-shm'))):
            raise ManagedWalletError('MANAGED_RECOVERY_SOURCE_AMBIGUOUS')
    finally:
        if db is not None:db.close()
        if memory is not None:memory.close()
        guard.close()


def _require_no_divergent_source(owner,vault,current,password,payload,*,runtime=None):
    """Unknown bytes may only RESTRICT recovery, never authorize restoration.

    A future publication can contain a new irreversible sign/broadcast intent.
    Copying only the older anchor must not turn that reservation into a draft.
    Refuse any differing logical state; do not merge/promote/delete an orphan.
    """
    expected,keys=_logical_checkpoint(payload,password)
    deadline=time.monotonic()+15;future_count=0
    for path in vault.directory.iterdir():
        if time.monotonic()>deadline:
            raise ManagedWalletError('MANAGED_RECOVERY_SOURCE_AUDIT_BUDGET')
        if path.name=='.vault.lock':continue
        match=re.fullmatch(r'snapshot-([0-9]{9})\.enc',path.name)
        if match is None or int(match[1])==0:
            raise ManagedWalletError('MANAGED_RECOVERY_SOURCE_AMBIGUOUS')
        generation=int(match[1])
        if generation<=current[0]:continue
        future_count+=1
        if future_count>64:raise ManagedWalletError('MANAGED_RECOVERY_SOURCE_AUDIT_BUDGET')
        raw=custody.storage().read(vault.directory,path.name)
        future=vault._load_payload(password,(generation,sha256(raw).hexdigest()))
        data,future_keys=_logical_checkpoint(future,password,expected['identity'])
        if (not hmac.compare_digest(keys,future_keys)
                or _table_rows(data['tables'])!=_table_rows(expected['tables'])):
            raise ManagedWalletError('MANAGED_RECOVERY_UNANCHORED_STATE_DIVERGED')
    # The unknown runtime is not a source of keys or balances. Its only use is
    # a read-only equality check that can deny, never broaden, recovery.
    if runtime is None:
        _, name, _=active_location(owner,vault.anchor.wallet_id)
        runtime=owner.directory/name
    if runtime.exists() or runtime.is_symlink():_require_runtime_matches_anchor(runtime,expected)
    elif any(runtime.with_name(runtime.name+s).exists() or runtime.with_name(runtime.name+s).is_symlink()
             for s in ('-journal','-wal','-shm')):
        raise ManagedWalletError('MANAGED_RECOVERY_SOURCE_AMBIGUOUS')


def require_recovery_source_equivalence(owner,source,password,anchor):
    """Audit retained source evidence, including legacy COMMITs, read-only.

    A prior version's completed recovery must not hide a stricter source intent.
    This cannot authorize an old snapshot: active native anchor/floor checks
    still select the only restorable target. Unknown evidence only denies use.
    """
    try:
        _audit_recovery_sources(owner,source,password,anchor)
    except (sqlite3.Error,TypeError,KeyError,RecursionError):
        raise ManagedWalletError('MANAGED_RECOVERY_SOURCE_AMBIGUOUS') from None


def _audit_recovery_sources(owner,source,password,anchor):
    from .vault import CheckpointVault
    rows,_=_records(owner,anchor.wallet_id)
    folder=owner.directory/'wallet-vault';runtime=owner.directory/'wallet-runtime.sqlite'
    if sum(row['state']=='BEGIN' for row in rows)>64:
        raise ManagedWalletError('MANAGED_RECOVERY_SOURCE_AUDIT_BUDGET')
    deadline=time.monotonic()+15
    for row in rows:
        if time.monotonic()>deadline:raise ManagedWalletError('MANAGED_RECOVERY_SOURCE_AUDIT_BUDGET')
        if row['state']=='BEGIN':
            old=CheckpointVault(folder,anchor,source)
            payload=old._load_payload(password,row['source_anchor'])
            _require_no_divergent_source(owner,old,row['source_anchor'],password,payload,runtime=runtime)
        else:
            folder=owner.directory/('wallet-recovery-'+row['action'])
            runtime=owner.directory/('wallet-runtime-recovery-'+row['action']+'.sqlite')


def has_recovery_records(owner):
    return any(p.name.startswith(PREFIX) for p in owner.root.iterdir())


def _record(value):
    return (type(value) is list and len(value)==2 and type(value[0]) is int
            and 1<=value[0]<10**9 and type(value[1]) is str
            and re.fullmatch('[0-9a-f]{64}',value[1]) is not None)


def _transition(row,last):
    if row['state']=='BEGIN':
        if row['target_anchor'] is not None or last and last['state']!='COMMIT':raise ValueError
        if last:require_anchor_floor(row['source_anchor'],last['target_anchor'])
    elif row['state']=='COMMIT':
        if (last is None or last['state']!='BEGIN' or not _record(row['target_anchor'])
                or row['target_anchor'][0]!=row['source_anchor'][0]+1
                or any(_canonical(row[k])!=_canonical(last[k]) for k in
                       ('action','target_identity','source_anchor'))):raise ValueError
    else:raise ValueError


def _records(owner,wallet_id):
    names=sorted(p.name for p in owner.root.iterdir() if p.name.startswith(PREFIX))
    if len(names)>MAX_EVENTS:raise ManagedWalletError('MANAGED_RECOVERY_CAPACITY')
    secret=read_exact(owner.root,'supervisor.token',length=32)
    profile=sha256(_canonical(owner.profile)).hexdigest()
    rows=[];previous='0'*64
    try:
        for seq,name in enumerate(names,1):
            if name!=f'{PREFIX}{seq:06d}':raise ValueError
            raw=read_exact(owner.root,name)
            row=json.loads(raw.decode('ascii'),object_pairs_hook=_distinct)
            if type(row) is not dict or set(row)!={'schema','seq','profile','wallet_id',
                    'action','state','target_identity','source_anchor','target_anchor','previous','mac'}:
                raise ValueError
            mac=row.pop('mac')
            if (row['schema']!=SCHEMA or type(row['seq']) is not int or row['seq']!=seq
                    or row['profile']!=profile or row['wallet_id']!=wallet_id
                    or type(row['action']) is not str or not re.fullmatch('[0-9a-f]{16}',row['action'])
                    or type(row['target_identity']) is not dict or not _record(row['source_anchor'])
                    or row['previous']!=previous or type(mac) is not str
                    or not re.fullmatch('[0-9a-f]{64}',mac)
                    or not hmac.compare_digest(mac,hmac.digest(secret,
                        SCHEMA.encode()+b'\n'+_canonical(row),'sha256').hex())):raise ValueError
            last=rows[-1] if rows else None
            _transition(row,last)
            row['mac']=mac;rows.append(row);previous=sha256(raw).hexdigest()
    except (OSError,ValueError,TypeError,KeyError,UnicodeError):
        raise ManagedWalletError('MANAGED_RECOVERY_REFERENCE_UNVERIFIED') from None
    return rows,previous


def require_anchor_floor(current,floor):
    if floor is not None and (not _record(list(current) if type(current) is tuple else current)
            or current[0]<floor[0] or current[0]==floor[0] and current[1]!=floor[1]):
        raise ManagedWalletError('MANAGED_RECOVERY_ANCHOR_DIVERGED')


def active_location(owner,wallet_id):
    rows,_=_records(owner,wallet_id)
    if not rows:return owner.directory/'wallet-vault','wallet-runtime.sqlite',None
    last=rows[-1]
    if last['state']!='COMMIT':raise ManagedWalletError('MANAGED_RECOVERY_PENDING')
    folder=owner.directory/('wallet-recovery-'+last['action'])
    if _canonical(directory_identity(folder))!=_canonical(last['target_identity']):
        raise ManagedWalletError('MANAGED_RECOVERY_CONTAINER_CHANGED')
    return folder,'wallet-runtime-recovery-'+last['action']+'.sqlite',last['target_anchor']


def _append(owner,wallet_id,*,action,state,target_identity,source_anchor,target_anchor=None):
    rows,previous=_records(owner,wallet_id)
    if len(rows)>=MAX_EVENTS:raise ManagedWalletError('MANAGED_RECOVERY_CAPACITY')
    if (type(source_anchor) not in (tuple,list) or not _record(list(source_anchor))
            or target_anchor is not None and
               (type(target_anchor) not in (tuple,list) or not _record(list(target_anchor)))):
        raise ManagedWalletError('MANAGED_RECOVERY_TRANSITION_DENIED')
    row={'schema':SCHEMA,'seq':len(rows)+1,'profile':sha256(_canonical(owner.profile)).hexdigest(),
         'wallet_id':wallet_id,'action':action,'state':state,'target_identity':target_identity,
         'source_anchor':list(source_anchor),'target_anchor':list(target_anchor) if target_anchor is not None else None,
         'previous':previous}
    try:
        if (type(action) is not str or not re.fullmatch('[0-9a-f]{16}',action)
                or type(target_identity) is not dict or not _record(row['source_anchor'])):raise ValueError
        _transition(row,rows[-1] if rows else None)
    except (ValueError,TypeError,KeyError):
        raise ManagedWalletError('MANAGED_RECOVERY_TRANSITION_DENIED') from None
    secret=read_exact(owner.root,'supervisor.token',length=32)
    row['mac']=hmac.digest(secret,SCHEMA.encode()+b'\n'+_canonical(row),'sha256').hex()
    create_once(owner.root,f"{PREFIX}{row['seq']:06d}",_canonical(row))
    _records(owner,wallet_id)  # No success follows a divergent publication.


def recover_checkpoint(owner,source,password,*,authorized=False,keychain=None):
    """Explicit copy of exact anchored state to a fresh SAME-wallet container.

    Source ambiguity is preserved, not adopted. This does not complete an
    interrupted recovery-reference transaction or recover a foreign Core.
    """
    _inputs(owner,source,password,authorized)
    from .vault import CheckpointVault
    from .wallet_session import WalletCoreCli
    wallet_id=_read_reference(owner)
    original,_,floor=active_location(owner,wallet_id)
    rows,_=_records(owner,wallet_id)
    if len(rows)>MAX_EVENTS-4:raise ManagedWalletError('MANAGED_RECOVERY_CAPACITY')
    anchor=custody.anchor(wallet_id,keychain)
    ring=scanner=rpc=None
    try:
        with anchor.lease():
            require_recovery_source_equivalence(owner,source,password,anchor)
            current=anchor.read();require_anchor_floor(current,floor)
            if current is None or current[0]>=10**9-1:
                raise ManagedWalletError('MANAGED_RECOVERY_ANCHOR_REQUIRED')
            old=CheckpointVault(original,anchor,source)
            payload=old._load_payload(password,current)
            _require_no_divergent_source(owner,old,current,password,payload)
            rpc=WalletCoreCli(owner.cli,owner.directory);rpc.attest()
            action=secrets.token_hex(8)
            target=owner.directory/('wallet-recovery-'+action)
            runtime=_runtime(owner,'wallet-runtime-recovery-'+action+'.sqlite')
            custody.create_directory(target)  # Existing names never reused.
            identity=directory_identity(target)
            _append(owner,wallet_id,action=action,state='BEGIN',target_identity=identity,source_anchor=current)
            old.backup(target,CheckpointVault._filename(current[0]))
            new=CheckpointVault(target,anchor,source)
            ring,scanner=new.restore(runtime,password,private_windows_runtime=sys.platform=='win32')
            result=_snapshot(ring,scanner,rpc,new)
            durable_core_checkpoint(owner,result['height'],result['tip'])
            new.save(ring,scanner,password)  # Existing create-only publication + native CAS.
            actual=anchor.read()
            if (actual!=new._expected or actual[0]!=current[0]+1
                    or _canonical(directory_identity(target))!=_canonical(identity)):
                raise ManagedWalletError('MANAGED_RECOVERY_TARGET_UNVERIFIED')
            _owned(owner)
            # Close ONLY this recovery's fresh runtime before publishing active
            # reference. All original unknown runtime/sidecar bytes stay intact.
            _close_owned_runtime(ring,scanner,runtime);ring=scanner=None
            _append(owner,wallet_id,action=action,state='COMMIT',target_identity=identity,
                    source_anchor=current,target_anchor=actual)
            result['checkpoint']=list(actual)
            result['explicit_checkpoint_recovery']=True
            return result
    except (OSError,ValueError,RuntimeError,sqlite3.Error,TypeError,KeyError,RecursionError):
        raise ManagedWalletError('MANAGED_RECOVERY_DENIED') from None
    finally:
        if scanner is not None:scanner.close()
        if ring is not None:ring.close()
        if rpc is not None and getattr(rpc,'_transport',None) is not None:rpc._transport.close()


def complete_recovery(owner,source,password,*,action,authorized=False,keychain=None):
    """Explicitly finish ONLY an already native-anchored recovery transaction.

    No anchor write/save, orphan promotion or automatic completion. A repeated
    COMMIT is observational/idempotent only while that exact anchor is current.
    Unknown runtimes or target residue refuse; no failed bytes are removed.
    """
    _inputs(owner,source,password,authorized)
    if type(action) is not str or not re.fullmatch('[0-9a-f]{16}',action):
        raise ManagedWalletError('MANAGED_RECOVERY_ACTION_REQUIRED')
    from .vault import CheckpointVault
    from .wallet_session import WalletCoreCli
    wallet_id=_read_reference(owner)
    rows,_=_records(owner,wallet_id)
    if not rows or rows[-1]['action']!=action:
        raise ManagedWalletError('MANAGED_RECOVERY_ACTION_MISMATCH')
    last=rows[-1];committed=last['state']=='COMMIT'
    if not committed and len(rows)>=MAX_EVENTS:
        raise ManagedWalletError('MANAGED_RECOVERY_CAPACITY')
    target=owner.directory/('wallet-recovery-'+action)
    runtime=_runtime(owner,'wallet-runtime-recovery-'+action+'.sqlite')
    anchor=custody.anchor(wallet_id,keychain)
    ring=scanner=rpc=None
    try:
        with anchor.lease():
            require_recovery_source_equivalence(owner,source,password,anchor)
            actual=anchor.read()
            if (type(actual) not in (tuple,list) or not _record(list(actual))
                    or actual[0]!=last['source_anchor'][0]+1
                    or committed and list(actual)!=last['target_anchor']):
                raise ManagedWalletError('MANAGED_RECOVERY_ANCHOR_DIVERGED')
            def verify_target():
                if _canonical(directory_identity(target))!=_canonical(last['target_identity']):
                    raise ManagedWalletError('MANAGED_RECOVERY_CONTAINER_CHANGED')
                # A complete transaction has exactly the copied source and
                # newly anchored target. Any stage/future/unknown name denies.
                expected={CheckpointVault._filename(last['source_anchor'][0]),
                          CheckpointVault._filename(actual[0])}
                names={p.name for p in target.iterdir()}
                if not expected<=names or names-expected-{'.vault.lock'}:
                    raise ManagedWalletError('MANAGED_RECOVERY_TARGET_AMBIGUOUS')
            verify_target()
            vault=CheckpointVault(target,anchor,source)
            vault._load_payload(password,last['source_anchor'])
            vault._load_payload(password,actual)
            rpc=WalletCoreCli(owner.cli,owner.directory);rpc.attest()
            ring,scanner=vault.restore(runtime,password,private_windows_runtime=sys.platform=='win32')
            result=_snapshot(ring,scanner,rpc,vault)
            _close_owned_runtime(ring,scanner,runtime);ring=scanner=None
            verify_target();_owned(owner)
            if anchor.read()!=actual or vault._expected!=actual or _records(owner,wallet_id)[0]!=rows:
                raise ManagedWalletError('MANAGED_RECOVERY_COMPLETION_CHANGED')
            if not committed:
                _append(owner,wallet_id,action=action,state='COMMIT',
                        target_identity=last['target_identity'],source_anchor=last['source_anchor'],
                        target_anchor=actual)
            active_location(owner,wallet_id)  # Do not return success on divergent publication.
            result.update(checkpoint=list(actual),explicit_recovery_completion=True,
                          completion_already_committed=committed,anchor_advanced=False)
            return result
    except (OSError,ValueError,RuntimeError,sqlite3.Error,TypeError,KeyError,RecursionError):
        raise ManagedWalletError('MANAGED_RECOVERY_COMPLETION_DENIED') from None
    finally:
        if scanner is not None:scanner.close()
        if ring is not None:ring.close()
        if rpc is not None and getattr(rpc,'_transport',None) is not None:rpc._transport.close()
