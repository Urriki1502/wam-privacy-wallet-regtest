"""Public build receipts after native E2E, never wallet/runtime authorization."""
from hashlib import sha256
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import platform as host_platform

RC_ID='WAM-Fusion-REGTEST-RC1'
WSP_COMMIT='ac55f13423620252bdbf848c7e8a280c3b84721e'


def write_candidate_manifest(output,platform,core_hashes):
    """Called ONLY after each builder's final executable acceptance succeeds.

    This inventory is not a signature/attestation or a replacement for the
    independent Core pins and workflow logs. PR head and checkout stay distinct.
    """
    if platform not in ('macos-arm64','windows-x64','linux-x86_64-headless','linux-x86_64-desktop'):
        raise ValueError('RC_PLATFORM_DENIED')
    checkout=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    head=os.environ.get('WAM_SOURCE_HEAD',checkout)
    if not all(re.fullmatch('[0-9a-f]{40}',v) for v in (head,checkout)):
        raise ValueError('RC_SOURCE_IDENTITY_DENIED')
    if os.environ.get('GITHUB_EVENT_NAME')=='workflow_dispatch' and head!=checkout:
        raise ValueError('RC_DISPATCH_CHECKOUT_MISMATCH')
    if (type(core_hashes) is not dict or len(core_hashes)!=2
            or any(not re.fullmatch('[0-9a-f]{64}',v) for v in core_hashes.values())):
        raise ValueError('RC_CORE_IDENTITY_DENIED')
    # Public instructions only; never copy a wallet, keychain, config or runtime.
    for name in ('OWNER_REGTEST_ACCEPTANCE.md','DEV_WAM_REVIEW_HANDOFF.md'):
        shutil.copyfile(Path('docs')/name,output/name)
    dependencies={}
    for name in ('PyInstaller','pyinstaller-hooks-contrib','setuptools','packaging','altgraph','PySide6','PySide6_Essentials','PySide6_Addons','shiboken6','qrcode','Pillow','coincurve','cryptography','cffi','pycryptodome'):
        try:dependencies[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:pass
    files={}
    for path in sorted(output.rglob('*')):
        if path.is_symlink():raise ValueError('RC_OUTPUT_SYMLINK_DENIED')
        if not path.is_file() or path.name in ('RELEASE_CANDIDATE_MANIFEST.json','SHA256SUMS.txt'):continue
        if path.name=='wam.conf' or path.suffix in ('.sqlite','.db','.enc','.keychain-db'):
            raise ValueError('RC_PRIVATE_OUTPUT_DENIED')
        files[path.relative_to(output).as_posix()]=sha256(path.read_bytes()).hexdigest()
    run=os.environ.get('GITHUB_RUN_ID')
    record={'schema':'wam-regtest-release-candidate/v1','candidate_id':RC_ID,
        'source_head_sha':head,'checkout_sha':checkout,'single_commit_build':head==checkout,
        'platform':platform,'python_version':sys.version.split()[0],
        'build_os':host_platform.platform(),'network':'regtest','core_sha256':core_hashes,
        'core_provenance':'reviewed-developer-source-build' if platform.startswith('linux') else 'official-signed-v0.1.11',
        'wsp_source_commit':WSP_COMMIT,'dependencies':dependencies,'files_sha256':files,
        'native_final_executable_e2e_pass':True,'mainnet_allowed':False,
        'physical_or_human_acceptance':'PENDING_OPERATOR','dev_wam_reviewed':False,
        'production_qualified':False,'official_final_release':False,
        'github_run_url':f'https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/{run}' if run else None,
        'github_event':os.environ.get('GITHUB_EVENT_NAME'),'artifact_retention_days':14}
    with (output/'RELEASE_CANDIDATE_MANIFEST.json').open('x',encoding='utf8') as stream:
        json.dump(record,stream,sort_keys=True,indent=2);stream.write('\n')
    # Existing per-platform manifests remain intact. All public top-level
    # payloads/inventories/instructions also get conventional portable hashes.
    (output/'SHA256SUMS.txt').write_text(''.join(sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n'
        for p in sorted(output.iterdir()) if p.is_file() and p.name!='SHA256SUMS.txt'),encoding='utf8')
    return record
