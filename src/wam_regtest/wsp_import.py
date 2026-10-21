"""Source-only native WSP import boundary; never replacement cryptography.

Authenticate literal pinned source before execution and compile those exact
bytes, bypassing mutable interpreter caches. Frozen bundles keep their own
build/source closure; trusted Python/Git/stdlib/application remain assumed.
"""
from importlib.machinery import PathFinder,SourceFileLoader
from pathlib import Path
import re
import subprocess
import sys


class WspImportError(ImportError):
    pass


class _VerifiedWspSourceLoader(SourceFileLoader):
    def __init__(self,name,filename,root):
        super().__init__(name,filename)
        self.source_root=root

    def get_code(self,fullname):
        from .wsp_live import _pinned_source,PINNED_WSP_COMMIT,RealWspScanError
        from .build_provenance import _file,_blob
        try:
            if fullname!=self.name:
                raise WspImportError('WSP_NATIVE_IMPORT_NAME_DENIED')
            member=Path(self.path)
            relative=member.relative_to(self.source_root).as_posix()
            if not relative.startswith('src/wam_sp/') or member.suffix!='.py':
                raise WspImportError('WSP_NATIVE_IMPORT_PATH_DENIED')
            _pinned_source(self.source_root)
            # Bind the actual bytes supplied to compile, not an earlier path
            # read. No bytecode is parsed/deserialized or allowed to execute.
            tree=subprocess.run(['git','--no-replace-objects','-C',str(self.source_root),
                'ls-tree','-z',PINNED_WSP_COMMIT,'--',relative],
                capture_output=True,check=True,timeout=6).stdout
            rows=tree.split(b'\0')
            if len(rows)!=2 or rows[1] or len(tree)>4096:
                raise WspImportError('WSP_NATIVE_IMPORT_BLOB_DENIED')
            header,name=rows[0].split(b'\t',1)
            mode,kind,oid=header.decode('ascii').split()
            if (mode not in ('100644','100755') or kind!='blob'
                    or name.decode('utf8')!=relative
                    or not re.fullmatch('[0-9a-f]{40}',oid)):
                raise WspImportError('WSP_NATIVE_IMPORT_BLOB_DENIED')
            raw,_=_file(member)
            if _blob(raw)!=oid and _blob(raw.replace(b'\r\n',b'\n'))!=oid:
                raise WspImportError('WSP_NATIVE_IMPORT_BYTES_DENIED')
            return compile(raw,self.path,'exec',dont_inherit=True,
                           optimize=sys.flags.optimize)
        except WspImportError:
            raise
        except RealWspScanError as error:
            raise WspImportError(error.args[0]) from None
        except Exception:
            raise WspImportError('WSP_NATIVE_IMPORT_AUTHENTICATION_DENIED') from None


class _VerifiedWspFinder:
    def find_spec(self,fullname,path=None,target=None):
        if fullname!='wam_sp' and not fullname.startswith('wam_sp.'):
            return None
        spec=PathFinder.find_spec(fullname,path,target)
        if (spec is None or type(spec.loader) is not SourceFileLoader
                or type(spec.origin) is not str):
            raise WspImportError('WSP_NATIVE_SOURCE_IMPORT_REQUIRED')
        member=Path(spec.origin)
        if not member.is_absolute():
            raise WspImportError('WSP_NATIVE_IMPORT_PATH_DENIED')
        if fullname=='wam_sp':
            if (member.name!='__init__.py' or member.parent.name!='wam_sp'
                    or member.parent.parent.name!='src'):
                raise WspImportError('WSP_NATIVE_IMPORT_PATH_DENIED')
            root=member.parent.parent.parent
        else:
            parent=sys.modules.get('wam_sp')
            loader=getattr(getattr(parent,'__spec__',None),'loader',None)
            if type(loader) is not _VerifiedWspSourceLoader:
                raise WspImportError('WSP_NATIVE_PARENT_UNVERIFIED')
            root=loader.source_root
        spec.loader=_VerifiedWspSourceLoader(fullname,spec.origin,root)
        return spec


def install_native_wsp_guard():
    if getattr(sys,'frozen',False):
        return
    # A library imported before this trusted application cannot be attested
    # retroactively. Refuse before opening any wallet/custody operation.
    for name,module in tuple(sys.modules.items()):
        if name=='wam_sp' or name.startswith('wam_sp.'):
            if type(getattr(getattr(module,'__spec__',None),'loader',None)) is not _VerifiedWspSourceLoader:
                raise WspImportError('WSP_PREIMPORTED_RUNTIME_DENIED')
    if not any(type(finder) is _VerifiedWspFinder for finder in sys.meta_path):
        sys.meta_path.insert(0,_VerifiedWspFinder())
