"""Build-boundary source checks, not signing/custody or host attestation.

Read tracked public repository files only. Refuse dirty/staged source and extra
importable modules; preserve user changes. Core/WSP/dependency gates stay separate.
"""
import argparse
from hashlib import sha1,sha256
import json
import os
from pathlib import Path,PurePosixPath
import re
import stat
import subprocess
import sys

SCHEMA='wam-build-source/v1'
TEXT_SUFFIXES={'.py','.sh','.md','.txt','.toml','.yml','.yaml','.json','.h','.cpp','.lock'}
TEXT_NAMES={'LICENSE','.gitattributes','.gitignore'}
# Generated package trees are outputs, never source import roots. The immutable
# WSP checkout is authenticated separately before backend execution and build.
BUILD_OUTPUTS={'.git','wsp-upstream','build','dist','bundle-input','package-output',
    'windows-package-output','linux-package-output','linux-upstream'}


class BuildSourceError(ValueError):
    pass


def _git(root,*args):
    p=subprocess.run(['git','--no-replace-objects','-C',str(root),*args],stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=30)
    if p.returncode or len(p.stdout)>4*1024*1024:raise BuildSourceError('BUILD_SOURCE_GIT_DENIED')
    return p.stdout


def _metadata(s):
    return [s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns]


def _windows_file(path):
    # lstat and CRT fstat can report different cached Windows timestamps after
    # writes. Use ONE native identity/size/write-time API on the locked handle;
    # deny write/delete sharing and hold every parent against reparse changes.
    from . import windows_private_storage as native
    with native.directory_guard(path.parent,private=False):
        handle=native.create(str(path),0x81,1,None,3,0x200000,None)
        if handle in (None,native.INVALID):raise BuildSourceError('BUILD_SOURCE_FILE_DENIED')
        try:
            before=native._metadata(handle);size=before[3]
            if size>128*1024*1024:raise BuildSourceError('BUILD_SOURCE_FILE_DENIED')
            buffer=native.c.create_string_buffer(65536);chunks=[];total=0
            while True:
                got=native.w.DWORD()
                if not native.readfile(handle,buffer,len(buffer),native.c.byref(got),None):
                    raise BuildSourceError('BUILD_SOURCE_FILE_DENIED')
                if not got.value:break
                total+=got.value
                if total>size:raise BuildSourceError('BUILD_SOURCE_CHANGED')
                chunks.append(buffer.raw[:got.value])
            if total!=size or native._metadata(handle)!=before:raise BuildSourceError('BUILD_SOURCE_CHANGED')
            return b''.join(chunks),list(before)
        finally:native.close(handle)


def _file(path):
    if os.name=='nt':return _windows_file(path)
    before=path.lstat()
    if (not stat.S_ISREG(before.st_mode) or before.st_nlink!=1
            or getattr(before,'st_file_attributes',0)&0x400 or before.st_size>128*1024*1024):
        raise BuildSourceError('BUILD_SOURCE_FILE_DENIED')
    with path.open('rb') as stream:
        if _metadata(os.fstat(stream.fileno()))!=_metadata(before):raise BuildSourceError('BUILD_SOURCE_CHANGED')
        raw=stream.read(128*1024*1024+1)
        if _metadata(os.fstat(stream.fileno()))!=_metadata(before):raise BuildSourceError('BUILD_SOURCE_CHANGED')
    if _metadata(path.lstat())!=_metadata(before) or len(raw)!=before.st_size:
        raise BuildSourceError('BUILD_SOURCE_CHANGED')
    return raw,_metadata(before)


def _blob(raw):return sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()


def capture(root):
    """Compare every regular HEAD file to Git's blob independently of index flags.

    Windows text CRLF checkout is permitted only if normalizing those line ends
    yields the exact HEAD blob. Native raw SHA256 is still recorded. No filters,
    textconv, symlinks, submodules or real wallet files are followed.
    """
    try:
        if type(root) is not type(Path()) or not root.is_absolute():raise BuildSourceError('BUILD_SOURCE_ROOT_DENIED')
        root=root.resolve(strict=True)
        if Path(os.fsdecode(_git(root,'rev-parse','--show-toplevel')).strip()).resolve()!=root:
            raise BuildSourceError('BUILD_SOURCE_ROOT_DENIED')
        head=_git(root,'rev-parse','HEAD').decode('ascii').strip()
        if not re.fullmatch('[0-9a-f]{40}',head):raise BuildSourceError('BUILD_SOURCE_HEAD_DENIED')
        _git(root,'diff','--cached','--quiet','--no-ext-diff','--no-textconv','HEAD','--')
        header=_git(root,'cat-file','-p','HEAD').split(b'\n\n',1)[0]
        parents=[line[7:].decode('ascii') for line in header.splitlines() if line.startswith(b'parent ')]
        rows=_git(root,'ls-tree','-rz','--full-tree','HEAD').split(b'\0')[:-1]
        if not 1<=len(rows)<=4096:raise BuildSourceError('BUILD_SOURCE_SIZE_DENIED')
        files={};seen=set();total=0
        for row in rows:
            header,name=row.split(b'\t',1);mode,kind,oid=header.decode('ascii').split()
            name=os.fsdecode(name);parts=PurePosixPath(name)
            if (mode not in ('100644','100755') or kind!='blob' or parts.is_absolute()
                    or '..' in parts.parts or '\\' in name or name.casefold() in seen):raise BuildSourceError('BUILD_SOURCE_TREE_DENIED')
            seen.add(name.casefold())
            path=root.joinpath(*parts.parts)
            for parent in path.parents:
                if parent==root:break
                st=parent.lstat()
                if not stat.S_ISDIR(st.st_mode) or getattr(st,'st_file_attributes',0)&0x400:
                    raise BuildSourceError('BUILD_SOURCE_TREE_DENIED')
            raw,metadata=_file(path);total+=len(raw)
            if total>256*1024*1024:raise BuildSourceError('BUILD_SOURCE_SIZE_DENIED')
            matched=_blob(raw)==oid
            if (not matched and sys.platform=='win32'
                    and (parts.suffix in TEXT_SUFFIXES or parts.name in TEXT_NAMES)
                    and not name.startswith('tests/source_contract/v0.1.11/')):
                matched=_blob(raw.replace(b'\r\n',b'\n'))==oid
            if not matched:raise BuildSourceError('BUILD_SOURCE_DIRTY')
            files[name]={'blob':oid,'sha256':sha256(raw).hexdigest(),'metadata':metadata}
        # PyInstaller discovers importable modules, including ignored .py files.
        # Deny extra code even if git status/assume-unchanged would hide it.
        count=0
        def walk_error(_error):raise BuildSourceError('BUILD_SOURCE_UNVERIFIED')
        for current,directories,names in os.walk(root,followlinks=False,onerror=walk_error):
            base=Path(current)
            if base==root:
                for name in directories:
                    if name in BUILD_OUTPUTS and name!='.git':
                        path=base/name
                        if path.is_symlink() or getattr(path.lstat(),'st_file_attributes',0)&0x400:
                            raise BuildSourceError('BUILD_SOURCE_TREE_DENIED')
                directories[:]=[name for name in directories if name not in BUILD_OUTPUTS]
            if len(base.relative_to(root).parts)>32:raise BuildSourceError('BUILD_SOURCE_SIZE_DENIED')
            for name in (*directories,*names):
                path=base/name;count+=1
                if count>20000:raise BuildSourceError('BUILD_SOURCE_SIZE_DENIED')
                if path.is_symlink() or getattr(path.lstat(),'st_file_attributes',0)&0x400:
                    raise BuildSourceError('BUILD_SOURCE_TREE_DENIED')
                imported=(path.suffix.lower() in ('.py','.pyw','.so','.pyd','.dll','.dylib')
                    or path.suffix.lower()=='.pyc' and '__pycache__' not in path.relative_to(root).parts)
                if imported and path.relative_to(root).as_posix() not in files:
                    raise BuildSourceError('BUILD_SOURCE_UNTRACKED_MODULE')
        if _git(root,'rev-parse','HEAD').decode('ascii').strip()!=head:raise BuildSourceError('BUILD_SOURCE_CHANGED')
        return {'schema':SCHEMA,'checkout_sha':head,'parents':parents,'files':files}
    except BuildSourceError:raise
    except (OSError,ValueError,UnicodeError,subprocess.SubprocessError):
        raise BuildSourceError('BUILD_SOURCE_UNVERIFIED') from None


def verify(root,snapshot):
    if type(snapshot) is not dict or snapshot.get('schema')!=SCHEMA:
        raise BuildSourceError('BUILD_SOURCE_STAMP_DENIED')
    if capture(root)!=snapshot:raise BuildSourceError('BUILD_SOURCE_CHANGED')


def public_receipt(snapshot,*,source_head=None,dispatch=False):
    head=snapshot['checkout_sha'] if source_head is None else source_head
    if (type(head) is not str or not re.fullmatch('[0-9a-f]{40}',head)
            or head!=snapshot['checkout_sha'] and (dispatch or len(snapshot['parents'])!=2 or head not in snapshot['parents'])):
        raise BuildSourceError('BUILD_SOURCE_HEAD_CHECKOUT_DENIED')
    values={k:{'blob':v['blob'],'sha256':v['sha256']} for k,v in snapshot['files'].items()}
    return {'schema':SCHEMA,'checkout_sha':snapshot['checkout_sha'],'source_head_sha':head,'tracked_files':len(values),
        'native_source_inventory_sha256':sha256(json.dumps(values,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        'tracked_source_matches_head':True,'source_unchanged_across_build':True,
        'same_uid_host_tamper_proof':False,'dependency_supply_chain_qualified':False}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('capture','verify'))
    parser.add_argument('--stamp',type=Path,required=True);parser.add_argument('--receipt',type=Path)
    args=parser.parse_args();root=Path.cwd()
    if args.action=='capture':
        snapshot=capture(root)
        public_receipt(snapshot,source_head=os.environ.get('WAM_SOURCE_HEAD'),dispatch=os.environ.get('GITHUB_EVENT_NAME')=='workflow_dispatch')
        with args.stamp.open('x') as output:json.dump(snapshot,output,sort_keys=True)
    else:
        raw,_=_file(args.stamp);snapshot=json.loads(raw)
        verify(root,snapshot)
        if args.receipt:
            with args.receipt.open('x') as output:json.dump(public_receipt(snapshot,source_head=os.environ.get('WAM_SOURCE_HEAD'),dispatch=os.environ.get('GITHUB_EVENT_NAME')=='workflow_dispatch'),output,sort_keys=True,indent=2);output.write('\n')
    print('BUILD_SOURCE_'+args.action.upper()+'_PASS')


if __name__=='__main__':main()
