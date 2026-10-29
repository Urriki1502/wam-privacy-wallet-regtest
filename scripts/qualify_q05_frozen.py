"""Execute final managed GUI bootloader; no editable wallet/source substitution.

Linux witness is provisioned ONLY by this explicit disposable test harness.
Keep profiles/receipts, including FAIL. Never sweep or repair an old workspace.
"""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import secrets
import subprocess
import sys
import tempfile


def require_receipt(record,executable,source):
    if (record.get('status')!='PASS' or record.get('owner_shutdown_verified') is not True
            or record.get('frozen') is not True or record.get('synthetic_rpc') is not False
            or record.get('mainnet_allowed') is not False or record.get('source_sha')!=source
            or record.get('wsp_source_commit')!='ac55f13423620252bdbf848c7e8a280c3b84721e'
            or record.get('source_provenance',{}).get('frozen_executable_sha256')!=sha256(executable.read_bytes()).hexdigest()
            or record.get('qt_platform')!={'Darwin':'cocoa','Windows':'windows','Linux':'xcb'}.get(platform.system())
            or len(record.get('observations',[]))!=6
            or record['observations'][-1].get('automatic_wallet_replay') is not False):
        raise ValueError('Q05_FINAL_FROZEN_RECEIPT_DENIED')


def main():
    p=argparse.ArgumentParser();p.add_argument('--executable',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    binary=a.executable.absolute();receipt=a.output.absolute()
    if not binary.is_file() or binary.is_symlink() or receipt.exists() or receipt.is_symlink():
        raise ValueError('Q05_FINAL_FROZEN_SCOPE_DENIED')
    source=os.environ.get('WAM_SOURCE_HEAD') or subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    parent=Path(tempfile.mkdtemp(prefix='wam-q05-final-gui-')).absolute()
    root=parent/('wam-fusion-core-'+secrets.token_hex(8))
    args=[str(binary),'--ci-q05-managed-wallet','--root',str(root),'--receipt',str(receipt),
        '--confirm-disposable-regtest']
    env={k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV')
        and not k.startswith(('DYLD_','QT_','QML_'))}
    env['QT_QPA_PLATFORM']={'Darwin':'cocoa','Windows':'windows','Linux':'xcb'}[platform.system()]
    witness=None
    if sys.platform=='win32':
        system=Path(os.environ['SystemRoot']);env['PATH']=str(system/'System32')+os.pathsep+str(system)
        env['QT_SCALE_FACTOR']='1.25'  # Logical scaling, not physical operator acceptance.
    else:env['PATH']='/usr/bin:/bin:/usr/sbin:/sbin'
    try:
        if sys.platform=='linux':
            sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
            os.environ['WAM_ROOT_WITNESS_NATIVE_TESTS']='1'
            from test_linux_anchor_witness import NativeRootWitness
            NativeRootWitness.setUpClass();witness=NativeRootWitness
            args+=['--linux-developer-manifest','e77a5745263b8fdbcffdb282af22800b6f7805f033c09f00738e997150a0f806',
                '--linux-root-witness',str(witness.root/'anchor.sock'),'--qualification-test-witness']
        subprocess.run(args,env=env,cwd=parent,check=True,timeout=420)
        require_receipt(json.loads(receipt.read_text()),binary,source)
        print('Q05_FINAL_FROZEN_MANAGED_GUI_LIFECYCLE_PASS')
    finally:
        if witness is not None:witness.tearDownClass()
        # Intentionally retain the entire managed profile, no rmtree/temp context.


if __name__=='__main__':main()
