"""Explicit disposable native-Core owner/UX audit. Never opens owner wallet data."""
from contextlib import contextmanager
from hashlib import sha256
import argparse,json,os,subprocess,sys,tempfile,time
from pathlib import Path
from PySide6.QtCore import QEventLoop,QTimer,QCoreApplication,QEvent,Qt
from PySide6.QtGui import QImage,QFontInfo
from PySide6.QtWidgets import QApplication
from wam_regtest.core import verified_core_paths,_port,_write_private_config,_read_cli
from wam_regtest.wsp_live import _pinned_source,public_regtest_mining_address,scan_actual_core_blocks
from wam_regtest.wallet_session import WalletSession,WalletCoreCli
from wam_regtest.wallet_read import format_wam
from wam_regtest.desktop import qt_application,shutdown_qt
from wam_regtest.operational_gui import OperationalWalletWindow
from wam_regtest.wallet_probe import _approve_dialog,_capture_fusion_views
from wam_regtest import custody

RESULTS=[];OUT=None

def record(name,passed,**proof):
 RESULTS.append({'check':name,'status':'PASS' if passed else 'FAIL','evidence':proof})
 (OUT/'OWNER_ACCEPTANCE.json').write_text(json.dumps({'schema':'wam-owner-audit/v1','network':'regtest','synthetic_rpc':False,'owner_data_touched':False,'checks':RESULTS},indent=2)+'\n')
 print(name,RESULTS[-1]['status'],flush=True)

def settle(app,window):
 if window._worker is not None:
  assert window._worker.wait(15000),'WORKER_SHUTDOWN_REQUIRED'
 app.processEvents();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)

def operation(app,window,action,trigger,denied=False):
 loop=QEventLoop();result={};timer=QTimer();timer.setSingleShot(True)
 def ready(name,value):
  if name==action:result.update(ok=True,value=value);loop.quit()
 def failed(code):result.update(denied=True,code=code);loop.quit()
 window.operation_completed.connect(ready);window.operation_failed.connect(failed)
 timer.timeout.connect(loop.quit);timer.start(90000);QTimer.singleShot(0,trigger);loop.exec();timer.stop()
 window.operation_completed.disconnect(ready);window.operation_failed.disconnect(failed);settle(app,window)
 assert result.get('denied') if denied else result.get('ok'),('OPERATION_FAILED',action,result)
 return result

def sync(app,window):
 loop=QEventLoop();r={};t=QTimer();t.setSingleShot(True)
 def done(snap):r['snapshot']=snap;loop.quit()
 window.snapshot_updated.connect(done);t.timeout.connect(loop.quit);t.start(20000)
 QTimer.singleShot(0,window.request_sync);loop.exec();t.stop();window.snapshot_updated.disconnect(done);settle(app,window)
 assert 'snapshot' in r,'LIVE_SYNC_REQUIRED'
 return r['snapshot']

def reservations(session):return tuple(tuple(r) for r in session.scanner.store.db.execute('SELECT txid,vout,token,state FROM reservations ORDER BY txid,vout'))

@contextmanager
def isolated_chain(core,source,*,process_observer=None):
 node,cli,receipt=verified_core_paths(core);_pinned_source(source)
 with tempfile.TemporaryDirectory(prefix='wam-owner-audit-') as temp:
  data=Path(temp).resolve();data.chmod(0o700);rpc_port,peer_port=_port(),_port();assert rpc_port!=peer_port;_write_private_config(data,rpc_port,peer_port)
  env={'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','HOME':str(data),'LC_ALL':'C'}
  prefix=[str(cli),f'-datadir={data}'];proc=None
  try:
   with (data/'core-output.log').open('xb') as log:proc=subprocess.Popen([str(node),f'-datadir={data}','-daemon=0'],cwd=data,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
   end=time.monotonic()+90
   while True:
    assert proc.poll() is None,'OWNED_CORE_EXITED'
    try:
     info=_read_cli(prefix+['getblockchaininfo'],timeout=3)
     if info['chain']=='regtest':break
    except Exception:pass
    assert time.monotonic()<end,'OWNED_CORE_START_TIMEOUT';time.sleep(.2)
   assert _read_cli(prefix+['getconnectioncount'])==0
   _read_cli(prefix+['createwallet','test'])
   mining=public_regtest_mining_address(source)
   assert len(_read_cli(prefix+['generatetoaddress','101',mining],timeout=90))==101
   scan=scan_actual_core_blocks(cli,data,source,expected_height=101,payment_e2e=True,mining_address=mining)
   assert scan['synthetic_rpc'] is False
   if process_observer is not None:process_observer(proc)
   yield data,mining,receipt
  finally:
   if proc is not None and proc.poll() is None:
    try:_read_cli(prefix+['stop'],timeout=10);proc.wait(timeout=20)
    except Exception:proc.terminate();proc.wait(timeout=10)

def audit(core,source):
 from wam_sp.keystore import Keyring
 from wam_sp.scanner import Scanner
 from wam_sp.wallet import Wallet
 app=qt_application();password=b'public-disposable-owner-audit-only'
 with isolated_chain(core,source) as (data,mining,receipt):
  keychain=data/'owner-audit.keychain-db';session=window=receiver=rscan=None;created=False
  try:
   assert sys.platform=='darwin','MACOS_OWNER_AUDIT_SCOPE'
   subprocess.run(['/usr/bin/security','create-keychain','-p','public-test-only',str(keychain)],check=True,capture_output=True);created=True
   session=WalletSession.create(core,data,source,password,mining,authorized=True,keychain=keychain)
   receiver=Keyring();rscan=Scanner(data/'receiver.sqlite',receiver.accounts())
   rpc=session._rpc();initial=session.snapshot();window=OperationalWalletWindow(session);window.show();window.apply_snapshot(initial);window._sync_timer.stop()
   record('fresh_wallet_core_wsp_sqlite',initial.height==103 and initial.confirmed_atoms>0,core_sha256=receipt['wamd_sha256'],height=initial.height,confirmed_atoms=initial.confirmed_atoms,zero_peers=rpc._call('getconnectioncount',[])==0)
   record('receive_code_native_wsp',window.receive_page.code==initial.receive_code and window.receive_page.qr.matrix is not None)
   # Independently decode actual rendered widget pixels, not a QR encoder roundtrip.
   window.navigation.setCurrentRow(1);app.processEvents();qr=window.receive_page.qr.grab().toImage().convertToFormat(QImage.Format.Format_Grayscale8)
   assert qr.save(str(OUT/'receive-qr.png'))
   import zxingcpp
   pixels=bytes(qr.bits());tight=b''.join(pixels[y*qr.bytesPerLine():y*qr.bytesPerLine()+qr.width()] for y in range(qr.height()))
   image=memoryview(tight).cast('B',shape=(qr.height(),qr.width()))
   decoded=zxingcpp.read_barcode(image)
   record('rendered_qr_independent_decode',decoded is not None and decoded.text==initial.receive_code)
   record('seven_screen_navigation',window.navigation.count()==7)
   for i in range(6):window.navigation.setCurrentRow(i);app.processEvents();assert window.stack.currentIndex()==i
   # Use a real malformed-input matrix; all denials must leave chain/reservations untouched.
   tests=[('amount_empty',receiver.accounts()[0].payment_code(),'','0.00010000'),('amount_negative',initial.receive_code,'-1','0.00010000'),('amount_comma',initial.receive_code,'0,001','0.00010000'),('amount_dust',initial.receive_code,'0.00000001','0.00010000'),('amount_precision',initial.receive_code,'0.000000001','0.00010000'),('fee_zero',initial.receive_code,'0.00100000','0'),('fee_negative',initial.receive_code,'0.00100000','-0.01'),('fee_excess',initial.receive_code,'0.00100000','0.01000001'),('fee_precision',initial.receive_code,'0.00100000','0.000000001'),('recipient_empty','','0.00100000','0.00010000'),('recipient_garbage','not-an-address','0.00100000','0.00010000'),('recipient_standard_core',mining,'0.00100000','0.00010000'),('recipient_bad_checksum',initial.receive_code[:-1]+('q' if initial.receive_code[-1]!='q' else 'p'),'0.00100000','0.00010000'),('insufficient_funds',initial.receive_code,'999999.00000000','0.00010000')]
   ui_codes={};ux={}
   for name,code,amount,fee in tests:
    sync(app,window);before=(reservations(session),rpc._call('getrawmempool',[]),session.vault.anchor.read())
    window.navigation.setCurrentRow(3);window.recipient.setText(code);window.amount.setText(amount);window.fee.setText(fee)
    response=operation(app,window,'prepare',window.prepare_button.click,denied=True)
    after=(reservations(session),rpc._call('getrawmempool',[]),session.vault.anchor.read())
    record(name+'_safe_refusal',before==after and session._signed is None and session._prepared is None)
    ui_codes[name]=response['code'];ux[name]={'status':window.status.text(),'badge':window.verification_badge.text(),'faulted':session.faulted,'locked':session.locked}
    if name in ('fee_zero','recipient_standard_core','insufficient_funds'):assert window.grab().save(str(OUT/(name+'.png')))
   (OUT/'INPUT_FAILURE_REPRODUCTION.json').write_text(json.dumps({'cases':ux,'signals':ui_codes},indent=2)+'\n')
   record('specific_input_error_feedback',len(set(ui_codes.values()))>=4,signals=ui_codes)
   record('validation_error_not_core_failure',all(v['badge']!='Not verified' for v in ux.values()),cases=ux)
   sync(app,window)
   # Two genuine transactions: another random WSP wallet, then self-payment.
   for mode,code,atoms,fee in [('other',receiver.accounts()[0].payment_code(),100000,10000),('self',initial.receive_code,200000,10000)]:
    start=session.snapshot();window.apply_snapshot(start);window.navigation.setCurrentRow(3)
    window.recipient.setText(code);window.amount.setText(format_wam(atoms));window.fee.setText('0.00010000')
    review=operation(app,window,'prepare',window.prepare_button.click)['value']
    selected=sum(c['atoms'] for c in session._prepared.proposal.coins)
    record(mode+'_exact_review',review.code==code and review.atoms==atoms and review.fee==fee and review.change_atoms==selected-atoms-fee and code in window.review_text.text())
    before=reservations(session);_approve_dialog(app,window,window.sign_button,approve=False)
    record(mode+'_sign_cancel',session._signed is None and reservations(session)==before and not rpc._call('getrawmempool',[]))
    operation(app,window,'sign',lambda:_approve_dialog(app,window,window.sign_button,approve=True))
    record(mode+'_sign_approved',session._signed is not None and not window.cancel_button.isEnabled())
    _approve_dialog(app,window,window.broadcast_button,approve=False)
    record(mode+'_broadcast_cancel',not rpc._call('getrawmempool',[]) and session._signed is not None)
    txid=operation(app,window,'broadcast',lambda:_approve_dialog(app,window,window.broadcast_button,approve=True))['value']
    pending=sync(app,window)
    record(mode+'_real_pending',txid in rpc._call('getrawmempool',[]) and pending.confirmed_atoms==start.confirmed_atoms,pending_label=window.status.text(),review_text=window.review_text.text(),confirmed_balance_unchanged=True)
    record(mode+'_pending_gui_feedback',any(word in (window.status.text()+' '+window.review_text.text()).lower() for word in ('pending','submitted','unconfirmed')))
    final=operation(app,window,'mine',window.mine_button.click)['value'];final=sync(app,window)
    expect=start.confirmed_atoms-fee-(atoms if mode=='other' else 0)
    rows=[r for r in final.history if r.txid==txid];rscan.sync(rpc)
    record(mode+'_confirmed_math',final.confirmed_atoms==expect and len(rows)==1 and rows[0].confirmations==1,before_atoms=start.confirmed_atoms,after_atoms=final.confirmed_atoms,payment_atoms=atoms,fee_atoms=fee,history_credit=rows[0].credit_atoms,history_debit=rows[0].debit_atoms)
    if mode=='other':record('recipient_independent_scanner',Wallet(rscan).balance()['confirmed_atoms']==atoms)
    assert window.grab().save(str(OUT/(mode+'-confirmed.png')))
   # Native background sync while a timer verifies responsiveness.
   events=[];heartbeat=QTimer();heartbeat.timeout.connect(lambda:events.append(time.monotonic()));heartbeat.start(10)
   window._sync_timer.setInterval(50);window._sync_timer.start();snap=sync(app,window);window._sync_timer.stop();heartbeat.stop()
   record('native_background_sync_responsiveness',len(events)>0 and window._worker is None,timer_ticks=len(events),production_interval_ms=30000)
   window._sync_timer.setInterval(30000)
   _capture_fusion_views(app,window)
   record('native_resize_theme_screenshots',True,qt_platform=app.platformName(),font_family=QFontInfo(app.font()).family(),human_typography_review='PENDING_OPERATOR')
   # Latest backup remains available after a rejected restore; no anchor reset.
   latest=data/'latest-backup';custody.create_directory(latest);operation(app,window,'backup',lambda:window.start_operation('backup',latest,'wallet-backup.enc'))
   expected=session.snapshot().confirmed_atoms;before_anchor=session.vault.anchor.read();operation(app,window,'lock',window.lock_button.click)
   record('lock_redaction',session.locked and not session.runtime.exists() and window.balance_text.text()=='—' and window.receive_page.code is None and not window.prepare_button.isEnabled())
   operation(app,window,'unlock',lambda:window.start_operation('unlock',b'wrong-public-audit-password'),denied=True)
   record('wrong_password_refusal',session.locked and not session.runtime.exists() and session.vault.anchor.read()==before_anchor)
   bad=data/'malformed-backup';custody.create_directory(bad);custody.storage().publish(bad,'wallet-backup.enc',b'WAMSP02\x00'+b'corrupt-authenticated-payload'*4)
   operation(app,window,'recover',lambda:window.start_operation('recover',bad,'wallet-backup.enc',password),denied=True)
   record('malformed_recovery_refusal',session.locked and session.vault.anchor.read()==before_anchor and not session.runtime.exists())
   operation(app,window,'recover',lambda:window.start_operation('recover',latest,'wallet-backup.enc',b'wrong-public-audit-password'),denied=True)
   record('wrong_recovery_password_refusal',session.locked and session.vault.anchor.read()==before_anchor and not session.runtime.exists())
   restored=operation(app,window,'recover',lambda:window.start_operation('recover',latest,'wallet-backup.enc',password))['value']
   record('latest_backup_recovery',not session.locked and restored.confirmed_atoms==expected and session.vault.anchor.read()==before_anchor)
   operation(app,window,'lock',window.lock_button.click);unlocked=operation(app,window,'unlock',lambda:window.start_operation('unlock',password))['value']
   record('correct_unlock',unlocked.confirmed_atoms==expected and not session.locked)
  finally:
   if window is not None:settle(app,window);window.close();window.deleteLater();app.processEvents()
   for obj in (rscan,receiver,session):
    if obj is not None:obj.close()
   if created:subprocess.run(['/usr/bin/security','delete-keychain',str(keychain)],check=True,capture_output=True)
 shutdown_qt()

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--core',type=Path,required=True);parser.add_argument('--wsp-source',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
 args=parser.parse_args();OUT=args.output.resolve();OUT.mkdir(exist_ok=False);os.chdir(OUT)
 sys.path.insert(0,str(OUT.parent/'test-deps'))
 audit(args.core.resolve(),args.wsp_source.resolve())
 failures=sum(r['status']=='FAIL' for r in RESULTS)
 print('OWNER_REAL_CORE_AUDIT_COMPLETE',len(RESULTS),'checks',failures,'failures',flush=True)
 raise SystemExit(1 if failures else 0)
