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

APPROVED='4052c4a75dee853f5a27c2fb1869aee841a075ed8d6187b90a9d1c06a88cf3c2'
CORE={'wamd':'a3e3bf810e74824e3739fd4cbd1a45037cae997056b8c978c4dc1a61d674f0c7',
      'wam-cli':'d99fc90e3aa4233979056d9981a388360e5d7ff77090d00b9bc37191a2425300'}


def _finish_production(args,name,bundle,binary,output,source_root,source_stamp,wsp_root,wsp_stamp):
    """Distributed Linux bytes: exact allowlist audit, developer argv refusal,
    read-only self-check. No normal-UI/headless E2E is claimed here."""
    from wam_regtest.build_provenance import verify as verify_source,public_receipt
    from production_packaging import audit,DEVELOPER_ARGV
    flavor='linux-desktop'
    inventory=audit(binary,bundle,flavor)
    (output/'PRODUCTION_MODULE_INVENTORY.json').write_text(json.dumps(inventory,indent=2)+'\n')
    clean={k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','PYTHONHOME')}
    hostile=dict(clean,CI='true',GITHUB_ACTIONS='true',WAM_Q06_CI_SPEND_QUALIFY='1',WAM_QUALIFICATION='1')
    checks=[]
    with tempfile.TemporaryDirectory(prefix='wam-linux-production-cwd-') as work:
        check=subprocess.run([str(binary),'--check-bundle'],env=clean,cwd=work,stdin=subprocess.DEVNULL,timeout=120)
        assert check.returncode==0,'LINUX_PRODUCTION_CHECK_BUNDLE_DENIED'
        for argv in DEVELOPER_ARGV:
            result=subprocess.run([str(binary),*argv],env=hostile,cwd=work,stdin=subprocess.DEVNULL,
                capture_output=True,timeout=60)
            assert result.returncode==64,'LINUX_PRODUCTION_DEVELOPER_DISPATCH_NOT_DENIED'
            checks.append({'argv':argv,'returncode':result.returncode})
    (output/'PRODUCTION_DISPATCH_NEGATIVES.json').write_text(json.dumps(checks,indent=2)+'\n')
    members={};links={}
    for p in sorted(bundle.rglob('*')):
        relative=p.relative_to(bundle).as_posix()
        if p.is_symlink():
            target=os.readlink(p)
            assert not Path(target).is_absolute() and p.resolve(strict=True).is_relative_to(bundle)
            links[relative]=target
        elif p.is_file():members[relative]=sha256(p.read_bytes()).hexdigest()
    head=os.environ['WAM_SOURCE_HEAD']
    verify_source(source_root,source_stamp);verify_source(wsp_root,wsp_stamp)
    archive=output/(name+'-linux-x86_64-production-'+head+'.tar.gz')
    with tarfile.open(archive,'x:gz',dereference=False) as tar:tar.add(bundle,arcname=name)
    receipt={'artifact_role':'allowlisted-regtest-wallet','platform':'linux-x86_64','frontend':flavor,
        'source':public_receipt(source_stamp,source_head=head,dispatch=os.environ.get('GITHUB_EVENT_NAME')=='workflow_dispatch'),
        'approved_core_manifest_sha256':APPROVED,'core_sha256':CORE,
        'wsp_source_commit':'ac55f13423620252bdbf848c7e8a280c3b84721e',
        'executable_sha256':sha256(binary.read_bytes()).hexdigest(),'bundle_files_sha256':members,
        'internal_symlinks':links,'archive_name':archive.name,'archive_sha256':sha256(archive.read_bytes()).hexdigest(),
        'production_qualified':False,'normal_ui_frozen_e2e':'PENDING_NATIVE_LINUX_NORMAL_ENTRY_QUALIFICATION',
        'separate_qualification_artifact':'linux-package-output; does not qualify distributed bytes',
        'root_witness_provisioned_by_app':False,'mainnet_allowed':False}
    (output/'PRODUCTION_BUILD_RECEIPT.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    from wam_regtest.release_candidate import write_portable_sha256sums
    write_portable_sha256sums(output)
    print('LINUX_PRODUCTION_ALLOWLIST_BUILD_PASS_'+('DESKTOP' if args.desktop else 'HEADLESS')+'_NORMAL_ENTRY_QUALIFICATION_PENDING')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--core-dir',type=Path,required=True)
    parser.add_argument('--desktop',action='store_true')
    parser.add_argument('--production',action='store_true',
        help='Allowlisted distributed wallet; qualification frozen E2E stays in the default build')
    args=parser.parse_args()
    if args.production and not args.desktop:
        # Six-gate decision B: no headless production spending authority.
        raise SystemExit('LINUX_HEADLESS_PRODUCTION_OUT_OF_SCOPE')
    assert sys.platform=='linux' and platform.machine()=='x86_64'
    from wam_regtest.build_provenance import capture,verify as verify_source,public_receipt
    source_root=Path.cwd();source_stamp=capture(source_root)
    wsp_root=source_root/'wsp-upstream';wsp_stamp=capture(wsp_root)
    if not args.desktop:
        assert importlib.util.find_spec('PySide6') is None,'HEADLESS_BUILD_MUST_HAVE_NO_QT'
    from wam_regtest.package_manifest import stage_pinned_wsp
    from wam_regtest.linux_official_core import verify as verify_core,inspect_elf
    from wam_regtest.branding import brand_image
    core=args.core_dir.absolute();verify_core(core,APPROVED,authorized=True)
    name='wam-regtest-desktop' if args.desktop else 'wam-regtest-headless'
    output=Path('linux-production-output' if args.production else 'linux-package-output');output.mkdir()
    with tempfile.TemporaryDirectory(prefix='wam-linux-package-') as temporary:
        stage=Path(temporary);wsp=stage/'wsp-source'
        from wam_regtest.q05_package_provenance import stage as stage_q05
        q05_source=stage/'Q05_BUILD_SOURCE.json';stage_q05(source_stamp,q05_source)
        stage_pinned_wsp(Path('wsp-upstream').absolute(),wsp)
        from wam_regtest.distribution_notices import stage_distribution_notices
        notices=stage/'third-party-notices'
        stage_distribution_notices(notices,qt=args.desktop)
        if args.production:
            # Positive allowlist and strict production entry; no developer CLI.
            sys.path.insert(0,str(source_root/'scripts'))
            from production_packaging import arguments as production_arguments
            modules=['--distpath','dist-production','--workpath','build-production',
                     *production_arguments(source_root,'linux-desktop')]
            entry='src/wam_regtest/linux_production_entry.py'
        else:
            modules=['--collect-submodules','wam_regtest']
            entry='src/wam_regtest/linux_package_entry.py'
        command=[sys.executable,'-I','-m','PyInstaller','--noconfirm','--clean','--onedir','--noupx',
            '--name',name,'--paths','src',*modules,
            '--collect-submodules','wam_sp','--collect-all','coincurve','--hidden-import','_cffi_backend',
            '--add-data',str(q05_source)+':.','--add-data',str(core)+':core','--add-data',str(wsp)+':wsp-source',
            '--add-data',str(notices)+':third-party-notices',
            '--add-data',str(brand_image())+':branding']
        if not args.desktop:
            for module in ('PySide6','shiboken6','qrcode'):command+=['--exclude-module',module]
        subprocess.run([*command,entry],check=True)
    bundle=Path('dist-production' if args.production else 'dist',name).absolute();binary=bundle/name
    inspect_elf(binary.read_bytes())
    if args.desktop:
        from wam_regtest.qt_bundle_prune import prune_unreferenced_qt
        removed=prune_unreferenced_qt(bundle)
        print('LINUX_QT_UNREFERENCED_REMOVED', len(removed['removed']), flush=True)
        for item in removed['removed']:
            print('LINUX_QT_REMOVED', item, flush=True)
        for item in removed['kept_candidates']:
            print('LINUX_QT_KEPT_REFERENCED', item, flush=True)
    for member,digest in CORE.items():
        files=[p for p in bundle.rglob(member) if p.is_file()]
        assert len(files)==1 and not files[0].is_symlink()
        assert sha256(files[0].read_bytes()).hexdigest()==digest,'FROZEN_CORE_BYTES_CHANGED'
        files[0].chmod(0o700)
    manifests=list(bundle.rglob('LINUX_OFFICIAL_CORE_MANIFEST.json'))
    assert len(manifests)==1 and sha256(manifests[0].read_bytes()).hexdigest()==APPROVED
    if not args.desktop:
        assert not any('pyside6' in p.as_posix().lower() or 'shiboken' in p.as_posix().lower() for p in bundle.rglob('*'))
    if args.production:
        return _finish_production(args,name,bundle,binary,output,source_root,source_stamp,wsp_root,wsp_stamp)
    # Execute final bootloader, bundled Python/WSP/crypto and unchanged Core.
    # Test harness alone provisions its disposable root witness, never the app.
    environment={k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','PYTHONHOME')}
    subprocess.run([sys.executable,'scripts/linux_headless_acceptance.py','--core-dir',str(core),
        '--executable',str(binary),*(['--qt'] if args.desktop else [])],env=environment,check=True,timeout=900)
    # Q04 external-miner coexistence through the frozen executable.
    shutil.copyfile('q04-evidence.json',output/'q04-frozen-evidence.json')
    evidence=Path('linux-qt-evidence.json' if args.desktop else 'linux-headless-evidence.json')
    record=json.loads(evidence.read_text());wallet=record['wallet_live_core']
    assert record['frozen_runtime'] is True
    assert record['platform']=='linux-x86_64' and record['official_signed_release'] is True
    assert wallet['synthetic_rpc'] is False and wallet['mainnet_allowed'] is False
    subprocess.run([sys.executable,'-I','scripts/qualify_q05_frozen.py',
        '--executable',str(binary),'--output',str((output/'q05-frozen-evidence.json').absolute()),
        *([] if args.desktop else ['--headless'])],
        env=environment,check=True,timeout=1200)
    # Q06 always runs in this final frozen executable against reviewed
    # developer Core + separately provisioned disposable root witness.
    subprocess.run([sys.executable,'-I','scripts/qualify_q06_frozen.py',
        '--executable',str(binary),'--output',str((output/'q06-frozen-evidence.json').absolute()),
        *([] if args.desktop else ['--headless'])],
        env=environment,check=True,timeout=1200)
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
    verify_source(source_root,source_stamp);verify_source(wsp_root,wsp_stamp)
    (output/'BUILD_SOURCE_RECEIPT.json').write_text(json.dumps(public_receipt(source_stamp,
        source_head=head,dispatch=os.environ.get('GITHUB_EVENT_NAME')=='workflow_dispatch'),sort_keys=True,indent=2)+'\n')
    archive=output/(name+'-linux-x86_64-'+head+'.tar.gz')
    with tarfile.open(archive,'x:gz',dereference=False) as tar:tar.add(bundle,arcname=name)
    manifest={'schema':'wam-regtest-linux-package/v1','source_head_sha':head,'checkout_sha':checkout,
        'platform':'linux-x86_64','build_os':'Ubuntu24.04','frontend':'desktop' if args.desktop else 'headless',
        'wsp_source_commit':'ac55f13423620252bdbf848c7e8a280c3b84721e',
        'approved_core_manifest_sha256':APPROVED,'official_core_sha256':CORE,
        'bundle_files_sha256':members,'internal_symlinks':links,'archive_name':archive.name,
        'archive_sha256':sha256(archive.read_bytes()).hexdigest(),'final_frozen_executable_e2e_pass':True,
        'e2e_evidence_sha256':sha256(evidence.read_bytes()).hexdigest(),'system_loader_libraries_pinned':True,
        'relocatable_across_linux_distributions_qualified':False,'human_desktop_signoff':False,
        'official_signed_core_release':True,'production_qualified':False,'mainnet_allowed':False,
        'dependencies':{n:importlib.metadata.version(n) for n in
            (('PySide6','qrcode') if args.desktop else ())+('PyInstaller','coincurve','cryptography')}}
    (output/'LINUX_PACKAGE_MANIFEST.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
    shutil.copyfile(evidence,output/evidence.name)
    # Public helper source is for explicit administrator review/provisioning.
    shutil.copyfile('src/wam_regtest/linux_anchor_witness.py',output/'root-witness-review-only.py')
    shutil.copyfile('docs/LINUX_ROOT_WITNESS_POLICY.md',output/'ROOT_WITNESS_POLICY.md')
    from wam_regtest.release_candidate import write_portable_sha256sums
    write_portable_sha256sums(output)
    from wam_regtest.release_candidate import write_candidate_manifest
    write_candidate_manifest(output,'linux-x86_64-'+('desktop' if args.desktop else 'headless'),CORE)
    print('LINUX_FINAL_FROZEN_'+('DESKTOP' if args.desktop else 'NO_QT_HEADLESS')+'_REAL_WALLET_PASS')


if __name__=='__main__':main()
