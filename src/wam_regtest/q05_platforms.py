"""Qualification-only adapters selectively reused from Cursor 952e875.

No normal application imports this module. Test root witness is explicit and
never presented as a deployed production authority.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import zipfile
from .custody import create_directory

APPROVED_LINUX_MANIFEST='e77a5745263b8fdbcffdb282af22800b6f7805f033c09f00738e997150a0f806'
class OwnedLifecycleError(ValueError):pass

class PlatformAdapter:
    platform_id=''
    core_trust=''
    core_version='v0.1.11'
    official_signed=False
    gui_mode='none'
    frozen=False

    def enforce_host(self):
        raise OwnedLifecycleError('Q05_OWNED_SESSION_PROBE_SCOPE_DENIED')

    def prepare_trust(self,core_dir,manifest=None,witness=None,*,test_witness=False):
        return None

    def make_anchor(self,root):
        return None

    def teardown(self):
        pass

    def node_name(self):
        return 'wamd.exe' if sys.platform=='win32' else 'wamd'


class DarwinArm64Adapter(PlatformAdapter):
    platform_id='macos-arm64'
    core_trust='official-signed-v0.1.11'
    official_signed=True
    gui_mode='offscreen'

    def enforce_host(self):
        if platform.system()!='Darwin' or platform.machine()!='arm64':
            raise OwnedLifecycleError('Q05_OWNED_SESSION_PROBE_SCOPE_DENIED')

    def make_anchor(self,root):
        keychain=root/'q05-disposable.keychain-db'
        result=subprocess.run(['/usr/bin/security','create-keychain','-p',
            'public-test-only',str(keychain)],capture_output=True,timeout=15)
        if result.returncode:
            raise OwnedLifecycleError('Q05_DISPOSABLE_KEYCHAIN_DENIED')
        return keychain


class WindowsX64Adapter(PlatformAdapter):
    platform_id='windows-x64'
    core_trust='official-signed-v0.1.11'
    official_signed=True
    gui_mode='offscreen'

    def enforce_host(self):
        machine=platform.machine().lower()
        if os.name!='nt' or machine not in ('amd64','x86_64') or sys.maxsize<=2**32:
            raise OwnedLifecycleError('Q05_OWNED_SESSION_PROBE_SCOPE_DENIED')

    def make_anchor(self,root):
        # WindowsCredentialAnchor via custody.anchor; never a macOS keychain.
        return None


class LinuxX64Adapter(PlatformAdapter):
    platform_id='linux-x86_64'
    core_trust='qualified-developer-core-reviewed-manifest'
    official_signed=False
    gui_mode='xcb-xvfb'
    _witness=None

    def enforce_host(self):
        if platform.system()!='Linux' or platform.machine()!='x86_64':
            raise OwnedLifecycleError('Q05_OWNED_SESSION_PROBE_SCOPE_DENIED')

    def prepare_trust(self,core_dir,manifest=None,witness=None,*,test_witness=False):
        pin=manifest or APPROVED_LINUX_MANIFEST
        if pin!=APPROVED_LINUX_MANIFEST:
            raise OwnedLifecycleError('LINUX_APPROVED_MANIFEST_DENIED')
        on_disk=None
        for path in (core_dir/'DEVELOPER_CORE_MANIFEST.json',
                     core_dir/'LINUX_DEVELOPER_CORE_MANIFEST_SHA256.txt',
                     core_dir.parent/'LINUX_DEVELOPER_CORE_MANIFEST_SHA256.txt'):
            if path.is_file() and not path.is_symlink():
                if path.name.endswith('.json'):
                    on_disk=sha256(path.read_bytes()).hexdigest()
                else:
                    on_disk=path.read_text().strip()
                break
        if on_disk is not None and on_disk!=APPROVED_LINUX_MANIFEST:
            raise OwnedLifecycleError('LINUX_QUALIFIED_ARTIFACT_MANIFEST_DENIED')
        endpoint=witness
        if endpoint is None:
            if test_witness is not True:
                raise OwnedLifecycleError('LINUX_ROOT_WITNESS_PREREQUISITE_BLOCKED')
            tests=Path(__file__).resolve().parents[2]/'tests'
            if str(tests) not in sys.path:
                sys.path.insert(0,str(tests))
            os.environ['WAM_ROOT_WITNESS_NATIVE_TESTS']='1'
            from test_linux_anchor_witness import NativeRootWitness
            NativeRootWitness.setUpClass()
            self._witness=NativeRootWitness
            endpoint=NativeRootWitness.root/'anchor.sock'
        from wam_regtest.linux_runtime import configure
        configure(core_dir,APPROVED_LINUX_MANIFEST,endpoint,authorized=True)
        return endpoint

    def make_anchor(self,root):
        return None

    def teardown(self):
        if self._witness is not None:
            try:
                self._witness.tearDownClass()
            finally:
                self._witness=None


def detect_adapter():
    system=platform.system()
    if system=='Darwin':
        return DarwinArm64Adapter()
    if system=='Windows' or os.name=='nt':
        return WindowsX64Adapter()
    if system=='Linux':
        return LinuxX64Adapter()
    raise OwnedLifecycleError('Q05_OWNED_SESSION_PROBE_SCOPE_DENIED')


def stage_windows_core(destination):
    """Hash-verified official Windows x64 Core into a private destination."""
    if os.name!='nt':
        raise OwnedLifecycleError('Q05_WINDOWS_CORE_STAGE_HOST_DENIED')
    from wam_regtest.release import _download_exact
    from wam_regtest.windows_release_preflight import ASSET,ROOT,verify_signed_windows_archive
    from wam_regtest.windows_core_transport import write_new
    destination=destination.expanduser().absolute()
    if destination.exists() or destination.is_symlink():
        raise OwnedLifecycleError('Q05_WINDOWS_CORE_DESTINATION_DENIED')
    create_directory(destination)
    with tempfile.TemporaryDirectory(prefix='wam-q05-win-core-') as temp:
        root=Path(temp)
        files=(
            ('/SIGNING-KEY.asc','SIGNING-KEY.asc',32768),
            ('/downloads/v0.1.11/SHA256SUMS','SHA256SUMS',131072),
            ('/downloads/v0.1.11/SHA256SUMS.asc','SHA256SUMS.asc',16384),
            ('/downloads/v0.1.11/'+ASSET,ASSET,320*1024*1024),
        )
        for remote,name,limit in files:
            _download_exact(remote,limit,root/name)
        proof=verify_signed_windows_archive(
            root/ASSET,root/'SIGNING-KEY.asc',root/'SHA256SUMS',root/'SHA256SUMS.asc')
        if proof.get('signed_archive_verified') is not True:
            raise OwnedLifecycleError('Q05_WINDOWS_SIGNED_ARCHIVE_DENIED')
        with zipfile.ZipFile(root/ASSET) as bundle:
            for filename in ('wamd.exe','wam-cli.exe'):
                write_new(destination,filename,bundle.read(f'{ROOT}/bin/{filename}'))
        write_new(destination,'receipt.json',json.dumps(proof,sort_keys=True).encode('utf8'))
    return proof


