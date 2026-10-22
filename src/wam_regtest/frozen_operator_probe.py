"""Actual frozen self-executable operator-route acceptance, never source fallback."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def prove_frozen_operator(core):
    if getattr(sys,'frozen',False) is not True:
        raise ValueError('FROZEN_OPERATOR_REAL_EXECUTABLE_REQUIRED')
    from .core import verified_core_paths,_read_cli
    from .core_supervisor import CoreSupervisor
    from .custody import create_directory
    from .index_recovery_probe import _blocks
    from .shutdown_probe import _wallet_witness
    node,cli,receipt=verified_core_paths(core)
    temporary=Path(tempfile.mkdtemp(prefix='wam-frozen-operator-e2e-')).resolve()
    root=temporary/'wam-fusion-core-0123456789abcdef'
    owner=None;children=[];safe=True
    try:
        create_directory(root)
        owner=CoreSupervisor(root,core,authorized=True)
        owner.start();children.append(owner.process)
        directory=owner.directory;prefix=[str(cli),f'-datadir={directory}']
        _read_cli(prefix+['createwallet','test'])
        address=_read_cli(prefix+['-rpcwallet=test','getnewaddress','frozen-operator-original'])
        _read_cli(prefix+['generatetoaddress','101',address],timeout=90)
        before=owner.read.attest();assert before['blocks']==101
        tip=before['bestblockhash'];blocks=_blocks(directory)
        balance=_wallet_witness(owner,'getbalances')
        labels=_wallet_witness(owner,'getaddressesbylabel','frozen-operator-original')
        owner.binding._assert_image();owner.process.kill()
        assert owner.process.wait(timeout=15)!=0
        owner.status();owner.start();children.append(owner.process)
        assert owner.read.attest()['blocks']<101
        owner.shutdown();owner.close_listener();owner.stack.close();owner=None
        binary=Path(sys.executable)
        command=[str(binary),'--recover-owned-regtest-index','--root',str(root),
            '--expected-height','101','--expected-tip',tip,'--confirm-regtest-managed-core']
        if sys.platform=='linux':
            from .linux_runtime import policy
            approved=policy()
            command.extend(['--linux-developer-manifest',approved.manifest_sha256,
                '--linux-root-witness',str(approved.witness)])
        # A fresh application, not PyInstaller's multiprocessing/worker mode.
        # Do not permit ambient Python paths to qualify the executable.
        environment={k:v for k,v in os.environ.items()
            if not k.startswith('_PYI_') and k not in ('PYTHONPATH','PYTHONHOME')}
        environment['PYINSTALLER_RESET_ENVIRONMENT']='1'
        denied=subprocess.run(command,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,env=environment,timeout=60)
        assert denied.returncode==2 and not list(root.glob('supervisor.recovery.*'))
        assert _blocks(directory)==blocks
        safe=False
        accepted=subprocess.run(command+['--confirm-reindex-existing-regtest'],
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
            env=environment,timeout=300)
        assert accepted.returncode==0,'FROZEN_OPERATOR_APPROVED_ENTRY_DENIED'
        safe=True
        assert _blocks(directory)==blocks
        owner=CoreSupervisor(root,core,authorized=True,existing_only=True)
        owner.start();children.append(owner.process)
        info=owner.read.attest()
        assert (info['blocks'],info['bestblockhash'])==(101,tip)
        if 'test' not in _wallet_witness(owner,'listwallets'):
            _wallet_witness(owner,'loadwallet','test')
        assert _wallet_witness(owner,'getbalances')==balance
        assert _wallet_witness(owner,'getaddressesbylabel','frozen-operator-original')==labels
        assert _wallet_witness(owner,'getaddressinfo',address)['ismine'] is True
        assert not _read_cli(prefix+['getrawmempool'])
    finally:
        if owner is not None:
            owner.status()
            if owner.process is not None:owner.shutdown()
            owner.close_listener();owner.stack.close()
        if any(c.poll() is None for c in children):safe=False
        if safe:shutil.rmtree(temporary)
    assert safe and not temporary.exists(),'FROZEN_OPERATOR_CLEANUP_UNVERIFIED'
    assert verified_core_paths(core)[2]==receipt
    return {'status':'ACTUAL_FROZEN_OPERATOR_REINDEX_ENTRY_PASS',
        'platform':receipt['platform'],'frozen_binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
        'missing_approval_exit_code':2,'explicit_approval_exit_code':0,
        'exact_original_101_tip':tip,'same_block_bytes_and_original_core_wallet':True,
        'own_child_processes_reaped':True,'cleanup_verified':True,
        'automatic_broadcast':False,'post_crash_mining':False,'mainnet_allowed':False,
        'source_python_fallback':False,'physical_accepted':False}
