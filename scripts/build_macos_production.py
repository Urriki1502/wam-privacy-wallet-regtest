"""Build an allowlisted REGTEST wallet plus separately labelled qualification app.

No production E2E claim is inherited from the separate diagnostic executable.
External normal-UI qualification remains mandatory for the distributed bytes.
"""
from pathlib import Path
from hashlib import sha256
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile


def main():
    if sys.platform != 'darwin' or platform.machine() != 'arm64':
        raise ValueError('PRODUCTION_MACOS_ARM64_REQUIRED')
    root = Path.cwd().resolve()
    sys.path.insert(0, str(root/'scripts'))
    from production_packaging import arguments, audit
    from wam_regtest.build_provenance import capture, verify, public_receipt
    from wam_regtest.release_candidate import write_portable_sha256sums
    from wam_regtest.core import verified_core_paths
    from wam_regtest.official_core_v013 import MEMBERS
    base = Path(os.environ.get('WAM_MACOS_OUTPUT_ROOT', str(root/'bundle-input/production-build'))).absolute()
    base.mkdir(parents=True, exist_ok=True)
    core = Path(os.environ.get('WAM_MACOS_CORE_DIR', str(root/'core'))).resolve()
    verified_core_paths(core)
    stage = Path(tempfile.mkdtemp(prefix='production-stage-', dir=root/'bundle-input'))
    stamp = stage/'source.json';snapshot=capture(root)
    stamp.write_text(json.dumps(snapshot,sort_keys=True))
    env = dict(os.environ, WAM_MACOS_CORE_DIR=str(core), WAM_MACOS_OUTPUT_ROOT=str(base/'qualification-only'))
    with (base/'qualification-only.log').open('x') as log:
        subprocess.run(['bash','scripts/build_macos_bundle.sh','--qualification-only'],env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    (base/'qualification-only/NOT_FOR_DISTRIBUTION.json').write_text(json.dumps(dict(artifact_role='qualification-only',production_binary_qualified=False))+'\n')
    stages = re.findall(r'^MACOS_APP_SOURCE_STAGE=(.+)$',(base/'qualification-only.log').read_text(),re.M)
    if len(stages)!=1:raise ValueError('PRODUCTION_QUALIFICATION_SOURCE_STAGE_DENIED')
    data = Path(stages[0]);dist=base/'dist';out=base/'package-output';out.mkdir(mode=0o700)
    command=[sys.executable,'-I','-m','PyInstaller','--noconfirm','--clean','--onedir','--windowed',
        '--distpath',str(dist),'--workpath',str(base/'production-work'),'--specpath',str(stage),
        '--name','WAM Privacy Wallet REGTEST','--osx-bundle-identifier','org.wamcoin.privacywallet.regtest',
        '--icon',str(root/'assets/wam-wallet.icns'),'--paths',str(root/'src'),
        '--collect-submodules','wam_sp','--copy-metadata','coincurve','--hidden-import','coincurve._cffi_backend']
    for src,dst in [(root/'assets/wam-coin-logo.png','branding'),(data/'Q05_BUILD_SOURCE.json','.'),
                    (data/'wsp-source','wsp-source'),(data/'third-party-notices','third-party-notices')]:
        command+=['--add-data',str(src)+':'+dst]
    for name in ('wamd','wam-cli','receipt.json'):command+=['--add-data',str(core/name)+':core']
    command+=arguments(root)+[str(root/'src/wam_regtest/production_entry.py')]
    subprocess.run(command,check=True)
    app=dist/'WAM Privacy Wallet REGTEST.app';binary=app/'Contents/MacOS/WAM Privacy Wallet REGTEST'
    for name,digest in MEMBERS['macos-arm64'].items():
        files=[p for p in app.rglob(name) if p.is_file() and not p.is_symlink()]
        if len(files)!=1:raise ValueError('PRODUCTION_CORE_SHAPE_DENIED')
        shutil.copyfile(core/name,files[0]);files[0].chmod(0o700)
        if sha256(files[0].read_bytes()).hexdigest()!=digest:raise ValueError('PRODUCTION_CORE_BYTES_DENIED')
    subprocess.run(['codesign','--force','--sign','-','--timestamp=none',str(app)],check=True)
    subprocess.run(['codesign','--verify','--deep','--strict',str(app)],check=True)
    for name,digest in MEMBERS['macos-arm64'].items():
        files=[p for p in app.rglob(name) if p.is_file() and not p.is_symlink()]
        if len(files)!=1 or sha256(files[0].read_bytes()).hexdigest()!=digest:raise ValueError('PRODUCTION_CODESIGN_CORE_BYTES_DENIED')
    inventory=audit(binary,app)
    (out/'PRODUCTION_MODULE_INVENTORY.json').write_text(json.dumps(inventory,indent=2)+'\n')
    from wam_regtest.macos_build_layout import frozen_environment
    clean=frozen_environment(os.environ)
    subprocess.run([str(binary),'--check-bundle'],env=clean,cwd=stage,timeout=45,check=True)
    modes=['--ci-q06-bip39-spend','--ci-q05-managed-wallet','--ci-real-core-gui','--ci-ui-layout',
        '--ci-v1-net-shared-regtest','--ci-q04-external-miner','--ci-real-core-wallet-cocoa',
        '--ci-q06-bip39-readonly','--ci-q06-owned-spend','q04-external-miner','linux-wallet','smoke',
        '-m','--core-dir','--check-bundle=1']
    checks=[]
    for mode in modes:
        env=dict(clean,CI='true',WAM_BUILD_SCOPE='full',WAM_QUALIFICATION='1')
        result=subprocess.run([str(binary),mode],env=env,cwd=stage,timeout=15)
        if result.returncode!=64:raise ValueError('PRODUCTION_DEVELOPER_DISPATCH_NOT_DENIED')
        checks.append(dict(mode=mode,returncode=result.returncode))
    (out/'PRODUCTION_DISPATCH_NEGATIVES.json').write_text(json.dumps(checks,indent=2)+'\n')
    subprocess.run(['ditto','-c','-k','--sequesterRsrc','--keepParent',str(app),str(out/'WAM-Privacy-Wallet-REGTEST-macOS-ARM64.app.zip')],check=True)
    subprocess.run([sys.executable,'-I','scripts/create_verified_dmg.py','--app',str(app),'--output',str(out/'WAM-Privacy-Wallet-REGTEST-macOS-ARM64.dmg')],check=True)
    verify(root,snapshot)
    receipt=public_receipt(snapshot)
    record=dict(artifact_role='allowlisted-regtest-wallet',source=receipt,core_sha256=MEMBERS['macos-arm64'],
        wsp_source_commit='ac55f13423620252bdbf848c7e8a280c3b84721e',mainnet_allowed=False,
        production_qualified=False,normal_ui_frozen_e2e='PENDING_EXTERNAL_NORMAL_UI_QUALIFICATION',
        separate_qualification_artifact='qualification-only; does not qualify distributed bytes',
        codesign='ad-hoc unnotarized',files_sha256={p.name:sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.suffix in ('.zip','.dmg')})
    (out/'PRODUCTION_BUILD_RECEIPT.json').write_text(json.dumps(record,indent=2)+'\n')
    write_portable_sha256sums(out)
    print('PRODUCTION_ALLOWLIST_BUILD_PASS_EXTERNAL_NORMAL_UI_QUALIFICATION_PENDING',flush=True)


if __name__=='__main__':main()
