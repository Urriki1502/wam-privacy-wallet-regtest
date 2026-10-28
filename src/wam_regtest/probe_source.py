"""Literal tracked-Python attestation for explicit native qualification probes.

CI may have untracked JSON/build artifacts. It may NOT change/add Python inputs,
hide tracked edits behind index flags, substitute a merge runtime or import a
different project package. Local qualification still requires a clean tree.
"""
from hashlib import sha1,sha256
import json
import os
from pathlib import Path
import re
import subprocess

REPOSITORY='Urriki1502/wam-privacy-wallet-regtest'


class ProbeSourceError(ValueError):pass


def _git(root,*args):
    return subprocess.check_output(['git','--no-replace-objects',*args],cwd=root)


def _tree(root,revision):
    result={}
    for row in _git(root,'ls-tree','-r','-z',revision,'--','src','scripts','tests').split(b'\0'):
        if not row:continue
        header,path=row.split(b'\t',1);name=path.decode('utf8')
        if not name.endswith('.py'):continue
        mode,kind,oid=header.decode('ascii').split()
        if mode not in ('100644','100755') or kind!='blob' or not re.fullmatch('[0-9a-f]{40}',oid):
            raise ProbeSourceError('Q05_LITERAL_SOURCE_TREE_DENIED')
        result[name]=oid
    return result


def verify_python_tree(root,checkout,candidate):
    if not checkout or checkout!=candidate:
        raise ProbeSourceError('Q05_CANDIDATE_CHECKOUT_PYTHON_DIFFERS')
    actual={p.relative_to(root).as_posix():p for folder in ('src','scripts','tests')
            for p in (root/folder).rglob('*.py')}
    if set(actual)!=set(checkout):raise ProbeSourceError('Q05_UNTRACKED_PYTHON_INPUT_DENIED')
    digests={};normalized=False
    for name,path in actual.items():
        if path.is_symlink() or not path.is_file():raise ProbeSourceError('Q05_SOURCE_FILE_TYPE_DENIED')
        raw=path.read_bytes()
        def object_id(value):return sha1(b'blob '+str(len(value)).encode()+b'\0'+value).hexdigest()
        if object_id(raw)!=checkout[name]:
            # Python's universal-newline import semantics; record actual raw
            # SHA-256 too. Never normalize binary/Core/vault/password bytes.
            if b'\r\n' not in raw or object_id(raw.replace(b'\r\n',b'\n'))!=checkout[name]:
                raise ProbeSourceError('Q05_LITERAL_SOURCE_BYTES_DENIED')
            normalized=True
        digests[name]=sha256(raw).hexdigest()
    return digests,normalized


def verify_source(root):
    import wam_regtest
    if Path(wam_regtest.__file__).resolve()!=root/'src/wam_regtest/__init__.py':
        raise ProbeSourceError('Q05_IMPORTED_PROJECT_SOURCE_DENIED')
    head=_git(root,'rev-parse','HEAD').decode().strip()
    ci=os.environ.get('GITHUB_ACTIONS')=='true'
    if ci:
        candidate=os.environ.get('WAM_SOURCE_HEAD','')
        if (os.environ.get('GITHUB_REPOSITORY')!=REPOSITORY
                or not re.fullmatch('[0-9a-f]{40}',candidate)
                or os.environ.get('GITHUB_SHA',head)!=head):
            raise ProbeSourceError('Q05_CI_SOURCE_CONTEXT_DENIED')
        status=_git(root,'status','--porcelain','--untracked-files=no')
    else:
        candidate=head;status=_git(root,'status','--porcelain')
    if status:raise ProbeSourceError('Q05_NATIVE_PROBE_CLEAN_SOURCE_REQUIRED')
    digests,normalized=verify_python_tree(root,_tree(root,head),_tree(root,candidate))
    return {'candidate_source_sha':candidate,'checkout_sha':head,'ci_artifacts_allowed':ci,
            'literal_python_files_verified':len(digests),'python_crlf_normalized':normalized,
            'raw_python_tree_sha256':sha256(json.dumps(digests,sort_keys=True,
                separators=(',',':')).encode()).hexdigest()}
