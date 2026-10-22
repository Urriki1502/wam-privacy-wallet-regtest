"""Explicit, offline-supervisor recovery of an existing owned REGTEST index.

No attached Core, generic RPC, wallet restoration, signing or mining. Immutable
private intent/completion records make interrupted/failed recovery nonpassing.
This journal is not a replacement for native wallet anti-rollback anchors.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
import time

from .supervisor_store import create_once, read_exact

SCHEMA='wam-owned-regtest-index-recovery/v1'
MAX_ATTEMPTS=64


class IndexRecoveryError(ValueError):
    """Fixed public error codes, no secrets or private paths."""


def _target(height,tip):
    if (type(height) is not int or not 1<=height<=100000000
            or type(tip) is not str or re.fullmatch('[0-9a-f]{64}',tip) is None):
        raise IndexRecoveryError('RECOVERY_EXACT_ORIGINAL_CHAIN_REQUIRED')


def _encoded(obj):
    return (json.dumps(obj,sort_keys=True,separators=(',',':'))+'\n').encode('ascii')


def _private_directory(directory):
    # Use the same native directory primitives as supervisor_store. Linux
    # Core/witness policy is independently mandatory at supervisor creation.
    if sys.platform=='win32':
        from .windows_private_storage import directory_guard
        with directory_guard(directory):pass
    else:
        from .supervisor_store import _posix_dir
        with _posix_dir(directory):pass


def _chain_tree(directory):
    # Refuse redirection/hardlinks BEFORE Core's authorized index rebuild.
    # Same-UID/OS compromise can still race paths; no host attestation claim.
    _private_directory(directory)
    count=0
    for entry in directory.rglob('*'):
        count+=1
        if count>20000:
            raise IndexRecoveryError('RECOVERY_CHAIN_TREE_LIMIT_DENIED')
        info=entry.lstat()
        if (stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400
                or not stat.S_ISREG(info.st_mode) and not stat.S_ISDIR(info.st_mode)
                or stat.S_ISREG(info.st_mode) and info.st_nlink!=1):
            raise IndexRecoveryError('RECOVERY_CHAIN_LINK_OR_SPECIAL_FILE_DENIED')
        if sys.platform!='win32' and (info.st_uid!=os.geteuid() or info.st_mode&0o022):
            raise IndexRecoveryError('RECOVERY_CHAIN_OWNER_OR_PERMISSIONS_DENIED')


def pending_recoveries(root,profile):
    from .supervisor_store import _root
    _private_directory(_root(root))
    names=[]
    for entry in root.iterdir():
        if entry.name.startswith('supervisor.recovery.'):
            names.append(entry.name)
            if len(names)>2*MAX_ATTEMPTS:
                raise IndexRecoveryError('RECOVERY_JOURNAL_CAPACITY_DENIED')
    pending=[]
    for name in names:
        if re.fullmatch(r'supervisor\.recovery\.[0-9a-f]{32}\.(intent|complete)',name) is None:
            raise IndexRecoveryError('RECOVERY_JOURNAL_NAME_DENIED')
        if name.endswith('.complete'):
            if name[:-8]+'intent' not in names:
                raise IndexRecoveryError('RECOVERY_JOURNAL_ORPHAN_DENIED')
            continue
        raw=read_exact(root,name)
        try:
            obj=json.loads(raw)
            _target(obj['height'],obj['tip'])
            if (set(obj)!={'schema','profile_id','height','tip','core_sha256','cli_sha256'}
                    or obj['schema']!=SCHEMA or obj['profile_id']!=profile['profile_id']
                    or obj['core_sha256']!=profile['core_sha256']
                    or obj['cli_sha256']!=profile['cli_sha256'] or raw!=_encoded(obj)):
                raise ValueError
        except (ValueError,KeyError,TypeError):
            raise IndexRecoveryError('RECOVERY_JOURNAL_UNVERIFIED') from None
        done=name[:-6]+'complete'
        digest=hashlib.sha256(raw).hexdigest()
        if done in names:
            if read_exact(root,done)!=_encoded({'schema':SCHEMA,'intent_sha256':digest,
                    'exact_chain_verified':True,'clean_owned_shutdown':True}):
                raise IndexRecoveryError('RECOVERY_COMPLETION_UNVERIFIED')
        else:
            pending.append((name,obj,digest))
    return pending


def recover_index(root,core,*,expected_height,expected_tip,authorized_reindex=False,timeout=180):
    # Consent and exact original checkpoint are mandatory before even opening
    # a profile. No implicit acceptance of a low/empty newly indexed chain.
    if authorized_reindex is not True:
        raise IndexRecoveryError('RECOVERY_EXPLICIT_EXISTING_REGTEST_REINDEX_APPROVAL_REQUIRED')
    _target(expected_height,expected_tip)
    if type(timeout) is not int or not 10<=timeout<=240:
        raise IndexRecoveryError('RECOVERY_BOUNDED_TIMEOUT_REQUIRED')
    from .core_supervisor import CoreSupervisor,_reserve_existing_rpc_port,_profile_read
    from .core_process import OwnedCoreBinding
    from .network_policy import local_rpc_port
    # Constructor holds the native profile lease and refuses an active owner,
    # foreign/partial profile, unknown bytes, network or create-new fallback.
    _profile_read(root)  # No lock-file creation in an unknown/external root.
    owner=CoreSupervisor(root,core,authorized=True,existing_only=True)
    child=None
    try:
        from .json_rpc import _private_config
        from .core import verified_core_paths
        profile_before=read_exact(root,'supervisor.profile')
        config_before=_private_config(owner.directory)
        _chain_tree(owner.directory)
        prior=pending_recoveries(root,owner.profile)
        if any((p['height'],p['tip'])!=(expected_height,expected_tip) for _,p,_ in prior):
            raise IndexRecoveryError('RECOVERY_PENDING_TARGET_MISMATCH')
        count=sum(1 for p in root.iterdir() if p.name.startswith('supervisor.recovery.') and p.name.endswith('.intent'))
        if count>=MAX_ATTEMPTS:
            raise IndexRecoveryError('RECOVERY_JOURNAL_CAPACITY_DENIED')
        port=local_rpc_port(owner.directory)
        with _reserve_existing_rpc_port(port):
            pass
        identity=(owner.directory.stat().st_dev,owner.directory.stat().st_ino)
        request={'schema':SCHEMA,'profile_id':owner.profile['profile_id'],
            'height':expected_height,'tip':expected_tip,
            'core_sha256':owner.profile['core_sha256'],'cli_sha256':owner.profile['cli_sha256']}
        name='supervisor.recovery.'+secrets.token_hex(16)+'.intent'
        raw=_encoded(request)
        create_once(root,name,raw)  # fsync BEFORE launching a mutating operation
        if read_exact(root,name)!=raw:
            raise IndexRecoveryError('RECOVERY_INTENT_PUBLICATION_UNVERIFIED')
        prior.append((name,request,hashlib.sha256(raw).hexdigest()))
        owner._state='recovery-needed'
        child=subprocess.Popen([str(owner.node),f'-datadir={owner.directory}',
                '-daemon=0','-reindex=1'],stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
            cwd=owner.node.parent if sys.platform=='win32' else owner.directory,
            env=owner._child_environment(),
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0) if sys.platform=='win32' else 0)
        owner.process=child
        owner.binding=OwnedCoreBinding(child,core,owner.directory,reindex=True)
        deadline=time.monotonic()+timeout
        owner.read=owner._ready(deadline,port)
        while time.monotonic()<deadline:
            info=owner.read.attest()
            if (info['blocks'],info['bestblockhash'])==(expected_height,expected_tip):
                break
            time.sleep(.1)
        else:
            raise IndexRecoveryError('RECOVERY_ORIGINAL_HEIGHT_TIP_NOT_RESTORED')
        if owner.read.call('getblockhash',[expected_height])!=expected_tip:
            raise IndexRecoveryError('RECOVERY_ORIGINAL_CHAIN_NOT_VERIFIED')
        if identity!=(owner.directory.stat().st_dev,owner.directory.stat().st_ino):
            raise IndexRecoveryError('RECOVERY_DATADIR_IDENTITY_CHANGED')
        owner.shutdown()
        if child.poll()!=0:
            raise IndexRecoveryError('RECOVERY_CLEAN_OWNED_SHUTDOWN_UNVERIFIED')
        if (profile_before!=read_exact(root,'supervisor.profile')
                or config_before!=_private_config(owner.directory)
                or verified_core_paths(core)[2]!=owner.receipt):
            raise IndexRecoveryError('RECOVERY_PROFILE_CONFIG_OR_CORE_CHANGED')
        # Only after exact genuine-chain verification and clean shutdown may
        # interrupted attempts with this SAME target be marked complete.
        for intent,_,digest in prior:
            create_once(root,intent[:-6]+'complete',_encoded({'schema':SCHEMA,
                'intent_sha256':digest,'exact_chain_verified':True,'clean_owned_shutdown':True}))
        if pending_recoveries(root,owner.profile):
            raise IndexRecoveryError('RECOVERY_COMPLETION_UNVERIFIED')
        return {'status':'OWNED_REGTEST_EXPLICIT_REINDEX_VERIFIED_STOPPED',
            'height':expected_height,'tip':expected_tip,'core_version':'v0.1.11',
            'wamd_sha256':owner.receipt['wamd_sha256'],'wam_cli_sha256':owner.receipt['wam_cli_sha256'],
            'operator_reindex_approved':True,'same_datadir_identity':True,
            'protected_profile_config_unchanged':True,
            'automatic_broadcast':False,'post_crash_mining':False,'mainnet_allowed':False}
    finally:
        try:
            if owner.process is not None and owner.process.poll() is None:
                owner.shutdown()  # only its verified Popen; NEVER a foreign PID
            if child is not None and child.poll() is None:
                raise IndexRecoveryError('RECOVERY_OWNED_CHILD_CLEANUP_UNVERIFIED')
        finally:
            owner.close_listener()
            owner.stack.close()
        # Failed/interrupted intent files stay; no deletion/retry/reset here.
