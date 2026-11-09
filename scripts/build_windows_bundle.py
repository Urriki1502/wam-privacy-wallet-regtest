"""Native Win64 PyInstaller onedir recipe; package real-wallet acceptance required.

Reuses only build tactics from legacy PR170/206, never their GUI-only acceptance.
Original owner-supplied PNG -> ICO conversion; no substituted/generated artwork.
"""
from hashlib import sha256
from contextlib import nullcontext
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile


def _production_mode(argv):
    """[] = existing qualification build; ['--production'] = allowlisted wallet."""
    if argv==[]:return False
    if argv==['--production']:return True
    raise SystemExit(64)


def _finish_production(executable,bundle,output,source_root,source_stamp,wsp_root,wsp_stamp,python_ssl,core_pins):
    """Distributed Windows bytes: exact allowlist audit, developer argv refusal,
    read-only self-check. No normal-UI E2E is claimed here (separate gate)."""
    from wam_regtest.build_provenance import verify,public_receipt
    sys.path.insert(0,str(source_root/'scripts'))
    from production_packaging import audit,DEVELOPER_ARGV
    for name,digest in core_pins.items():
        matches=[p for p in bundle.rglob(name) if p.is_file()]
        assert len(matches)==1 and not matches[0].is_symlink() and sha256(matches[0].read_bytes()).hexdigest()==digest
    inventory=audit(executable,bundle,'windows')
    (output/'PRODUCTION_MODULE_INVENTORY.json').write_text(json.dumps(inventory,indent=2)+'\n')
    system_root=Path(os.environ['SystemRoot'])
    clean={k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV')
        and not k.startswith(('QT_','QML_'))}
    clean.update({'QT_QPA_PLATFORM':'windows','PATH':str(system_root/'System32')+os.pathsep+str(system_root)})
    checks=[]
    with tempfile.TemporaryDirectory(prefix='wam-win-production-cwd-') as work:
        check=subprocess.run([str(executable),'--check-bundle'],env=clean,cwd=work,stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=180)
        assert check.returncode==0,'WIN_PRODUCTION_CHECK_BUNDLE_DENIED'
        hostile=dict(clean,CI='true',GITHUB_ACTIONS='true',WAM_Q06_CI_SPEND_QUALIFY='1',WAM_QUALIFICATION='1')
        for argv in DEVELOPER_ARGV:
            result=subprocess.run([str(executable),*argv],env=hostile,cwd=work,stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=60)
            assert result.returncode==64,'WIN_PRODUCTION_DEVELOPER_DISPATCH_NOT_DENIED'
            checks.append({'argv':argv,'returncode':result.returncode})
    (output/'PRODUCTION_DISPATCH_NEGATIVES.json').write_text(json.dumps(checks,indent=2)+'\n')
    members={p.relative_to(bundle).as_posix():sha256(p.read_bytes()).hexdigest() for p in bundle.rglob('*') if p.is_file()}
    assert not any(p.is_symlink() for p in bundle.rglob('*'))
    verify(source_root,source_stamp);verify(wsp_root,wsp_stamp)
    head=os.environ['WAM_SOURCE_HEAD']
    archive=output/('WAM-Privacy-Wallet-REGTEST-windows-x64-production-'+head+'.zip')
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for relative in sorted(members):z.write(bundle/relative,'WAM-Privacy-Wallet-REGTEST/'+relative)
    receipt={'artifact_role':'allowlisted-regtest-wallet','platform':'windows-x64',
        'source':public_receipt(source_stamp,source_head=head,dispatch=os.environ.get('GITHUB_EVENT_NAME')=='workflow_dispatch'),
        'core_sha256':core_pins,'wsp_source_commit':'ac55f13423620252bdbf848c7e8a280c3b84721e',
        'executable_sha256':sha256(executable.read_bytes()).hexdigest(),'bundle_files_sha256':members,
        'archive_name':archive.name,'archive_sha256':sha256(archive.read_bytes()).hexdigest(),
        'q01_cpython_ssl_sha256':python_ssl,'authenticode_signed_application':False,
        'production_qualified':False,'normal_ui_frozen_e2e':'PENDING_NATIVE_WINDOWS_NORMAL_UI_QUALIFICATION',
        'separate_qualification_artifact':'windows-package-output; does not qualify distributed bytes',
        'mainnet_allowed':False}
    (output/'PRODUCTION_BUILD_RECEIPT.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    from wam_regtest.release_candidate import write_portable_sha256sums
    write_portable_sha256sums(output)
    print('WIN64_PRODUCTION_ALLOWLIST_BUILD_PASS_NORMAL_UI_QUALIFICATION_PENDING')


def main():
    production=_production_mode(sys.argv[1:])
    assert sys.platform=='win32' and platform.machine().lower() in ('amd64','x86_64')
    from wam_regtest.build_provenance import capture,verify,public_receipt
    source_root=Path.cwd();source_stamp=capture(source_root)
    from wam_regtest.windows_release_preflight import ASSET,BINARY_SHA256,verify_signed_windows_archive,_validate_amd64_pe
    from wam_regtest.release import _download_exact
    from wam_regtest.package_manifest import stage_pinned_wsp
    from wam_regtest.branding import brand_image
    source=Path('wsp-upstream').absolute()
    assert subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()=='ac55f13423620252bdbf848c7e8a280c3b84721e'
    wsp_stamp=capture(source)
    output=Path('windows-production-output' if production else 'windows-package-output');output.mkdir()
    with tempfile.TemporaryDirectory(prefix='wam-win-build-') as t:
        stage=Path(t);core=stage/'core';core.mkdir()
        from wam_regtest.q05_package_provenance import stage as stage_q05
        q05_source=stage/'Q05_BUILD_SOURCE.json';stage_q05(source_stamp,q05_source)
        for remote,name,limit in (
            ('/SIGNING-KEY.asc','SIGNING-KEY.asc',32768),
            ('/downloads/v0.1.13/SHA256SUMS','SHA256SUMS',131072),
            ('/downloads/v0.1.13/SHA256SUMS.asc','SHA256SUMS.asc',16384),
            ('/downloads/v0.1.13/'+ASSET,ASSET,320*1024*1024)):
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
        # Qt's hook otherwise searches ambient PATH for optional OpenSSL DLLs.
        # Two genuine clean-run artifacts contained different executable code
        # (OpenSSL3.5.9 vs3.5.5). Do not import developer/Git/Chocolatey providers.
        # CPython's declared SSL DLLs and native Windows Schannel stay intact.
        system_root=Path(os.environ['SystemRoot'])
        build_environment={k:v for k,v in os.environ.items() if k not in
            ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV','OPENSSL_CONF','OPENSSL_MODULES')
            and not k.startswith(('QT_','QML_'))}
        build_environment['PATH']=os.pathsep.join(map(str,(Path(sys.executable).parent,
            Path(sys.base_prefix),Path(sys.base_prefix)/'DLLs',system_root/'System32',system_root)))
        from wam_regtest.distribution_notices import stage_distribution_notices
        notices=stage/'third-party-notices'
        stage_distribution_notices(notices,qt=True)
        if production:
            # Positive allowlist and the strict production entry; no
            # --collect-submodules wam_regtest, no developer dispatch.
            sys.path.insert(0,str(source_root/'scripts'))
            from production_packaging import arguments as production_arguments
            modules=['--distpath','dist-production','--workpath','build-production',
                     *production_arguments(source_root,'windows')]
            entry='src/wam_regtest/windows_production_entry.py'
        else:
            modules=['--collect-submodules','wam_regtest']
            entry='src/wam_regtest/windows_package_entry.py'
        subprocess.run([sys.executable,'-I','-m','PyInstaller','--noconfirm','--clean','--noupx','--onedir','--windowed',
            '--name','WAM-Privacy-Wallet-REGTEST','--icon',str(icon),'--paths','src',
            *modules,'--collect-submodules','wam_sp',
            # Production: no loose third-party Python (loose-file audit);
            # coincurve via its PyInstaller hook + binaries, like macOS.
            *(['--collect-binaries','coincurve','--copy-metadata','coincurve',
               '--hidden-import','coincurve._cffi_backend'] if production else
              ['--collect-all','coincurve']),'--hidden-import','_cffi_backend',
            '--add-data',str(q05_source)+':.','--add-data',str(core)+':core','--add-data',str(wsp)+':wsp-source',
            '--add-data',str(notices)+':third-party-notices',
            '--add-data',str(brand_image())+':branding',entry],env=build_environment,check=True)
    bundle=Path('dist-production/WAM-Privacy-Wallet-REGTEST' if production else 'dist/WAM-Privacy-Wallet-REGTEST').absolute()
    executable=bundle/'WAM-Privacy-Wallet-REGTEST.exe'
    _validate_amd64_pe(executable.read_bytes())
    # Refuse, never delete, an undeclared optional TLS provider. This does not
    # disable TLS verification or replace WSP/cryptography/Core implementations.
    assert not any(p.name.lower() in ('libcrypto-3-x64.dll','libssl-3-x64.dll') for p in bundle.rglob('*')),'WIN_UNDECLARED_QT_OPENSSL_PROVIDER_DENIED'
    python_ssl={}
    for name in ('libcrypto-3.dll','libssl-3.dll'):
        source_dll=Path(sys.base_prefix)/'DLLs'/name
        members=[p for p in bundle.rglob(name) if p.is_file()]
        assert source_dll.is_file() and len(members)==1
        digest=sha256(source_dll.read_bytes()).hexdigest()
        assert sha256(members[0].read_bytes()).hexdigest()==digest,'WIN_CPYTHON_SSL_BYTES_CHANGED'
        python_ssl[name]=digest
    if production:
        return _finish_production(executable,bundle,output,source_root,source_stamp,source,wsp_stamp,python_ssl,BINARY_SHA256)
    subprocess.run([sys.executable,'-I','scripts/qualify_q05_frozen.py',
        '--executable',str(executable),'--output',str((output/'q05-frozen-evidence.json').absolute())],
        check=True,timeout=1200)
    # Q06 uses genuine signed-Core native Windows custody and FINAL frozen
    # executable, not inherited Q05 evidence or source-only green tests.
    subprocess.run([sys.executable,'-I','scripts/qualify_q06_frozen.py',
        '--executable',str(executable),'--output',str((output/'q06-frozen-evidence.json').absolute())],
        check=True,timeout=1200)
    for name,digest in BINARY_SHA256.items():
        matches=[p for p in bundle.rglob(name) if p.is_file()]
        assert len(matches)==1 and not matches[0].is_symlink() and sha256(matches[0].read_bytes()).hexdigest()==digest
    environment={k:v for k,v in os.environ.items() if k not in
        ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV') and not k.startswith(('QT_','QML_'))}
    system_root=Path(os.environ['SystemRoot'])
    environment.update({'QT_QPA_PLATFORM':'windows','PATH':str(system_root/'System32')+os.pathsep+str(system_root)})
    # Preserve this NEW qualification namespace on failure, including a live
    # original owner. Never upload private profiles/configs or sweep temp roots.
    with nullcontext(tempfile.mkdtemp(prefix='wam-q01-win-frozen-cwd-')) as clean:
        isolated=Path(clean).resolve()
        result=subprocess.run([str(executable),'--ci-real-core-wallet'],env=environment,cwd=isolated,stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=1200)
        if result.returncode!=0:
            # The windowed PyInstaller process has no console output. Report only
            # the strict public token emitted by the disposable frozen test entry.
            # Never print OS/RPC logs, paths, exception text or credentials.
            refusal=isolated/'windows-packaged-wallet-denied.json'
            code='WIN_BUNDLE_NO_PUBLIC_REFUSAL_RECEIPT'
            from wam_regtest.windows_package_entry import public_failure_details
            details=public_failure_details({})
            if refusal.is_file():
                try:
                    payload=json.loads(refusal.read_text(encoding='utf8'))
                    candidate=payload.get('reason_code')
                    if (payload.get('status')=='WIN_BUNDLE_DENIED'
                            and type(candidate) is str and len(candidate)<=110
                            and re.fullmatch(r'(?:CORE|WIN|WALLET|WSP|Q02|Q04|Q06)_[A-Z0-9_]{4,105}',candidate)):
                        code=candidate
                        details=public_failure_details(payload)
                except (OSError,ValueError,TypeError):
                    pass
            print('WIN_FROZEN_DEFAULT_PUBLIC_DENIAL='+code,flush=True)
            line_path=isolated/'wallet-probe-public-line.json'
            if line_path.is_file():
                try:
                    line=json.loads(line_path.read_text(encoding='utf8')).get('line')
                    if type(line) is int and 1<=line<=10000:details['wallet_probe_line']=line
                except (OSError,ValueError,TypeError):pass
            print('WIN_FROZEN_DEFAULT_PUBLIC_DETAILS='+json.dumps(details,sort_keys=True),flush=True)
            with (output/'Q01_DEFAULT_FAILURE.json').open('x') as failure:
                json.dump({'status':'FAIL','stage':'frozen-100','reason_code':code,**details},failure)
            raise AssertionError('WIN_FROZEN_REAL_WALLET_DENIED')
        evidence=json.loads((isolated/'windows-packaged-wallet-evidence.json').read_text())
        assert evidence['wallet_live_core']['synthetic_rpc'] is False and evidence['platform']=='windows-x64'
        shutil.copyfile(isolated/'windows-packaged-wallet-evidence.json',output/'windows-packaged-wallet-evidence.json')
        shutil.copytree(isolated/'fusion-ui-review',output/'fusion-ui-review')
        # Actual native qwindows + genuine Core again at Windows125%/150%.
        # Distinct cwd keeps create-only evidence and screenshots independent.
        scales={}
        for factor in ('1.25','1.5'):
            review=isolated/('windows-ui-scale-'+factor);review.mkdir()
            scaled={**environment,'QT_SCALE_FACTOR':factor}
            result=subprocess.run([str(executable),'--ci-real-core-wallet'],cwd=review,env=scaled,
                stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=1200)
            if result.returncode!=0:
                # The windowed frozen process has no stdout/stderr. Read ONLY a
                # fixed public status token, never Core/Qt logs or user paths.
                refusal=review/'windows-packaged-wallet-denied.json'
                code='WIN_BUNDLE_NO_PUBLIC_REFUSAL_RECEIPT'
                if refusal.is_file():
                    try:
                        payload=json.loads(refusal.read_text(encoding='utf8'))
                        candidate=payload.get('reason_code')
                        if (payload.get('status')=='WIN_BUNDLE_DENIED'
                                and type(candidate) is str and len(candidate)<=110
                                and re.fullmatch(r'(?:CORE|WIN|WALLET|WSP|Q02|Q04|Q06)_[A-Z0-9_]{4,105}',candidate)):
                            code=candidate
                    except (OSError,ValueError,TypeError):
                        pass
                line_path=review/'wallet-probe-public-line.json'
                if line_path.is_file():
                    try:
                        line=json.loads(line_path.read_text(encoding='utf8')).get('line')
                        if type(line) is int and 1<=line<=10000:
                            print('WALLET_PROBE_ASSERTION_LINE='+str(line),flush=True)
                    except (OSError,ValueError,TypeError):
                        pass
                print('WIN_SCALED_FROZEN_PUBLIC_DENIAL_'+factor.replace('.','_')+'='+code,flush=True)
                with (output/('Q01_SCALE_'+factor+'_FAILURE.json')).open('x') as failure:
                    json.dump({'status':'FAIL','stage':'frozen-'+factor,'reason_code':code},failure)
                raise AssertionError('WIN_SCALED_FROZEN_REAL_WALLET_DENIED')
            record=json.loads((review/'fusion-ui-review/windows-x64-visual-receipt.json').read_text())
            assert record['qt_platform']=='windows' and abs(record['device_pixel_ratio']-float(factor))<.01
            assert record['real_core_snapshot'] and not record['synthetic_rpc']
            target=output/('ui-scale-'+factor);target.mkdir()
            shutil.copytree(review/'fusion-ui-review',target/'fusion-ui-review')
            shutil.copyfile(review/'windows-packaged-wallet-evidence.json',target/'windows-packaged-wallet-evidence.json')
            scales[factor]={'native_qwindows_real_frozen_e2e':True,'device_pixel_ratio':record['device_pixel_ratio']}
    # Q04 external-miner coexistence through the frozen executable.
    with tempfile.TemporaryDirectory(prefix='wam-q04-win-frozen-cwd-') as q04_clean:
        q04_isolated=Path(q04_clean).resolve()
        q04_env={k:v for k,v in os.environ.items() if k not in
            ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV') and not k.startswith(('QT_','QML_'))}
        system_root=Path(os.environ['SystemRoot'])
        q04_env.update({'QT_QPA_PLATFORM':'windows','PATH':str(system_root/'System32')+os.pathsep+str(system_root)})
        q04_result=subprocess.run([str(executable),'--ci-q04-external-miner'],env=q04_env,cwd=q04_isolated,
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=600)
        if q04_result.returncode!=0:
            refusal=q04_isolated/'windows-packaged-wallet-denied.json'
            code='WIN_BUNDLE_NO_PUBLIC_REFUSAL_RECEIPT'
            if refusal.is_file():
                try:
                    payload=json.loads(refusal.read_text(encoding='utf8'))
                    candidate=payload.get('reason_code')
                    if (payload.get('status')=='WIN_BUNDLE_DENIED' and type(candidate) is str
                            and len(candidate)<=110
                            and re.fullmatch(r'(?:CORE|WIN|WALLET|WSP|Q04)_[A-Z0-9_]{4,105}',candidate)):
                        code=candidate
                except (OSError,ValueError,TypeError):
                    pass
            print('WIN_Q04_FROZEN_PUBLIC_DENIAL='+code,flush=True)
            raise AssertionError('WIN_Q04_FROZEN_EXTERNAL_MINER_DENIED')
        shutil.copyfile(q04_isolated/'q04-frozen-evidence.json',output/'q04-frozen-evidence.json')
    members={p.relative_to(bundle).as_posix():sha256(p.read_bytes()).hexdigest() for p in bundle.rglob('*') if p.is_file()}
    assert not any(p.is_symlink() for p in bundle.rglob('*'))
    verify(source_root,source_stamp);verify(source,wsp_stamp)
    (output/'BUILD_SOURCE_RECEIPT.json').write_text(json.dumps(public_receipt(source_stamp,
        source_head=os.environ.get('WAM_SOURCE_HEAD'),dispatch=os.environ.get('GITHUB_EVENT_NAME')=='workflow_dispatch'),sort_keys=True,indent=2)+'\n')
    head=os.environ['WAM_SOURCE_HEAD'];archive=output/('WAM-Privacy-Wallet-REGTEST-windows-x64-'+head+'.zip')
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for relative in sorted(members):z.write(bundle/relative,'WAM-Privacy-Wallet-REGTEST/'+relative)
    manifest={'schema':'wam-regtest-windows-package/v1','source_head_sha':head,
        'checkout_sha':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'platform':'windows-x64','wsp_source_commit':'ac55f13423620252bdbf848c7e8a280c3b84721e',
        'official_core_sha256':BINARY_SHA256,'bundle_files_sha256':members,
        'archive_sha256':sha256(archive.read_bytes()).hexdigest(),'archive_name':archive.name,
        'q01_external_working_directory':True,'q01_developer_python_path_removed':True,
        'q01_cpython_ssl_sha256':python_ssl,'q01_qt_tls_backend':'schannel',
        'q01_ambient_openssl_provider_allowed':False,
        'packaged_real_core_wallet_e2e_pass':True,'native_ui_scaling_acceptance':scales,'operator_windows10_11_acceptance':False,
        'authenticode_signed_application':False,'production_qualified':False,'mainnet_allowed':False,
        'dependencies':{n:importlib.metadata.version(n) for n in ('PySide6','PyInstaller','coincurve','cryptography','Pillow','qrcode')}}
    (output/'WINDOWS_PACKAGE_MANIFEST.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
    from wam_regtest.release_candidate import write_portable_sha256sums
    write_portable_sha256sums(output)
    from wam_regtest.release_candidate import write_candidate_manifest
    write_candidate_manifest(output,'windows-x64',BINARY_SHA256)
    print('WIN64_FROZEN_OPERATIONAL_REAL_CORE_WALLET_PACKAGE_PASS')


if __name__=='__main__':main()
