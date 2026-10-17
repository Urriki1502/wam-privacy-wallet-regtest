"""Native onedir packages, published only after FINAL executable real E2E.

Headless build environment has no Qt. Desktop is an independent build/job.
Artifacts remain Ubuntu24.04 developer candidates, not portable signed releases.
"""
import argparse
from hashlib import sha256
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile

APPROVED='e77a5745263b8fdbcffdb282af22800b6f7805f033c09f00738e997150a0f806'
CORE={'wamd':'ccc9f0f1d299a1e98a49ff83859aa03e994e83e6ea4b7cd60c327eb1e0e8e4d6',
      'wam-cli':'ada9dabd56d0859b9d64c0b20a05c33cb039b2573f75088443b45c35d5379652'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--core-dir',type=Path,required=True)
    parser.add_argument('--desktop',action='store_true');args=parser.parse_args()
    assert sys.platform=='linux' and platform.machine()=='x86_64'
    if not args.desktop:
        assert importlib.util.find_spec('PySide6') is None,'HEADLESS_BUILD_MUST_HAVE_NO_QT'
    from wam_regtest.package_manifest import stage_pinned_wsp
    from wam_regtest.linux_developer_core import verify,inspect_elf
    from wam_regtest.branding import brand_image
    core=args.core_dir.absolute();verify(core,APPROVED,authorized=True)
    name='wam-regtest-desktop' if args.desktop else 'wam-regtest-headless'
    from wam_regtest.build_provenance import capture,verify as verify_source,public_receipt
    build_source=capture(Path.cwd())
    source_provenance=public_receipt(build_source,source_head=os.environ.get("WAM_SOURCE_HEAD"),dispatch=os.environ.get("GITHUB_EVENT_NAME")=="workflow_dispatch")
    output=Path('linux-package-output');output.mkdir()
    with tempfile.TemporaryDirectory(prefix='wam-linux-package-') as temporary:
        stage=Path(temporary);wsp=stage/'wsp-source'
        stage_pinned_wsp(Path('wsp-upstream').absolute(),wsp)
        command=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir','--noupx',
            '--name',name,'--paths','src','--collect-submodules','wam_regtest',
            '--collect-submodules','wam_sp','--collect-all','coincurve','--hidden-import','_cffi_backend',
            '--add-data',str(core)+':core','--add-data',str(wsp)+':wsp-source',
            '--add-data',str(brand_image())+':branding']
        if not args.desktop:
            for module in ('PySide6','shiboken6','qrcode'):command+=['--exclude-module',module]
        subprocess.run([*command,'src/wam_regtest/linux_package_entry.py'],check=True)
    bundle=Path('dist',name).absolute();binary=bundle/name
    inspect_elf(binary.read_bytes())
    for member,digest in CORE.items():
        files=[p for p in bundle.rglob(member) if p.is_file()]
        assert len(files)==1 and not files[0].is_symlink()
        assert sha256(files[0].read_bytes()).hexdigest()==digest,'FROZEN_CORE_BYTES_CHANGED'
        files[0].chmod(0o700)
    manifests=list(bundle.rglob('DEVELOPER_CORE_MANIFEST.json'))
    assert len(manifests)==1 and sha256(manifests[0].read_bytes()).hexdigest()==APPROVED
    if not args.desktop:
        assert not any('pyside6' in p.as_posix().lower() or 'shiboken' in p.as_posix().lower() for p in bundle.rglob('*'))
    verify_source(Path.cwd(),build_source)
    # Execute final bootloader, bundled Python/WSP/crypto and unchanged Core.
    # Test harness alone provisions its disposable root witness, never the app.
    environment={k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','PYTHONHOME')}
    subprocess.run([sys.executable,'scripts/linux_headless_acceptance.py','--core-dir',str(core),
        '--executable',str(binary),*(['--qt'] if args.desktop else [])],env=environment,check=True,timeout=900)
    evidence=Path('linux-qt-evidence.json' if args.desktop else 'linux-headless-evidence.json')
    verify_source(Path.cwd(),build_source)
    (output/'BUILD_SOURCE_PROVENANCE.json').write_text(json.dumps(source_provenance,sort_keys=True,indent=2)+'\n')
    record=json.loads(evidence.read_text());wallet=record['wallet_live_core']
    assert record['frozen_runtime'] is True
    assert record['platform']=='linux-x86_64' and not record['official_signed_release']
    assert wallet['synthetic_rpc'] is False and wallet['mainnet_allowed'] is False
    # Enumerate links without following arbitrary paths. PyInstaller uses
    # relative internal library links; custody/Core members stay regular files.
    members={};links={}
    for p in sorted(bundle.rglob('*')):
        relative=p.relative_to(bundle).as_posix()
        if p.is_symlink():
            target=os.readlink(p)
            assert not Path(target).is_absolute() and p.resolve(strict=True).is_relative_to(bundle)
            links[relative]=target
        elif p.is_file():members[relative]=sha256(p.read_bytes()).hexdigest()
    head=os.environ['WAM_SOURCE_HEAD'];checkout=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    archive=output/(name+'-linux-x86_64-'+head+'.tar.gz')
    with tarfile.open(archive,'x:gz',dereference=False) as tar:tar.add(bundle,arcname=name)
    manifest={'schema':'wam-regtest-linux-package/v1','source_head_sha':head,'checkout_sha':checkout,
        'platform':'linux-x86_64','build_os':'Ubuntu24.04','frontend':'desktop' if args.desktop else 'headless',
        'wsp_source_commit':'ac55f13423620252bdbf848c7e8a280c3b84721e',
        'approved_core_manifest_sha256':APPROVED,'developer_core_sha256':CORE,
        'bundle_files_sha256':members,'internal_symlinks':links,'archive_name':archive.name,
        'archive_sha256':sha256(archive.read_bytes()).hexdigest(),'final_frozen_executable_e2e_pass':True,
        'e2e_evidence_sha256':sha256(evidence.read_bytes()).hexdigest(),'system_loader_libraries_pinned':True,
        'relocatable_across_linux_distributions_qualified':False,'human_desktop_signoff':False,
        'official_signed_core_release':False,'production_qualified':False,'mainnet_allowed':False,
        'dependencies':{n:importlib.metadata.version(n) for n in
            (('PySide6','qrcode') if args.desktop else ())+('PyInstaller','coincurve','cryptography')}}
    (output/'LINUX_PACKAGE_MANIFEST.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
    shutil.copyfile(evidence,output/evidence.name)
    if args.desktop:
        shutil.copyfile('linux-frozen-managed-core-evidence.json',output/'frozen-managed-core-evidence.json')
    # Public helper source is for explicit administrator review/provisioning.
    shutil.copyfile('src/wam_regtest/linux_anchor_witness.py',output/'root-witness-review-only.py')
    shutil.copyfile('docs/LINUX_ROOT_WITNESS_POLICY.md',output/'ROOT_WITNESS_POLICY.md')
    (output/'SHA256SUMS.txt').write_text(''.join(sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n'
        for p in sorted(output.iterdir()) if p.is_file() and p.name!='SHA256SUMS.txt'))
    from wam_regtest.release_candidate import write_candidate_manifest
    write_candidate_manifest(output,'linux-x86_64-'+('desktop' if args.desktop else 'headless'),CORE)
    print('LINUX_FINAL_FROZEN_'+('DESKTOP' if args.desktop else 'NO_QT_HEADLESS')+'_REAL_WALLET_PASS')


if __name__=='__main__':main()
