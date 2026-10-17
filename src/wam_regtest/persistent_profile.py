"""T05: non-activating, read-only persistent REGTEST profile preflight.

A profile receipt is never permission to launch/attach Core, sign, restore, or
access a user's existing wallet. POSIX-only candidate; Windows is refused
until independently qualified with native handle/ACL semantics.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys

SCHEMA = 'wam-fusion-owned-regtest-profile/v1'
MAX_RECEIPT_BYTES = 2048
_FIELDS = frozenset(('schema','network','core_version','genesis_hash',
                     'node_sha256','cli_sha256','profile_id'))


class PersistentProfileError(ValueError):
    """Only fixed, non-sensitive refusal codes are raised."""


def _deny(code):
    raise PersistentProfileError(code)


def _hex(value, digits):
    return type(value) is str and re.fullmatch('[0-9a-f]{'+str(digits)+'}',value) is not None


def _duplicates(pairs):
    result={}
    for key,value in pairs:
        if key in result:_deny('PROFILE_DUPLICATE_FIELD_DENIED')
        result[key]=value
    return result


def _root(root):
    if sys.platform not in ('linux','darwin') or not hasattr(os,'O_NOFOLLOW'):
        _deny('PROFILE_NATIVE_PLATFORM_UNQUALIFIED')
    if type(root) is not type(Path()) or not root.is_absolute() or '..' in root.parts:
        _deny('PROFILE_ABSOLUTE_PATH_REQUIRED')
    if not re.fullmatch(r'wam-fusion-owned-regtest-[0-9a-f]{16}',root.name):
        _deny('PROFILE_OWNED_NAMESPACE_REQUIRED')
    # Inspect but never create/chmod/open an existing user wallet. Refuse
    # symlinks in ancestry; world-writable ancestors require sticky+root owner.
    for ancestor in reversed(root.parents):
        meta=ancestor.lstat()
        if not stat.S_ISDIR(meta.st_mode):
            _deny('PROFILE_ANCESTOR_DENIED')
        if meta.st_mode & (stat.S_IWGRP|stat.S_IWOTH) and not (
                meta.st_uid == 0 and meta.st_mode & stat.S_ISVTX):
            _deny('PROFILE_ANCESTOR_DENIED')
    prior=root.lstat()
    if (not stat.S_ISDIR(prior.st_mode) or prior.st_uid != os.geteuid()
            or stat.S_IMODE(prior.st_mode)!=0o700):
        _deny('PROFILE_ROOT_CUSTODY_DENIED')
    fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    if (os.fstat(fd).st_ino,os.fstat(fd).st_dev)!=(prior.st_ino,prior.st_dev):
        os.close(fd);_deny('PROFILE_ROOT_CHANGED')
    return fd,prior


def inspect_profile(root, *, expected_genesis, expected_node_sha256,
                    expected_cli_sha256):
    """Return public identity only; never attach to or start an actual node."""
    if not all(_hex(value,64) for value in
               (expected_genesis,expected_node_sha256,expected_cli_sha256)):
        _deny('PROFILE_INDEPENDENT_PIN_REQUIRED')
    directory=receipt=None
    try:
        directory,root_before=_root(root)
        receipt=os.open('profile.json',os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,
                        dir_fd=directory)
        before=os.fstat(receipt)
        if (not stat.S_ISREG(before.st_mode) or before.st_uid!=os.geteuid()
                or before.st_nlink!=1 or stat.S_IMODE(before.st_mode)!=0o600
                or not 1<=before.st_size<=MAX_RECEIPT_BYTES):
            _deny('PROFILE_RECEIPT_CUSTODY_DENIED')
        raw=os.read(receipt,MAX_RECEIPT_BYTES+1)
        after=os.fstat(receipt)
        keys=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_nlink')
        if len(raw)!=before.st_size or any(
                getattr(before,k)!=getattr(after,k) for k in keys):
            _deny('PROFILE_RECEIPT_CHANGED')
        current=root.lstat()
        if (current.st_ino,current.st_dev,current.st_mode,current.st_uid)!=(
                root_before.st_ino,root_before.st_dev,root_before.st_mode,root_before.st_uid):
            _deny('PROFILE_ROOT_CHANGED')
        value=json.loads(raw.decode('ascii'),object_pairs_hook=_duplicates)
        if (type(value) is not dict or set(value)!=_FIELDS
                or value.get('schema')!=SCHEMA or value.get('network')!='regtest'
                or value.get('core_version')!='v0.1.11'
                or not _hex(value.get('profile_id'),32)):
            _deny('PROFILE_RECEIPT_SCHEMA_DENIED')
        if (value['genesis_hash']!=expected_genesis
                or value['node_sha256']!=expected_node_sha256
                or value['cli_sha256']!=expected_cli_sha256):
            _deny('PROFILE_TRUST_PINS_MISMATCH')
        # This identity is information, not a launch/security authorization.
        return {'profile_id':value['profile_id'],'network':'regtest',
                'core_version':'v0.1.11','pins_matched':True,
                'persistent_runtime_qualified':False,'attach_authorized':False,
                'signing_authorized':False,'mainnet_allowed':False}
    except PersistentProfileError:
        raise
    except (OSError,TypeError,ValueError,UnicodeError):
        _deny('PROFILE_READ_UNVERIFIED')
    finally:
        if receipt is not None:os.close(receipt)
        if directory is not None:os.close(directory)


def create_disposable_profile(parent, *, expected_genesis, expected_node_sha256,
                              expected_cli_sha256, authorized=False):
    """Create a new public identity receipt, never a chain or wallet.

    Requires an operator-provisioned private parent named specifically for
    Fusion REGTEST profiles. Uses create-once namespace/file, fsync and bounded
    self-inspection. An interrupted creation is *not* silently deleted/reused.
    """
    if authorized is not True:
        _deny('PROFILE_CREATE_EXPLICIT_CONSENT_REQUIRED')
    if not all(_hex(x,64) for x in
               (expected_genesis,expected_node_sha256,expected_cli_sha256)):
        _deny('PROFILE_INDEPENDENT_PIN_REQUIRED')
    if sys.platform not in ('linux','darwin') or not hasattr(os,'O_NOFOLLOW'):
        _deny('PROFILE_NATIVE_PLATFORM_UNQUALIFIED')
    if (type(parent) is not type(Path()) or not parent.is_absolute()
            or parent.name!='wam-fusion-regtest-profiles' or '..' in parent.parts):
        _deny('PROFILE_PRIVATE_PARENT_DENIED')
    try:
        if parent.resolve(strict=True)!=parent:
            _deny('PROFILE_PRIVATE_PARENT_DENIED')
        for ancestor in reversed(parent.parents):
            ancestor_info=ancestor.lstat()
            if (not stat.S_ISDIR(ancestor_info.st_mode)
                    or ancestor_info.st_mode & (stat.S_IWGRP|stat.S_IWOTH)
                    and not (ancestor_info.st_uid==0 and ancestor_info.st_mode & stat.S_ISVTX)):
                _deny('PROFILE_PRIVATE_PARENT_DENIED')
        info=parent.lstat()
    except PersistentProfileError:raise
    except (OSError,ValueError):
        _deny('PROFILE_PRIVATE_PARENT_DENIED')
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.geteuid()
            or stat.S_IMODE(info.st_mode)!=0o700):
        _deny('PROFILE_PRIVATE_PARENT_DENIED')
    directory=None
    try:
        directory=os.open(parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        current=os.fstat(directory)
        if (current.st_dev,current.st_ino)!=(info.st_dev,info.st_ino):
            _deny('PROFILE_PARENT_CHANGED')
        name='wam-fusion-owned-regtest-'+secrets.token_hex(8)
        try:
            os.mkdir(name,0o700,dir_fd=directory)
        except FileExistsError:
            _deny('PROFILE_NEW_NAMESPACE_CONFLICT')
        # No cleanup on failure: never overwrite/reuse a potentially partial
        # receipt or erase user files. The operator must review recovery.
        sub=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,
                    dir_fd=directory)
        try:
            fd=os.open('profile.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,
                       0o600,dir_fd=sub)
            try:
                data={'schema':SCHEMA,'network':'regtest','core_version':'v0.1.11',
                      'genesis_hash':expected_genesis,'node_sha256':expected_node_sha256,
                      'cli_sha256':expected_cli_sha256,'profile_id':secrets.token_hex(16)}
                raw=json.dumps(data,sort_keys=True,separators=(',',':')).encode('ascii')
                if len(raw)>MAX_RECEIPT_BYTES:_deny('PROFILE_RECEIPT_SIZE_DENIED')
                offset=0
                while offset<len(raw):
                    written=os.write(fd,raw[offset:])
                    if written<=0:_deny('PROFILE_RECEIPT_WRITE_DENIED')
                    offset+=written
                os.fsync(fd)
            finally:os.close(fd)
            os.fsync(sub)
        finally:os.close(sub)
        os.fsync(directory)
        root=parent/name
        again=parent.lstat()
        if (again.st_dev,again.st_ino)!=(current.st_dev,current.st_ino):
            _deny('PROFILE_PARENT_CHANGED')
        result=inspect_profile(root,expected_genesis=expected_genesis,
                               expected_node_sha256=expected_node_sha256,
                               expected_cli_sha256=expected_cli_sha256)
        return root,result
    except PersistentProfileError:raise
    except (OSError,ValueError,TypeError):
        _deny('PROFILE_CREATE_UNVERIFIED')
    finally:
        if directory is not None:os.close(directory)
