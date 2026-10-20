"""Source integrity regression, no source-module import/Core/key operation."""
import sys,json,subprocess,hashlib
from pathlib import Path
from wam_regtest.wsp_live import _pinned_source,PINNED_WSP_COMMIT,RealWspScanError
root=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]).resolve()
assert (root/'.git/WAM_PUBLIC_DISPOSABLE_PROBE').read_text() == 'DISPOSABLE_PUBLIC_SOURCE_PROBE_ONLY\n'
assert not (root/'.git').is_symlink()
assert subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()==PINNED_WSP_COMMIT
assert 'wam_sp' not in sys.modules
rows=[]
def probe(name):
    dirty=subprocess.check_output(['git','-C',str(root),'status','--porcelain','--untracked-files=no','--','src/wam_sp'],text=True)
    try:_pinned_source(root);accepted=True;category=None
    except RealWspScanError as e:accepted=False;category=str(e)
    assert 'wam_sp' not in sys.modules
    rows.append({'case':name,'accepted':accepted,'safe_error':category,'git_status_no_untracked_empty':not dirty.strip(),'wam_sp_import_executed':False})
probe('clean_pinned_checkout')
extra=root/'src/wam_sp/public_untracked_probe.py'
extra.write_text("raise RuntimeError('PUBLIC_PROBE_MUST_NEVER_BE_IMPORTED')\n")
try:probe('untracked_python_module')
finally:extra.unlink()
native=root/'src/wam_sp/public_untracked_probe.so';native.write_bytes(b'PUBLIC_INERT_NOT_A_LIBRARY')
try:probe('untracked_native_extension')
finally:native.unlink()
exclude=root/'.git/info/exclude';old_exclude=exclude.read_bytes()
exclude.write_bytes(old_exclude+b'\nsrc/wam_sp/public_ignored_probe.so\n')
ignored=root/'src/wam_sp/public_ignored_probe.so';ignored.write_bytes(b'PUBLIC_INERT_NOT_A_LIBRARY')
try:probe('ignored_native_extension')
finally:
    ignored.unlink()
    exclude.write_bytes(old_exclude)
scanner=root/'src/wam_sp/scanner.py';original=scanner.read_bytes()
for flag,reset in [('--assume-unchanged','--no-assume-unchanged'),('--skip-worktree','--no-skip-worktree')]:
    subprocess.run(['git','-C',str(root),'update-index',flag,'src/wam_sp/scanner.py'],check=True)
    scanner.write_bytes(b"raise RuntimeError('PUBLIC_PINNED_MODULE_TAMPER_NOT_IMPORTED')\n")
    try:probe('modified_tracked_scanner_'+flag[2:])
    finally:
        scanner.write_bytes(original)
        subprocess.run(['git','-C',str(root),'update-index',reset,'src/wam_sp/scanner.py'],check=True)
probe('restored_clean_pinned_checkout')
assert subprocess.check_output(['git','-C',str(root),'status','--porcelain','--untracked-files=all'],text=True)==''
result={'source_head_sha':sys.argv[3], 'actual_guard_file_sha256':hashlib.sha256(Path(sys.modules['wam_regtest.wsp_live'].__file__).read_bytes()).hexdigest(),'wsp_pin':PINNED_WSP_COMMIT,'evidence_layer':'ACTUAL_SOURCE_GUARD_EXECUTION_NOT_CORE_E2E','rows':rows,'disposable_source_clone_only':True,'original_dependency_changed':False,'core_or_keys_or_anchors_used':False,'synthetic_core_acceptance':False,'mainnet_allowed':False}
out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
