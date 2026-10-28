"""Bounded genuine Core crash/recovery with the original in-process Popen owner.

This kills only a fresh disposable Core after owned native/image/socket/chain
attestation. It is process-crash injection, not physical power-loss acceptance.
"""
import argparse
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path
import platform
import subprocess

from wam_regtest.core import verified_core_paths
from wam_regtest.core_supervisor import CoreSupervisor
from wam_regtest.custody import create_directory
from wam_regtest.wsp_live import PINNED_WSP_COMMIT


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--core-dir',required=True,type=Path)
    p.add_argument('--root',required=True,type=Path)
    p.add_argument('--receipt',required=True,type=Path)
    p.add_argument('--confirm-disposable-regtest',action='store_true')
    a=p.parse_args();source=Path(__file__).resolve().parents[1]
    if (not a.confirm_disposable_regtest or platform.system()!='Darwin'
            or platform.machine()!='arm64' or a.root.exists() or a.root.is_symlink()
            or a.receipt.exists() or a.receipt.with_suffix('.pre.json').exists()
            or subprocess.check_output(['git','status','--porcelain'],cwd=source)):
        raise SystemExit('Q05_CRASH_PROBE_SCOPE_DENIED')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()
    node,cli,intake=verified_core_paths(a.core_dir)
    record={'source_sha':head,'checkout_sha':head,'status':'FAIL',
        'platform':'macos-arm64','fault_model':'SIGKILL of freshly verified original owned Popen',
        'core_sha256':{x.name:sha256(x.read_bytes()).hexdigest() for x in (node,cli)},
        'core_version':'v0.1.11','core_trust':'official-signed-v0.1.11',
        'wsp_source_commit':PINNED_WSP_COMMIT,'wsp_executed':False,
        'synthetic_rpc':False,'frozen':False,'mainnet_allowed':False,'observations':[]}
    record['source_files']={p:sha256((source/p).read_bytes()).hexdigest() for p in (
        'src/wam_regtest/core_supervisor.py','src/wam_regtest/supervisor_journal.py',
        'src/wam_regtest/supervisor_identity.py','src/wam_regtest/core_process.py',
        'src/wam_regtest/rpc_scope.py','scripts/probe_q05_core_crash.py')}
    create_directory(a.root);owner=CoreSupervisor(a.root,a.core_dir,authorized=True)
    record['lifecycle_schema']=owner.journal.schema
    try:
        owner.start(timeout=30)
        before=owner.status()
        profile=(a.root/'supervisor.profile').read_bytes()
        config=(owner.directory/'wam.conf').read_bytes()
        inode=owner.directory.stat().st_ino
        record['original_core_pid']=owner.process.pid
        record['profile_sha256']=sha256(profile).hexdigest()
        record['config_sha256']=sha256(config).hexdigest()
        record['observations'].append({'before_crash':before})
        if not before['core_process_owned']:raise ValueError('Q05_CRASH_OWNER_UNVERIFIED')
        # Preserve public evidence before the authorized fault. Fresh native
        # ownership/image/endpoint was proven by status; recheck image now.
        owner.binding._assert_image();verified_core_paths(a.core_dir)
        with a.receipt.with_suffix('.pre.json').open('x') as out:json.dump(record,out,indent=2)
        original=owner.process
        original.kill();original.wait(timeout=5)
        failed=owner.status()
        if failed['state']!='recovery-needed' or owner.journal.state!='FAULT':
            raise ValueError('Q05_CRASH_NOT_DIRTY')
        record['observations'].append({'crash_detected':failed})
        owner.recover_dead(authorized=True)
        after=owner.status()
        if (owner.process is original or not after['core_process_owned']
                or after['height']<before['height'] or owner.directory.stat().st_ino!=inode
                or (a.root/'supervisor.profile').read_bytes()!=profile
                or (owner.directory/'wam.conf').read_bytes()!=config):
            raise ValueError('Q05_CRASH_IDENTITY_OR_HEIGHT_DENIED')
        record['observations'].append({'same_owner_explicit_recovery':after})
        owner.shutdown()
        if owner.journal.state!='CLEAN':raise ValueError('Q05_CRASH_SHUTDOWN_NOT_CLEAN')
        owner.close();reopened=CoreSupervisor(a.root,a.core_dir,authorized=True)
        try:
            if reopened.journal.state!='CLEAN' or reopened._faulted:
                raise ValueError('Q05_CRASH_REOPEN_NOT_CLEAN')
            record['observations'].append({'clean_reopen':reopened.status()})
        finally:reopened.close()
        record['status']='PASS'
    except Exception as error:
        record['failure_type']=type(error).__name__
        # Fixed private diagnostics are available separately; never echo args.
        if owner.process is not None and owner.process.poll() is None:
            try:owner.recover_stop()
            except (ValueError,OSError,RuntimeError):record['original_owner_release_blocked']=True
    finally:
        if owner.process is None or owner.process.poll() is not None:owner.close()
        record['timestamp_utc']=datetime.now(timezone.utc).isoformat()
        with a.receipt.open('x') as out:json.dump(record,out,indent=2);out.write('\n')
    print(json.dumps({'status':record['status'],'source_sha':head}))
    return 0 if record['status']=='PASS' else 2


if __name__=='__main__':raise SystemExit(main())
