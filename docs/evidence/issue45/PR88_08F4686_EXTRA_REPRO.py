"""Real Git/source-handle integrity tests; no WSP import, Core or keys."""
import sys,os,json,subprocess,hashlib
from pathlib import Path
from wam_regtest.wsp_live import _pinned_source,PINNED_WSP_COMMIT,RealWspScanError
root=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]);rows=[]
def git(*args):return subprocess.check_output(['git','-C',str(root),*args])
def probe(case):
    try:_pinned_source(root);accepted=True;error=None
    except RealWspScanError as e:accepted=False;error=str(e)
    assert 'wam_sp' not in sys.modules
    rows.append({'case':case,'accepted':accepted,'safe_error':error,'wam_sp_import_executed':False})
assert (root/'.git/WAM_PUBLIC_DISPOSABLE_PROBE').read_text() == 'DISPOSABLE_PUBLIC_SOURCE_PROBE_ONLY\n'
assert not (root/'.git').is_symlink()
assert git('rev-parse','HEAD').decode().strip()==PINNED_WSP_COMMIT
probe('clean_with_normal_python_caches')
scanner=root/'src/wam_sp/scanner.py';link=root/'public-source-hardlink-probe'
os.link(scanner,link)
try:probe('tracked_source_hardlink_outside_package')
finally:link.unlink()
# Source-parent link only, original files left byte-identical. All mutations
# are in THIS disposable clone, never the installed original dependency.
tracked=git('ls-files','-z','--','src/wam_sp').split(b'\0')[:-1]
for raw in tracked:git('update-index','--assume-unchanged',raw.decode())
original_src=root/'src';moved=root/'public-probe-real-src';original_src.rename(moved);original_src.symlink_to(moved.name,target_is_directory=True)
try:probe('symlink_source_parent_hidden_by_index_flags')
finally:
    original_src.unlink();moved.rename(original_src)
    for raw in tracked:git('update-index','--no-assume-unchanged',raw.decode())
probe('restored_clean_with_normal_caches')
assert not git('status','--porcelain','--untracked-files=all').strip()
out.write_text(json.dumps({'source_under_test':sys.argv[3],'actual_guard_sha256':hashlib.sha256(Path(sys.modules['wam_regtest.wsp_live'].__file__).read_bytes()).hexdigest(),'wsp_pin':PINNED_WSP_COMMIT,'native_platform':sys.platform,'rows':rows,'core_e2e':False,'frozen_e2e':False,'disposable_clone_only':True,'trusted_dependency_changed':False},indent=2)+'\n')
print(json.dumps(rows,indent=2))
