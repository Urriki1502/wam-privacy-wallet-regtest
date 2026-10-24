"""Real Qt startup selector/password/create/sync/close; explicit native test Keychain."""
import argparse,importlib.util,json,os,subprocess,time
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication,QInputDialog,QLineEdit
from wam_regtest import custody
from wam_regtest.operational_gui import launch_disposable_wallet,OperationalWalletWindow
from wam_regtest.desktop import qt_application,shutdown_qt
p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--core',type=Path,required=True);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
spec=importlib.util.spec_from_file_location('audit_driver',a.repo/'scripts/owner_acceptance.py');d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
out=a.output.resolve();out.mkdir(exist_ok=False);os.chdir(out);app=qt_application();proof={};password='public-disposable-gui-startup-audit'
try:
 with d.isolated_chain(a.core,a.source) as (data,mining,core):
  fixture=data/'startup-fixture.keychain-db';subprocess.run(['/usr/bin/security','create-keychain','-p','public-test-only',str(fixture)],check=True,capture_output=True)
  original=custody.anchor;targets=[];stage=0;timer=QTimer();started=time.monotonic();errors=[]
  def fixture_anchor(wallet_id,keychain=None):
   assert keychain is None,'UNEXPECTED_ANCHOR_TARGET'
   target=original(wallet_id,fixture);targets.append(type(target).__name__);return target
  # Real native anchor factory delegates unchanged. Only the explicit test
  # keychain target differs; no Core/RPC/crypto/storage/anchor gate is mocked.
  custody.anchor=fixture_anchor
  def drive():
   global stage
   try:
    if time.monotonic()-started>60:raise AssertionError('STARTUP_TIMEOUT')
    modal=QApplication.activeModalWidget()
    if isinstance(modal,QInputDialog):
     if stage==0:
      assert modal.comboBoxItems()==['Create fresh test keys','Recover latest backup on this computer']
      modal.setTextValue('Create fresh test keys');stage=1;modal.accept();return
     if stage==1:
      assert modal.textEchoMode()==QLineEdit.EchoMode.Password
      modal.setTextValue(password);stage=2;modal.accept();return
    for w in QApplication.topLevelWidgets():
     if isinstance(w,OperationalWalletWindow) and w._snapshot is not None and w._worker is None:
      snap=w._snapshot;assert stage==2 and snap.height==103 and snap.confirmed_atoms>0 and snap.synthetic_rpc is False
      assert w.navigation.count()==6 and targets==['KeychainAnchor']
      proof.update(startup_choice_fresh_real_keys=True,startup_masked_password=True,live_core_wsp_gui_snapshot=True,height=snap.height,confirmed_atoms=snap.confirmed_atoms,native_keychain_fixture_routing=True,synthetic_rpc=False,mainnet_allowed=False,qt_platform=app.platformName())
      assert w.grab().save(str(out/'fresh-gui-startup.png'));timer.stop();w.close();return
   except Exception as error:
    errors.append(type(error).__name__);timer.stop()
    if modal is not None:modal.reject()
    app.exit(2)
  timer.timeout.connect(drive);timer.start(80)
  try:
   code=launch_disposable_wallet(a.core,data,a.source,mining)
   assert code==0 and proof and not errors,'STARTUP_AUDIT_FAILED'
   proof['clean_gui_close']=True
   (out/'GUI_STARTUP_RECEIPT.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof,indent=2))
  finally:
   timer.stop();custody.anchor=original
   subprocess.run(['/usr/bin/security','delete-keychain',str(fixture)],check=True,capture_output=True)
finally:shutdown_qt()
