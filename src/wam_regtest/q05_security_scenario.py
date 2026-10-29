"""Explicit native/frozen safety probes; fresh disposable profiles only.

The contender only attempts the native lease: it never creates or stops Core.
The hostile listener receives no credential bytes. All Core authority stays in
the original in-process Popen; failures retain the profile and original owner.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import socket
import subprocess
import sys
import threading

from .core import verified_core_paths, _read_cli, CoreSmokeError
from .core_process import CoreBindingError
from .core_supervisor import CoreSupervisor
from .custody import create_directory
from .probe_source import verify_source
from .q05_platforms import detect_adapter
from .rpc_scope import quarantine, identity
from .supervisor_store import exclusive_lease, SupervisorStorageError
from .wallet_executor import ManagedWalletBackend
from .wsp_live import _pinned_source, PINNED_WSP_COMMIT


def main(argv=None, *, core=None, source=None, frozen=False):
    p=argparse.ArgumentParser()
    if not frozen:
        p.add_argument('--core-dir',type=Path,required=True)
        p.add_argument('--wsp-source',type=Path,required=True)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--receipt',type=Path,required=True)
    p.add_argument('--confirm-disposable-regtest',action='store_true')
    p.add_argument('--lease-contender',action='store_true')
    p.add_argument('--linux-developer-manifest')
    p.add_argument('--linux-root-witness',type=Path)
    p.add_argument('--qualification-test-witness',action='store_true')
    a=p.parse_args(argv)
    if (not a.confirm_disposable_regtest or not a.root.is_absolute()
            or not re.fullmatch('wam-fusion-core-[0-9a-f]{16}',a.root.name)
            or a.root.is_symlink() or a.root.exists()!=a.lease_contender
            or not a.receipt.is_absolute() or a.receipt.exists() or a.receipt.is_symlink()):
        raise ValueError('Q05_SECURITY_DISPOSABLE_SCOPE_DENIED')
    if frozen:
        from .q05_package_provenance import read
        proof=read();a.core_dir=core;a.wsp_source=source
        if sys.platform=='linux' and (not a.linux_developer_manifest or not a.linux_root_witness):
            raise ValueError('Q05_FROZEN_EXPLICIT_SCOPE_REQUIRED')
    else:proof=verify_source(Path(__file__).resolve().parents[2])
    adapter=detect_adapter();adapter.enforce_host()
    adapter.prepare_trust(a.core_dir,a.linux_developer_manifest,a.linux_root_witness,
                          test_witness=a.qualification_test_witness)
    node,cli,_=verified_core_paths(a.core_dir);_pinned_source(a.wsp_source)
    record={'schema':'q05-security-native/v1','status':'FAIL','source_provenance':proof,
        'source_sha':proof['candidate_source_sha'],'checkout_sha':proof['checkout_sha'],
        'platform':adapter.platform_id,'python_version':sys.version.split()[0],
        'core_version':'v0.1.11','core_trust':adapter.core_trust,
        'core_sha256':{p.name:sha256(p.read_bytes()).hexdigest() for p in (node,cli)},
        'wsp_source_commit':PINNED_WSP_COMMIT,'frozen':frozen,'synthetic_rpc':False,
        'mainnet_allowed':False,'profile_root':str(a.root),'observations':[]}
    owner=None;original=None;control_thread=None;control_errors=[]
    try:
        if a.lease_contender:
            try:
                with exclusive_lease(a.root):pass
            except SupervisorStorageError as error:
                if error.args!=('SUPERVISOR_STORAGE_LEASE_BUSY',):raise
                record['observations'].append({'cross_process_native_lease_busy':True,
                                               'core_started':False})
            else:raise ValueError('Q05_COMPETING_LEASE_ACCEPTED')
        else:
            create_directory(a.root);owner=CoreSupervisor(a.root,a.core_dir,authorized=True)
            owner.start(timeout=30);original=owner.process
            before=owner.status();profile=(a.root/'supervisor.profile').read_bytes()
            config=(owner.directory/'wam.conf').read_bytes()
            datadir=(owner.directory.stat().st_dev,owner.directory.stat().st_ino)
            if not before['core_process_owned']:raise ValueError('Q05_SECURITY_OWNER_DENIED')
            def serve():
                try:owner.serve()
                except OSError:
                    if not owner._release_requested:control_errors.append('CONTROL_LISTENER_FAILED')
            control_thread=threading.Thread(target=serve,name='Q05-qualification-control',daemon=True)
            control_thread.start()
            from .supervisor_client import control
            for _ in range(2):
                state=control(a.root,timeout=10)
                if not state['core_process_owned'] or owner.process is not original:
                    raise ValueError('Q05_AUTHENTICATED_RECONNECT_DENIED')
            events={p.name:sha256(p.read_bytes()).hexdigest() for p in a.root.glob('supervisor.event.*')}
            from .supervisor_protocol import PROTOCOL
            with socket.create_connection(('127.0.0.1',owner.profile['control_port']),timeout=3) as conn:
                with conn.makefile('rb') as reader:hello=json.loads(reader.readline(513))
                bad={'protocol':PROTOCOL,'op':'shutdown','nonce':'a'*32,
                     'challenge':hello['challenge'],'proof':'0'*64}
                conn.sendall(json.dumps(bad).encode('ascii')+b'\n')
                if conn.recv(1)!=b'':raise ValueError('Q05_UNAUTHENTICATED_CONTROL_REPLIED')
            if (events!={p.name:sha256(p.read_bytes()).hexdigest() for p in a.root.glob('supervisor.event.*')}
                    or original.poll() is not None):
                raise ValueError('Q05_UNAUTHENTICATED_CONTROL_MUTATED_OWNER')
            # Same executable/source, no -c or editable replacement in frozen mode.
            child_receipt=a.receipt.with_name(a.receipt.stem+'-contender.json')
            args=[sys.executable]
            if frozen:args+=['--ci-q05-managed-wallet','--scenario','security']
            else:args+=[str(Path(__file__).resolve().parents[2]/'scripts/probe_q05_security.py'),
                '--core-dir',str(a.core_dir),'--wsp-source',str(a.wsp_source)]
            args+=['--root',str(a.root),'--receipt',str(child_receipt),
                   '--confirm-disposable-regtest','--lease-contender']
            if a.linux_root_witness:
                args+=['--linux-root-witness',str(a.linux_root_witness),
                       '--linux-developer-manifest',a.linux_developer_manifest]
            # Linux auto test-witness lives in this parent, pass its endpoint.
            elif sys.platform=='linux' and adapter._witness is not None:
                args+=['--linux-root-witness',str(adapter._witness.root/'anchor.sock'),
                       '--linux-developer-manifest',a.linux_developer_manifest or
                       'e77a5745263b8fdbcffdb282af22800b6f7805f033c09f00738e997150a0f806']
            subprocess.run(args,check=True,timeout=30,stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            child=json.loads(child_receipt.read_text())
            if (child.get('status')!='PASS' or child.get('source_sha')!=record['source_sha']
                    or child.get('observations')!=[{'cross_process_native_lease_busy':True,
                                                   'core_started':False}]):
                raise ValueError('Q05_CONTENDER_RECEIPT_DENIED')
            record['observations'].append({'cross_process_competing_owner_refused':True,
                'authenticated_control_reconnect_same_original_owner':True,
                'wrong_hmac_shutdown_refused_without_journal_mutation':True,
                'receipt_sha256':sha256(child_receipt.read_bytes()).hexdigest()})
            # A different live loopback socket cannot impersonate original Core.
            with socket.socket() as server:
                server.bind(('127.0.0.1',0));server.listen(1);server.settimeout(3)
                with socket.create_connection(server.getsockname(),timeout=3) as probe:
                    peer,_=server.accept()
                    with peer:
                        try:owner.binding.assert_socket(probe)
                        except CoreBindingError as error:
                            if error.args!=('RPC_ENDPOINT_OWNER_DENIED',):raise
                        else:raise ValueError('Q05_HOSTILE_ENDPOINT_ACCEPTED')
                        probe.shutdown(socket.SHUT_WR)
                        if peer.recv(1)!=b'':raise ValueError('Q05_HOSTILE_ENDPOINT_RECEIVED_BYTES')
            record['observations'].append({'hostile_loopback_endpoint_refused_before_auth':True,
                                           'credential_bytes_sent':0})
            if (owner.process is not original or original.poll() is not None
                    or (a.root/'supervisor.profile').read_bytes()!=profile
                    or (owner.directory/'wam.conf').read_bytes()!=config
                    or (owner.directory.stat().st_dev,owner.directory.stat().st_ino)!=datadir):
                raise ValueError('Q05_SECURITY_IDENTITY_MUTATED')
            # Exercise the actual recently fixed backend route against real Core.
            quarantine(owner.directory)
            try:_read_cli([str(cli),f'-datadir={owner.directory}','getblockcount'])
            except CoreSmokeError as error:
                if error.args!=('CORE_RPC_SCOPE_FAULTED',):raise
            else:raise ValueError('Q05_QUARANTINED_RPC_ACCEPTED')
            if owner._faulted or not identity(owner.directory).faulted:
                raise ValueError('Q05_QUARANTINE_STATE_NOT_EXERCISED')
            backend=ManagedWalletBackend(a.root,a.core_dir,a.wsp_source);backend.owner=owner
            backend.execute('quit',(),{})
            if original.poll() is None or owner.process is not None:
                raise ValueError('Q05_QUARANTINED_OWNER_STILL_ALIVE')
            record['observations'].append({'quarantined_rpc_refused':True,
                'supervisor_latch_was_false':True,'explicit_original_backend_quit_verified':True,
                'original_popen_exit_code':original.returncode,'automatic_transaction_replay':False})
        record['status']='PASS'
    except Exception as error:
        record['failure_type']=type(error).__name__
        # No arbitrary exception text, credentials or paths enter public evidence.
    finally:
        if owner is not None and owner.process is not None and owner.process.poll() is None:
            try:owner.recover_stop()
            except (OSError,ValueError,RuntimeError):record['original_owner_retained']=True
        safe=owner is None or owner.process is None or owner.process.poll() is not None
        if owner is not None and safe:
            try:owner.close()
            except (OSError,ValueError,RuntimeError):safe=False
        if control_thread is not None and safe:
            control_thread.join(4)
            if control_thread.is_alive() or control_errors:
                safe=False;record['status']='FAIL';record['control_exit_unverified']=True
        record['owner_shutdown_verified']=safe
        if safe:adapter.teardown()
        record['timestamp_utc']=datetime.now(timezone.utc).isoformat()
        with a.receipt.open('x') as out:json.dump(record,out,indent=2);out.write('\n')
    print(json.dumps({'status':record['status'],'source_sha':record['source_sha']}))
    return 0 if record['status']=='PASS' and safe else 2
