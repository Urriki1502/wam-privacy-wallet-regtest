"""Platform-neutral Q05 owned-session START→RESTORE harness.

Adapters isolate Core provenance, OS credential anchors, Popen ownership,
filesystem durability, disposable REGTEST profiles and GUI environment.
WalletSession.open_owned is the single wallet implementation.
"""
from datetime import datetime,timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import secrets
import subprocess
import sys
import tempfile
import zipfile

from wam_regtest.core import _read_cli,verified_core_paths
from wam_regtest.core_supervisor import CoreSupervisor,ManagedCoreError
from wam_regtest.supervisor_store import SupervisorStorageError
from wam_regtest.custody import create_directory,private_temporary_directory
from wam_regtest.rpc_scope import identity
from wam_regtest.wallet_session import WalletSession,WalletSessionError
from wam_regtest.wsp_live import PINNED_WSP_COMMIT,_pinned_source

APPROVED_LINUX_MANIFEST='e77a5745263b8fdbcffdb282af22800b6f7805f033c09f00738e997150a0f806'
PASSWORD=b'public-disposable-q05-native-only'
SCHEMA='q05-owned-session-native/v6'


class OwnedLifecycleError(ValueError):
    pass


def assert_live_original(owner):
    process=owner.process
    scope=identity(owner.directory)
    if (type(process) is not subprocess.Popen or process.poll() is not None
            or owner.binding is None or owner.binding.process is not process
            or owner._faulted or not owner._registered
            or scope is None or scope.binding.process is not process):
        raise OwnedLifecycleError('Q05_ORIGINAL_POPEN_DENIED')
    status=owner.status()
    if not status.get('core_process_owned') or status.get('state') not in ('ready','syncing'):
        raise OwnedLifecycleError('Q05_OWNED_CORE_NOT_READY')
    return process.pid


def stop_owned(owner,record=None):
    """Stop only the original Popen. Never adopt or kill an unknown PID."""
    if owner is None:
        return False
    leftover=False
    process=owner.process
    if process is not None and process.poll() is None:
        try:
            owner.shutdown()
        except (ManagedCoreError,OSError,ValueError,RuntimeError) as error:
            leftover=True
            if record is not None:
                record['owned_shutdown_blocked']=True
                record['owned_shutdown_type']=type(error).__name__
            try:
                owner.recover_stop()
            except (ManagedCoreError,OSError,ValueError,RuntimeError) as recover_error:
                leftover=True
                if record is not None:
                    record['owned_release_blocked']=True
                    record['owned_release_type']=type(recover_error).__name__
    try:
        owner.close()
    except (ManagedCoreError,OSError,ValueError,RuntimeError) as error:
        leftover=True
        if record is not None:
            record['owned_close_blocked']=True
            record['owned_close_type']=type(error).__name__
    if process is not None and process.poll() is None:
        leftover=True
        if record is not None:
            record['surviving_original_core']=True
            record['surviving_original_pid']=process.pid
    return leftover


def _generate_blocks(owner,address,count):
    if type(count) is not int or not 1<=count<=101:
        raise OwnedLifecycleError('Q05_REGTEST_GENERATE_DENIED')
    assert_live_original(owner)
    hashes=_read_cli(
        [str(owner.cli),f'-datadir={owner.directory}','generatetoaddress',str(count),address],
        timeout=120)
    if type(hashes) is not list or len(hashes)!=count:
        raise OwnedLifecycleError('Q05_REGTEST_MATURITY_DENIED')
    assert_live_original(owner)
    return hashes


def _git_head(source):
    return subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()


def _dirty_tracked(source):
    return subprocess.check_output(
        ['git','status','--porcelain','--untracked-files=no'],cwd=source)


class PlatformAdapter:
    platform_id=''
    core_trust=''
    core_version='v0.1.11'
    official_signed=False
    gui_mode='none'
    frozen=False

    def enforce_host(self):
        raise OwnedLifecycleError('Q05_OWNED_SESSION_PROBE_SCOPE_DENIED')

    def prepare_trust(self,core_dir,manifest=None,witness=None):
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

    def prepare_trust(self,core_dir,manifest=None,witness=None):
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
    destination=destination.expanduser().resolve()
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


def _base_record(head,adapter,intake,funded):
    run=os.environ.get('GITHUB_RUN_ID')
    repo=os.environ.get('GITHUB_REPOSITORY','Urriki1502/wam-privacy-wallet-regtest')
    server=os.environ.get('GITHUB_SERVER_URL','https://github.com')
    return {
        'schema':SCHEMA,'status':'FAIL','source_sha':head,'checkout_sha':head,
        'github_sha':os.environ.get('GITHUB_SHA'),
        'github_run_id':run,
        'github_run_url':(f'{server}/{repo}/actions/runs/{run}' if run else None),
        'platform':adapter.platform_id,
        'os':platform.system(),'arch':platform.machine(),
        'frozen':adapter.frozen,'core_trust':adapter.core_trust,
        'core_version':adapter.core_version,
        'core_intake_platform':intake.get('platform'),
        'core_sha256':{},
        'core_release_signature_or_linux_provenance':adapter.core_trust,
        'official_signed_release':adapter.official_signed,
        'wsp_source_commit':PINNED_WSP_COMMIT,'synthetic_rpc':False,
        'fixture_funding':bool(funded),'mainnet_allowed':False,
        'automatic_wallet_transaction_replay':False,'pid_adoption':False,
        'real_popen':False,'real_rpc':False,
        'gui_mode':'none','gui_status':'NOT EXECUTED','frozen_status':'NOT EXECUTED',
        'scenarios':{
            'authentic_core_startup':'NOT EXECUTED',
            'owned_session_create':'NOT EXECUTED',
            'encrypted_checkpoint':'NOT EXECUTED',
            'wallet_restore':'NOT EXECUTED',
            'concurrent_owner_refused':'NOT EXECUTED',
            'real_bip352_receiving':'NOT EXECUTED',
            'sign_broadcast':'NOT EXECUTED',
            'crash_fail_closed':'NOT EXECUTED',
            'same_owner_crash_recovery':'NOT EXECUTED',
            'funded_same_owner_crash_recovery':'NOT EXECUTED',
            'same_owner_reattach':'NOT EXECUTED',
            'dirty_runtime_fail_closed':'NOT EXECUTED',
            'wrong_core_refused':'NOT EXECUTED',
            'interrupted_publication_fail_closed':'NOT EXECUTED',
            'native_gui':'NOT EXECUTED',
            'frozen_build':'NOT EXECUTED',
        },
        'observations':[],
    }


def _gui_lifecycle(session,record,adapter):
    try:
        from wam_regtest.operational_gui import OperationalWalletWindow
        from wam_regtest.desktop import qt_application
    except ImportError:
        record['gui_status']='NOT EXECUTED'
        record['gui_mode']='unavailable'
        record['scenarios']['native_gui']='NOT EXECUTED'
        return
    app=qt_application()
    window=OperationalWalletWindow(session)
    window.show()
    app.processEvents()
    # closeEvent locks the owned session; leave the window open for later lock().
    record['gui_status']='PASS'
    record['gui_mode']=os.environ.get('QT_QPA_PLATFORM') or adapter.gui_mode
    record['scenarios']['native_gui']='PASS'


def _profile_name():
    return f'wam-fusion-core-{secrets.token_hex(8)}'


def _positive_lifecycle(adapter,core,source,root,funded,record,gui):
    stage='CORE_START'
    owner=session=None
    try:
        owner=CoreSupervisor(root,core,authorized=True)
        owner.start(timeout=90)
        pid=assert_live_original(owner)
        if owner.process.pid!=pid or type(owner.process.pid) is not int:
            raise OwnedLifecycleError('Q05_ORIGINAL_POPEN_DENIED')
        record['real_popen']=True
        record['scenarios']['authentic_core_startup']='PASS'
        record['observations'].append({'original_popen_owned':True,'core_pid':pid,
            'wamd_sha256':record.get('core_node_sha256')})
        stage='CREATE_OWNED_SESSION'
        keychain=adapter.make_anchor(root)
        session=WalletSession.open_owned(owner,source,PASSWORD,authorized=True,
                                         create=True,keychain=keychain)
        assert_live_original(owner)
        snap=session.snapshot()
        expected_core=record.get('core_node_sha256')
        if (snap.chain!='regtest' or snap.mainnet_allowed or not snap.signer_allowed
                or type(snap.receive_count) is not int or snap.receive_count!=0
                or snap.history_count!=0
                or (expected_core and snap.core_sha256!=expected_core)):
            raise OwnedLifecycleError('Q05_EMPTY_OWNED_SNAPSHOT_DENIED')
        code=snap.receive_code;digest=snap.core_sha256
        record['real_rpc']=True
        record['scenarios']['owned_session_create']='PASS'
        record['scenarios']['encrypted_checkpoint']='PASS'
        record['observations'].append({'created_empty_owned_session':True,
            'height':snap.height,'history_count':0,'receive_count':0,
            'receive_code_sha256':sha256(code.encode()).hexdigest()})
        if funded:
            stage='PUBLIC_DISPOSABLE_FIXTURE_FUNDING'
            from wam_regtest.wsp_live import _public_fixture_payment,public_regtest_mining_address
            from wam_sp.keystore import Keyring
            address=public_regtest_mining_address(source)
            _generate_blocks(owner,address,101)
            rpc=session._rpc()
            txid,atoms,height=_public_fixture_payment(
                rpc,session.ring.accounts()[0],address)
            funded_snap=session.snapshot()
            if (funded_snap.history_count!=1 or funded_snap.receive_count!=1
                    or funded_snap.confirmed_atoms!=atoms or funded_snap.height!=height):
                raise OwnedLifecycleError('Q05_FUNDED_OWNED_SCAN_DENIED')
            record['scenarios']['real_bip352_receiving']='PASS'
            record['observations'].append({'real_fixture_payment_txid':txid,
                'height':height,'confirmed_atoms':atoms,'history_count':1,
                'receive_count':1})
            stage='OWNED_PREPARE_SIGN_BROADCAST'
            recipient=Keyring()
            try:
                pay=recipient.accounts()[0].payment_code()
            finally:
                recipient.close()
            review=session.prepare(pay,100000,10000)
            session.sign(review.commitment)
            sent=session.broadcast(review.commitment)
            if type(sent) is not str or len(sent)!=64:
                raise OwnedLifecycleError('Q05_OWNED_BROADCAST_DENIED')
            _generate_blocks(owner,address,1)
            paid=session.snapshot()
            seen=tuple(row.txid for row in paid.history)
            spent=100000+10000
            if (paid.history_count<2 or paid.receive_count<1 or sent not in seen
                    or paid.confirmed_atoms!=atoms-spent):
                record['observations'].append({'confirmed_history_observed':True,
                    'history_count':paid.history_count,'receive_count':paid.receive_count,
                    'confirmed_atoms':paid.confirmed_atoms,'broadcast_present':sent in seen})
                raise OwnedLifecycleError('Q05_OWNED_CONFIRMED_HISTORY_DENIED')
            record['scenarios']['sign_broadcast']='PASS'
            record['observations'].append({'genuine_owned_broadcast':True,
                'broadcast_txid':sent,'history_count':paid.history_count,
                'receive_count':paid.receive_count,'confirmed_atoms':paid.confirmed_atoms})
            stage='FUNDED_SAME_OWNER_CRASH_RECOVERY'
            owner,session=_funded_same_owner_crash_recovery(
                owner,session,source,code=code,digest=digest,sent=sent,paid=paid,
                keychain=keychain,record=record)
        if gui:
            stage='NATIVE_GUI'
            _gui_lifecycle(session,record,adapter)
        stage='LOCK_WITHOUT_CORE_SHUTDOWN'
        pid=assert_live_original(owner)
        held=session.snapshot()
        session.lock();session=None
        if owner.process is None or owner.process.poll() is not None or owner.process.pid!=pid:
            raise OwnedLifecycleError('Q05_WALLET_LOCK_STOPPED_CORE')
        assert_live_original(owner)
        record['observations'].append({'wallet_lock_left_core_running':True,'core_pid':pid})
        stage='CONCURRENT_OWNER_WHILE_CORE_LIVE'
        rival=None
        try:
            try:
                rival=CoreSupervisor(root,core,authorized=True)
            except SupervisorStorageError as error:
                if error.args!=('SUPERVISOR_STORAGE_LEASE_BUSY',):
                    raise OwnedLifecycleError('Q05_CONCURRENT_OWNER_WRONG_DENIAL') from error
            else:
                raise OwnedLifecycleError('Q05_CONCURRENT_OWNER_SHOULD_DENY')
        finally:
            if rival is not None and rival.process is None:
                try:
                    rival.close()
                except (ManagedCoreError,OSError,ValueError,RuntimeError):
                    record['concurrent_owner_close_blocked']=True
        if (owner.process is None or owner.process.poll() is not None
                or owner.process.pid!=pid or type(owner.process) is not subprocess.Popen):
            raise OwnedLifecycleError('Q05_CONCURRENT_OWNER_DISTURBED_ORIGINAL')
        assert_live_original(owner)
        record['scenarios']['concurrent_owner_refused']='PASS'
        record['observations'].append({'concurrent_owner_refused':True,
            'second_process_started':False,'original_core_pid':pid,
            'automatic_pid_adoption':False})
        stage='SAME_OWNER_REATTACH'
        session=WalletSession.open_owned(owner,source,PASSWORD,authorized=True,
                                         create=False,keychain=keychain)
        again=session.snapshot()
        if (owner.process is None or type(owner.process) is not subprocess.Popen
                or owner.process.pid!=pid or owner.process.poll() is not None
                or again.receive_code!=held.receive_code
                or again.history_count!=held.history_count
                or again.receive_count!=held.receive_count
                or again.history_sha256!=held.history_sha256
                or again.confirmed_atoms!=held.confirmed_atoms
                or again.core_sha256!=held.core_sha256
                or again.chain!='regtest' or again.mainnet_allowed):
            raise OwnedLifecycleError('Q05_SAME_OWNER_REATTACH_DENIED')
        assert_live_original(owner)
        record['scenarios']['same_owner_reattach']='PASS'
        record['observations'].append({
            'same_owner_reattach':True,'second_daemon':False,
            'original_core_pid':pid,'history_count':again.history_count,
            'history_sha256':again.history_sha256,
        })
        session.lock();session=None
        stage='CORE_REOPEN'
        owner.shutdown();owner.close()
        owner=CoreSupervisor(root,core,authorized=True)
        owner.start(timeout=90)
        assert_live_original(owner)
        stage='RESTORE_OWNED_SESSION'
        session=WalletSession.open_owned(owner,source,PASSWORD,authorized=True,
                                         create=False,keychain=keychain)
        restored=session.snapshot()
        if restored.receive_code!=code or restored.core_sha256!=digest:
            raise OwnedLifecycleError('Q05_OWNED_RESTORE_CONTINUITY_DENIED')
        if not funded:
            if restored.history_count!=0 or restored.receive_count!=0:
                raise OwnedLifecycleError('Q05_OWNED_RESTORE_CONTINUITY_DENIED')
        else:
            if restored.history_count<2 or restored.receive_count<1:
                raise OwnedLifecycleError('Q05_OWNED_FUNDED_RESTORE_DENIED')
        session.lock();session=None
        owner.shutdown();owner.close();owner=None
        record['scenarios']['wallet_restore']='PASS'
        record['observations'].append({'restored_same_payment_code':True,
            'funded_restore':bool(funded)})
        return stage
    except Exception:
        record['failure_stage']=stage
        raise
    finally:
        if session is not None:
            try:
                session.lock()
            except (OSError,ValueError,RuntimeError):
                record['wallet_lock_blocked']=True
        stop_owned(owner,record)


def _fail_closed_dirty_runtime(adapter,core,source,root,record):
    owner=None
    try:
        owner=CoreSupervisor(root,core,authorized=True)
        owner.start(timeout=90)
        assert_live_original(owner)
        sidecar=owner.directory/'wallet-runtime.sqlite-wal'
        sidecar.write_bytes(b'preserve-wal')
        try:
            WalletSession.open_owned(owner,source,PASSWORD,authorized=True,
                                     create=True,keychain=adapter.make_anchor(root))
        except WalletSessionError as error:
            text=str(error)
            if 'EXISTING_RUNTIME' not in text and 'OWNED_OPEN' not in text:
                raise
        else:
            raise OwnedLifecycleError('Q05_DIRTY_RUNTIME_OPEN_SHOULD_DENY')
        if sidecar.read_bytes()!=b'preserve-wal':
            raise OwnedLifecycleError('Q05_DIRTY_RUNTIME_MUTATED')
        record['scenarios']['dirty_runtime_fail_closed']='PASS'
        record['observations'].append({'dirty_runtime_preserved':True,
            'automatic_recovery_allowed':False})
    finally:
        stop_owned(owner,record)


def _fail_closed_interrupted_publication(core,source,root,record):
    from wam_regtest.managed_wallet_checkpoint import publication_ambiguity
    owner=None
    try:
        owner=CoreSupervisor(root,core,authorized=True)
        owner.start(timeout=90)
        assert_live_original(owner)
        runtime=owner.directory/'wallet-runtime.sqlite'
        runtime.write_bytes(b'preserve-runtime')
        row=publication_ambiguity(owner,source,authorized=True)
        if row['automatic_recovery_allowed'] or not row['checkpoint_open_blocked']:
            raise OwnedLifecycleError('Q05_INTERRUPTED_PUBLICATION_SHOULD_BLOCK')
        if runtime.read_bytes()!=b'preserve-runtime':
            raise OwnedLifecycleError('Q05_INTERRUPTED_PUBLICATION_MUTATED')
        record['scenarios']['interrupted_publication_fail_closed']='PASS'
        record['observations'].append({'interrupted_publication_inspect_only':True,
            'automatic_recovery_allowed':False})
    finally:
        stop_owned(owner,record)


def _same_owner_crash_recovery(adapter,core,source,root,record):
    """Restart the exited original Popen. Never adopt a PID or delete evidence."""
    owner=session=None
    try:
        owner=CoreSupervisor(root,core,authorized=True)
        owner.start(timeout=90)
        original_pid=assert_live_original(owner)
        datadir=owner.directory.resolve()
        keychain=adapter.make_anchor(root)
        session=WalletSession.open_owned(owner,source,PASSWORD,authorized=True,
                                         create=True,keychain=keychain)
        snap=session.snapshot()
        code=snap.receive_code
        height=snap.height
        reference=owner.root/'supervisor.wallet'
        reference_bytes=reference.read_bytes()
        vault=owner.directory/'wallet-vault'
        config=owner.directory/'wam.conf'
        config_bytes=config.read_bytes()
        if not vault.is_dir() or vault.is_symlink() or snap.history_count!=0:
            raise OwnedLifecycleError('Q05_CRASH_RECOVERY_VAULT_DENIED')
        session.lock();session=None
        process=owner.process
        if type(process) is not subprocess.Popen or process.pid!=original_pid:
            raise OwnedLifecycleError('Q05_CRASH_RECOVERY_ORIGINAL_POPEN_DENIED')
        process.kill()
        process.wait(timeout=30)
        if process.poll() is None:
            raise OwnedLifecycleError('Q05_CRASH_RECOVERY_ORIGINAL_STILL_LIVE')
        if reference.read_bytes()!=reference_bytes or config.read_bytes()!=config_bytes:
            raise OwnedLifecycleError('Q05_CRASH_RECOVERY_EVIDENCE_MUTATED')
        owner.recover_dead(authorized=True)
        recovered_pid=assert_live_original(owner)
        if (recovered_pid==original_pid or owner.directory.resolve()!=datadir
                or reference.read_bytes()!=reference_bytes
                or config.read_bytes()!=config_bytes or not vault.is_dir()):
            raise OwnedLifecycleError('Q05_CRASH_RECOVERY_IDENTITY_DENIED')
        session=WalletSession.open_owned(owner,source,PASSWORD,authorized=True,
                                         create=False,keychain=keychain)
        restored=session.snapshot()
        if (restored.receive_code!=code or restored.history_count!=0
                or restored.receive_count!=0 or restored.height<height
                or restored.mainnet_allowed or restored.chain!='regtest'):
            raise OwnedLifecycleError('Q05_CRASH_RECOVERY_CONTINUITY_DENIED')
        session.lock();session=None
        owner.shutdown();owner.close();owner=None
        record['scenarios']['same_owner_crash_recovery']='PASS'
        record['observations'].append({
            'same_owner_crash_recovery':True,
            'original_core_pid':original_pid,
            'recovered_core_pid':recovered_pid,
            'datadir_unchanged':True,
            'wallet_reference_preserved':True,
            'automatic_pid_adoption':False,
            'automatic_wallet_transaction_replay':False,
        })
    finally:
        if session is not None:
            try:
                session.lock()
            except (OSError,ValueError,RuntimeError):
                record['wallet_lock_blocked']=True
        stop_owned(owner,record)


def _funded_same_owner_crash_recovery(owner,session,source,*,code,digest,sent,paid,
                                      keychain,record):
    """Restart this funded original Popen and reopen the same wallet.

    The datadir, wallet reference and config stay in place. The confirmed
    spend is not broadcast again. A replacement supervisor is not created.
    """
    pre_count=paid.history_count
    pre_receive=paid.receive_count
    pre_atoms=paid.confirmed_atoms
    pre_height=paid.height
    if (type(sent) is not str or len(sent)!=64 or type(pre_count) is not int
            or pre_count<2 or type(pre_receive) is not int or pre_receive<1
            or type(pre_atoms) is not int or type(pre_height) is not int):
        raise OwnedLifecycleError('Q05_FUNDED_CRASH_RECOVERY_BASELINE_DENIED')
    datadir=owner.directory.resolve()
    original_pid=assert_live_original(owner)
    reference=owner.root/'supervisor.wallet'
    reference_bytes=reference.read_bytes()
    config=owner.directory/'wam.conf'
    config_bytes=config.read_bytes()
    vault=owner.directory/'wallet-vault'
    if not vault.is_dir() or vault.is_symlink():
        raise OwnedLifecycleError('Q05_FUNDED_CRASH_RECOVERY_VAULT_DENIED')
    # Recovery must not accept a chain shorter than the confirmed spend.
    if pre_height>owner._height_snapshot:
        owner._height_snapshot=pre_height
    session.lock()
    process=owner.process
    if type(process) is not subprocess.Popen or process.pid!=original_pid:
        raise OwnedLifecycleError('Q05_FUNDED_CRASH_RECOVERY_ORIGINAL_POPEN_DENIED')
    process.kill()
    process.wait(timeout=30)
    if process.poll() is None:
        raise OwnedLifecycleError('Q05_FUNDED_CRASH_RECOVERY_ORIGINAL_STILL_LIVE')
    if reference.read_bytes()!=reference_bytes or config.read_bytes()!=config_bytes:
        raise OwnedLifecycleError('Q05_FUNDED_CRASH_RECOVERY_EVIDENCE_MUTATED')
    owner.recover_dead(authorized=True)
    recovered_pid=assert_live_original(owner)
    if (recovered_pid==original_pid or owner.directory.resolve()!=datadir
            or reference.read_bytes()!=reference_bytes
            or config.read_bytes()!=config_bytes or not vault.is_dir()):
        raise OwnedLifecycleError('Q05_FUNDED_CRASH_RECOVERY_IDENTITY_DENIED')
    restored_session=WalletSession.open_owned(
        owner,source,PASSWORD,authorized=True,create=False,keychain=keychain)
    try:
        restored=restored_session.snapshot()
        seen=tuple(row.txid for row in restored.history)
        if (restored.receive_code!=code or restored.core_sha256!=digest
                or sent not in seen or seen.count(sent)!=1
                or restored.history_count!=pre_count
                or restored.receive_count!=pre_receive
                or restored.confirmed_atoms!=pre_atoms
                or restored.height<pre_height
                or restored.mainnet_allowed or restored.chain!='regtest'):
            raise OwnedLifecycleError('Q05_FUNDED_CRASH_RECOVERY_CONTINUITY_DENIED')
    except Exception:
        try:
            restored_session.lock()
        except (OSError,ValueError,RuntimeError):
            record['wallet_lock_blocked']=True
        raise
    record['scenarios']['funded_same_owner_crash_recovery']='PASS'
    record['observations'].append({
        'funded_same_owner_crash_recovery':True,
        'original_core_pid':original_pid,
        'recovered_core_pid':recovered_pid,
        'broadcast_txid':sent,
        'history_count':pre_count,
        'confirmed_atoms':pre_atoms,
        'datadir_unchanged':True,
        'wallet_reference_preserved':True,
        'automatic_pid_adoption':False,
        'automatic_wallet_transaction_replay':False,
    })
    return owner,restored_session


def _fail_closed_crash(adapter,core,source,root,record):
    owner=None
    try:
        owner=CoreSupervisor(root,core,authorized=True)
        owner.start(timeout=90)
        assert_live_original(owner)
        session=WalletSession.open_owned(owner,source,PASSWORD,authorized=True,
                                         create=True,keychain=adapter.make_anchor(root))
        session.lock();session=None
        process=owner.process
        process.kill()
        process.wait(timeout=30)
        try:
            owner.close()
        except (ManagedCoreError,OSError,ValueError,RuntimeError) as error:
            record['crash_owner_close_type']=type(error).__name__
        owner=None
        blocked=CoreSupervisor(root,core,authorized=True)
        try:
            try:
                blocked.start(timeout=90)
            except ManagedCoreError:
                record['scenarios']['crash_fail_closed']='PASS'
                record['observations'].append({'crash_dirty_journal_start_denied':True,
                    'automatic_pid_adoption':False})
                return
            raise OwnedLifecycleError('Q05_CRASH_START_SHOULD_DENY')
        finally:
            stop_owned(blocked,record)
            blocked=None
    finally:
        stop_owned(owner,record)


def _refuse_untrusted_core(root,core):
    """Constructor must fail before start. No Popen and no adopted PID."""
    try:
        CoreSupervisor(root,core,authorized=True)
    except (ManagedCoreError,OSError,ValueError,RuntimeError):
        return
    raise OwnedLifecycleError('Q05_WRONG_CORE_SHOULD_DENY')


def _wrong_core_refused(core,root,record):
    receipt=core/'receipt.json'
    before=receipt.read_bytes() if receipt.is_file() else None
    _refuse_untrusted_core(root/'unused-missing-core',root/'missing-core')
    tampered=root/'tampered-core'
    tampered.mkdir(mode=0o700)
    (tampered/'receipt.json').write_text(
        json.dumps({'platform':'untrusted','signed_archive_verified':False,
                    'mainnet_allowed':True,'wamd_sha256':'0'*64,
                    'wam_cli_sha256':'0'*64}),encoding='ascii')
    for name in ('wamd','wam-cli','wamd.exe','wam-cli.exe'):
        (tampered/name).write_bytes(b'not-a-wam-core')
    _refuse_untrusted_core(root/'unused-tampered-core',tampered)
    if receipt.is_file() and receipt.read_bytes()!=before:
        raise OwnedLifecycleError('Q05_WRONG_CORE_MUTATED_REAL_RECEIPT')
    record['scenarios']['wrong_core_refused']='PASS'
    record['observations'].append({
        'wrong_core_directory_refused':True,
        'untrusted_core_directory_refused':True,
        'mainnet_receipt_refused':True,
        'process_started':False,
        'real_core_receipt_unchanged':True,
    })


def run_owned_lifecycle(*,core_dir,wsp_source,root,receipt,confirm,funded,
                        linux_manifest=None,linux_witness=None,gui=False,
                        fail_closed=True):
    source=Path(__file__).resolve().parents[2]
    adapter=detect_adapter()
    if (not confirm or root.exists() or root.is_symlink()
            or receipt.exists() or _dirty_tracked(source)):
        raise OwnedLifecycleError('Q05_OWNED_SESSION_PROBE_SCOPE_DENIED')
    adapter.enforce_host()
    head=_git_head(source)
    expected=os.environ.get('GITHUB_SHA')
    if expected and expected!=head:
        raise OwnedLifecycleError('Q05_OWNED_SESSION_SOURCE_SHA_DENIED')
    record=_base_record(head,adapter,{},funded)
    record['linux_manifest_sha256']=(APPROVED_LINUX_MANIFEST
        if adapter.platform_id=='linux-x86_64' else None)
    stage='TRUST'
    holder=None
    try:
        adapter.prepare_trust(core_dir,linux_manifest,linux_witness)
        node,cli,intake=verified_core_paths(core_dir);_pinned_source(wsp_source)
        record['core_intake_platform']=intake.get('platform')
        try:
            record['core_sha256']={node.name:sha256(node.read_bytes()).hexdigest(),
                                   cli.name:sha256(cli.read_bytes()).hexdigest()}
        except OSError:
            record['core_sha256']={node.name:intake.get('wamd_sha256'),
                                   cli.name:intake.get('wam_cli_sha256')}
        record['core_node_sha256']=intake.get('wamd_sha256')
        holder=private_temporary_directory(prefix='wam-q05-owned-')
        base=Path(holder.name)
        profile=base/_profile_name()
        create_directory(profile)
        _positive_lifecycle(adapter,core_dir,wsp_source,profile,funded,record,gui)
        if fail_closed:
            stage='FAIL_CLOSED'
            dirty=base/_profile_name();create_directory(dirty)
            _fail_closed_dirty_runtime(adapter,core_dir,wsp_source,dirty,record)
            interrupted=base/_profile_name();create_directory(interrupted)
            _fail_closed_interrupted_publication(core_dir,wsp_source,interrupted,record)
            crashed=base/_profile_name();create_directory(crashed)
            _fail_closed_crash(adapter,core_dir,wsp_source,crashed,record)
            recovered=base/_profile_name();create_directory(recovered)
            _same_owner_crash_recovery(adapter,core_dir,wsp_source,recovered,record)
            _wrong_core_refused(core_dir,base/_profile_name(),record)
        required=['authentic_core_startup','owned_session_create','encrypted_checkpoint',
                  'wallet_restore','concurrent_owner_refused','same_owner_reattach']
        if funded:
            required.extend(['real_bip352_receiving','sign_broadcast',
                             'funded_same_owner_crash_recovery'])
        if fail_closed:
            required.extend(['crash_fail_closed','same_owner_crash_recovery',
                             'dirty_runtime_fail_closed',
                             'interrupted_publication_fail_closed','wrong_core_refused'])
        if gui:
            required.append('native_gui')
        if any(record['scenarios'][name]!='PASS' for name in required):
            raise OwnedLifecycleError('Q05_REQUIRED_SCENARIO_INCOMPLETE')
        record['status']='PASS'
    except Exception as error:
        record.setdefault('failure_stage',stage)
        record['failure_type']=type(error).__name__
        code=error.args[0] if getattr(error,'args',None) else type(error).__name__
        record['failure_code']=code
        blocked=(isinstance(error,subprocess.CalledProcessError)
                 and 'sudo' in str(getattr(error,'cmd','')))
        if blocked or code in ('LINUX_ROOT_WITNESS_PREREQUISITE_BLOCKED',
                               'LINUX_EXPLICIT_CORE_AND_WITNESS_POLICY_REQUIRED'):
            record['status']='BLOCKED'
    finally:
        adapter.teardown()
        leftover=bool(record.get('surviving_original_core') or record.get('owned_release_blocked'))
        if holder is not None and record.get('status')=='PASS' and not leftover:
            holder.cleanup()
        elif holder is not None:
            record['failed_profile_retained']=True
            try:
                holder._finalizer.detach()
            except (AttributeError,ValueError):
                holder.cleanup=lambda:None
        record['timestamp_utc']=datetime.now(timezone.utc).isoformat()
        with receipt.open('x') as out:
            json.dump(record,out,indent=2);out.write('\n')
    return record
