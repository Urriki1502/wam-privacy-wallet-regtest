"""Literal tracked-Python attestation for explicit native qualification probes.

CI may have untracked JSON/build artifacts. It may NOT change/add Python inputs,
hide tracked edits behind index flags, substitute a merge runtime or import a
different project package. Local qualification requires exact committed source;
Explicitly enumerated non-runtime audit Markdown files are recorded separately.
"""
from hashlib import sha1,sha256
import json
import os
from pathlib import Path
import re
import subprocess
import stat

REPOSITORY='Urriki1502/wam-privacy-wallet-regtest'
LOCAL_AUDIT_DOCUMENTS=frozenset((
    'docs/DEVELOPER_INDEPENDENT_REBUILD_GUIDE.md',
    'docs/INDEPENDENT_RC_AUDIT_56ea3618.md',
    'docs/RC_PACKAGE_CONTENT_VERIFICATION.md',
    'docs/RC_RUNTIME_DEPENDENCY_MATRIX.md',
    'docs/security-audit/WAM_Fusion_PreMainnet_Security_Audit_Charter_2026-11-06.md',
    'docs/security-audit/WAM_Fusion_Security_Remediation_Design_Review_2026-11-06.md',
    'WAM_Fusion_ADR_Gap_Audit_Codex_2026-11-06/WAM_Fusion_ADR_2026-11-06.md',
    'WAM_Fusion_ADR_Gap_Audit_Codex_2026-11-06/WAM_Fusion_Q10_Q20_Gap_Audit_2026-11-06.md',
    'WAM_Fusion_ADR_Gap_Audit_Codex_2026-11-06/WAM_Fusion_Codex_Handoff_2026-11-06.md'))


class ProbeSourceError(ValueError):pass


def local_audit_documents(root,status):
    """Not import inputs: never hide, stage, move or alter the owner's audits."""
    records={}
    for row in status.splitlines():
        if not row.startswith(b'?? '):
            raise ProbeSourceError('Q05_NATIVE_PROBE_CLEAN_SOURCE_REQUIRED')
        name=row[3:].decode('utf8')
        if name not in LOCAL_AUDIT_DOCUMENTS:
            raise ProbeSourceError('Q05_NATIVE_PROBE_CLEAN_SOURCE_REQUIRED')
        path=root/name
        info=path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink!=1
                or os.name!='nt' and info.st_uid!=os.geteuid()
                or info.st_mode&0o111 or path.parent.is_symlink()):
            raise ProbeSourceError('Q05_LOCAL_AUDIT_DOCUMENT_TYPE_DENIED')
        from .build_provenance import _file
        raw,_=_file(path)
        records[name]=sha256(raw).hexdigest()
    return records


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
    non_runtime={}
    if ci:
        candidate=os.environ.get('WAM_SOURCE_HEAD','')
        if (os.environ.get('GITHUB_REPOSITORY')!=REPOSITORY
                or not re.fullmatch('[0-9a-f]{40}',candidate)
                or os.environ.get('GITHUB_SHA',head)!=head):
            raise ProbeSourceError('Q05_CI_SOURCE_CONTEXT_DENIED')
        status=_git(root,'status','--porcelain','--untracked-files=no')
    else:
        # Entirely untracked owner-document folders must be enumerated. Never
        # accept a collapsed directory row or exempt unknown siblings.
        candidate=head;status=_git(root,'status','--porcelain','--untracked-files=all')
        non_runtime=local_audit_documents(root,status)
        # Also compare ALL tracked files with HEAD, independent of Git index
        # flags, and reject untracked importable modules anywhere in the tree.
        from .build_provenance import capture
        capture(root)
        status=b''
    if status:raise ProbeSourceError('Q05_NATIVE_PROBE_CLEAN_SOURCE_REQUIRED')
    digests,normalized=verify_python_tree(root,_tree(root,head),_tree(root,candidate))
    return {'candidate_source_sha':candidate,'checkout_sha':head,'ci_artifacts_allowed':ci,
            'retained_non_runtime_audit_sha256':non_runtime,
            'literal_python_files_verified':len(digests),'python_crlf_normalized':normalized,
            'raw_python_tree_sha256':sha256(json.dumps(digests,sort_keys=True,
                separators=(',',':')).encode()).hexdigest()}
