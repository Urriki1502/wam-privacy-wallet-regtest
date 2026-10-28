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

from . import custody
from .managed_wallet_checkpoint import (
    ManagedWalletError,_canonical,_inputs,_read_reference,_runtime,_snapshot,
    _owned,_close_owned_runtime,
)
from .supervisor_identity import directory_identity
from .supervisor_protocol import _distinct
from .supervisor_store import create_once,read_exact

SCHEMA='wam-native-wallet-recovery-reference/v1'
MAX_EVENTS=100000
PREFIX='supervisor.recovery.'


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
            current=anchor.read();require_anchor_floor(current,floor)
            if current is None or current[0]>=10**9-1:
                raise ManagedWalletError('MANAGED_RECOVERY_ANCHOR_REQUIRED')
            old=CheckpointVault(original,anchor,source)
            old._load_payload(password,current)  # Authenticate before reference mutation.
            rpc=WalletCoreCli(owner.cli,owner.directory);rpc.attest()
            action=secrets.token_hex(8)
            target=owner.directory/('wallet-recovery-'+action)
            runtime=_runtime(owner,'wallet-runtime-recovery-'+action+'.sqlite')
            custody.create_directory(target)  # Existing names never reused.
            identity=directory_identity(target)
            _append(owner,wallet_id,action=action,state='BEGIN',target_identity=identity,source_anchor=current)
            old.backup(target,CheckpointVault._filename(current[0]))
            new=CheckpointVault(target,anchor,source)
            ring,scanner=new.restore(runtime,password)
            result=_snapshot(ring,scanner,rpc,new)
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
    except (OSError,ValueError,RuntimeError):
        raise ManagedWalletError('MANAGED_RECOVERY_DENIED') from None
    finally:
        if scanner is not None:scanner.close()
        if ring is not None:ring.close()
        if rpc is not None and getattr(rpc,'_transport',None) is not None:rpc._transport.close()
