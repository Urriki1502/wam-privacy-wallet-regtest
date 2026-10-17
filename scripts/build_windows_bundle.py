"""Native Win64 PyInstaller onedir recipe; package real-wallet acceptance required.

Reuses only build tactics from legacy PR170/206, never their GUI-only acceptance.
Original owner-supplied PNG -> ICO conversion; no substituted/generated artwork.
"""
from hashlib import sha256
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile


def main():
    assert sys.platform=='win32' and platform.machine().lower() in ('amd64','x86_64')
    from wam_regtest.windows_release_preflight import ASSET,BINARY_SHA256,verify_signed_windows_archive,_validate_amd64_pe
    from wam_regtest.release import _download_exact
    from wam_regtest.package_manifest import stage_pinned_wsp
    from wam_regtest.branding import brand_image
    source=Path('wsp-upstream').absolute()
    assert subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()=='ac55f13423620252bdbf848c7e8a280c3b84721e'
    from wam_regtest.build_provenance import capture,verify as verify_source,public_receipt
    build_source=capture(Path.cwd())
    source_provenance=public_receipt(build_source,source_head=os.environ.get("WAM_SOURCE_HEAD"),dispatch=os.environ.get("GITHUB_EVENT_NAME")=="workflow_dispatch")
    output=Path('windows-package-output');output.mkdir()
    with tempfile.TemporaryDirectory(prefix='wam-win-build-') as t:
        stage=Path(t);core=stage/'core';core.mkdir()
        for remote,name,limit in (
            ('/SIGNING-KEY.asc','SIGNING-KEY.asc',32768),
            ('/downloads/v0.1.11/SHA256SUMS','SHA256SUMS',131072),
            ('/downloads/v0.1.11/SHA256SUMS.asc','SHA256SUMS.asc',16384),
            ('/downloads/v0.1.11/'+ASSET,ASSET,320*1024*1024)):
            _download_exact(remote,limit,stage/name)
        receipt=verify_signed_windows_archive(stage/ASSET,stage/'SIGNING-KEY.asc',stage/'SHA256SUMS',stage/'SHA256SUMS.asc')
        from wam_regtest.windows_release_preflight import ROOT
        with zipfile.ZipFile(stage/ASSET) as z:
            for name,digest in BINARY_SHA256.items():
                payload=z.read(ROOT+'/bin/'+name);assert sha256(payload).hexdigest()==digest
                (core/name).write_bytes(payload)
        (core/'receipt.json').write_text(json.dumps(receipt,sort_keys=True))
        wsp=stage/'wsp-source';stage_pinned_wsp(source,wsp)
        from PIL import Image
        icon=stage/'wam-wallet.ico'
        with Image.open(brand_image()) as image:
            image.save(icon,format='ICO',sizes=[(n,n) for n in (16,24,32,48,64,128,256)])
        subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir','--windowed',
            '--name','WAM-Privacy-Wallet-REGTEST','--icon',str(icon),'--paths','src',
            '--collect-submodules','wam_regtest','--collect-submodules','wam_sp',
            '--collect-all','coincurve','--hidden-import','_cffi_backend',
            '--add-data',str(core)+':core','--add-data',str(wsp)+':wsp-source',
            '--add-data',str(brand_image())+':branding','src/wam_regtest/windows_package_entry.py'],check=True)
    bundle=Path('dist/WAM-Privacy-Wallet-REGTEST').absolute()
    executable=bundle/'WAM-Privacy-Wallet-REGTEST.exe'
    _validate_amd64_pe(executable.read_bytes())
    for name,digest in BINARY_SHA256.items():
        matches=[p for p in bundle.rglob(name) if p.is_file()]
        assert len(matches)==1 and not matches[0].is_symlink() and sha256(matches[0].read_bytes()).hexdigest()==digest
    verify_source(Path.cwd(),build_source)
    environment={**os.environ,'QT_QPA_PLATFORM':'windows'}
    result=subprocess.run([str(executable),'--ci-real-core-wallet'],env=environment,stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=1200)
    assert result.returncode==0,'WIN_FROZEN_REAL_WALLET_DENIED'
    evidence=json.loads(Path('windows-packaged-wallet-evidence.json').read_text())
    assert evidence['wallet_live_core']['synthetic_rpc'] is False and evidence['platform']=='windows-x64'
    from wam_regtest.windows_package_entry import _stage_original_core
    with tempfile.TemporaryDirectory(prefix='wam-win-frozen-test-operator-') as t:
        private_core=Path(t).absolute()/'core'
        _stage_original_core(next(bundle.rglob('wamd.exe')).parent,private_core)
        subprocess.run([sys.executable,'scripts/frozen_managed_acceptance.py',
            '--core-dir',str(private_core),'--executable',str(executable),
            '--output',str(output/'frozen-managed-core-evidence.json')],
            env=environment,stdin=subprocess.DEVNULL,check=True,timeout=600)
    # Actual native qwindows + genuine Core again at Windows125%/150%.
    # Distinct cwd keeps create-only evidence and screenshots independent.
    scales={}
    for factor in ('1.25','1.5'):
        review=Path('windows-ui-scale-'+factor).absolute();review.mkdir()
        scaled={**environment,'QT_SCALE_FACTOR':factor}
        result=subprocess.run([str(executable),'--ci-real-core-wallet'],cwd=review,env=scaled,
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=1200)
        assert result.returncode==0,'WIN_SCALED_FROZEN_REAL_WALLET_DENIED'
        record=json.loads((review/'fusion-ui-review/windows-x64-visual-receipt.json').read_text())
        assert record['qt_platform']=='windows' and abs(record['device_pixel_ratio']-float(factor))<.01
        assert record['real_core_snapshot'] and not record['synthetic_rpc']
        target=output/('ui-scale-'+factor);target.mkdir()
        shutil.copytree(review/'fusion-ui-review',target/'fusion-ui-review')
        shutil.copyfile(review/'windows-packaged-wallet-evidence.json',target/'windows-packaged-wallet-evidence.json')
        scales[factor]={'native_qwindows_real_frozen_e2e':True,'device_pixel_ratio':record['device_pixel_ratio']}
    verify_source(Path.cwd(),build_source)
    (output/'BUILD_SOURCE_PROVENANCE.json').write_text(json.dumps(source_provenance,sort_keys=True,indent=2)+'\n')
    members={p.relative_to(bundle).as_posix():sha256(p.read_bytes()).hexdigest() for p in bundle.rglob('*') if p.is_file()}
    assert not any(p.is_symlink() for p in bundle.rglob('*'))
    head=os.environ['WAM_SOURCE_HEAD'];archive=output/('WAM-Privacy-Wallet-REGTEST-windows-x64-'+head+'.zip')
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for relative in sorted(members):z.write(bundle/relative,'WAM-Privacy-Wallet-REGTEST/'+relative)
    manifest={'schema':'wam-regtest-windows-package/v1','source_head_sha':head,
        'checkout_sha':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'platform':'windows-x64','wsp_source_commit':'ac55f13423620252bdbf848c7e8a280c3b84721e',
        'official_core_sha256':BINARY_SHA256,'bundle_files_sha256':members,
        'archive_sha256':sha256(archive.read_bytes()).hexdigest(),'archive_name':archive.name,
        'packaged_real_core_wallet_e2e_pass':True,'native_ui_scaling_acceptance':scales,'operator_windows10_11_acceptance':False,
        'authenticode_signed_application':False,'production_qualified':False,'mainnet_allowed':False,
        'dependencies':{n:importlib.metadata.version(n) for n in ('PySide6','PyInstaller','coincurve','cryptography','Pillow','qrcode')}}
    (output/'WINDOWS_PACKAGE_MANIFEST.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
    shutil.copyfile('windows-packaged-wallet-evidence.json',output/'windows-packaged-wallet-evidence.json')
    (output/'SHA256SUMS.txt').write_text(''.join(sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n'
        for p in sorted(output.iterdir()) if p.is_file() and p.name!='SHA256SUMS.txt'))
    from wam_regtest.release_candidate import write_candidate_manifest
    write_candidate_manifest(output,'windows-x64',BINARY_SHA256)
    print('WIN64_FROZEN_OPERATIONAL_REAL_CORE_WALLET_PACKAGE_PASS')


if __name__=='__main__':main()
