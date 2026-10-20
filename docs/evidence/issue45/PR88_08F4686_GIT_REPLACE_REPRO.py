"""Public disposable Git metadata probe; never imports WSP or starts Core."""
from pathlib import Path
import sys,subprocess,json,hashlib
from wam_regtest.wsp_live import _pinned_source,PINNED_WSP_COMMIT,RealWspScanError
root=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]);assert (root/'.git/WAM_PUBLIC_DISPOSABLE_PROBE').read_text()=='DISPOSABLE_PUBLIC_SOURCE_PROBE_ONLY\n'
def git(*args,input=None):return subprocess.check_output(['git','-C',str(root),*args],input=input)
assert not git('status','--porcelain','--untracked-files=all').strip()
assert not git('replace','-l').strip()
f=root/'src/wam_sp/scanner.py';old=f.read_bytes();rows=[]
def probe(case):
 try:_pinned_source(root);allowed=True;error=None
 except RealWspScanError as e:allowed=False;error=str(e)
 assert 'wam_sp' not in sys.modules
 rows.append({'case':case,'accepted':allowed,'safe_error':error})
probe('clean_before')
try:
 f.write_bytes(b"raise RuntimeError('PUBLIC_REPLACE_PROBE_NEVER_IMPORTED')\n")
 git('add','--','src/wam_sp/scanner.py');tree=git('write-tree').decode().strip()
 commit=git('-c','user.name=Public Probe','-c','user.email=public-probe@example.invalid','commit-tree',tree,input=b'Public disposable replacement only\n').decode().strip()
 git('replace',PINNED_WSP_COMMIT,commit)
 assert git('rev-parse','HEAD').decode().strip()==PINNED_WSP_COMMIT
 assert not git('status','--porcelain','--untracked-files=all').strip()
 probe('modified_tracked_source_hidden_by_git_replace')
finally:
 if git('replace','-l').strip():git('replace','-d',PINNED_WSP_COMMIT)
 f.write_bytes(old);git('reset','--mixed',PINNED_WSP_COMMIT)
probe('restored_clean')
assert not git('status','--porcelain','--untracked-files=all').strip()
r={'source_label':sys.argv[3],'actual_guard_sha256':hashlib.sha256(Path(sys.modules['wam_regtest.wsp_live'].__file__).read_bytes()).hexdigest(),'rows':rows,'native_platform':sys.platform,'disposable_clone_only':True,'wam_sp_import_executed':False,'core_or_keys_or_anchors_used':False,'real_core_e2e':False,'mainnet_allowed':False};out.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
