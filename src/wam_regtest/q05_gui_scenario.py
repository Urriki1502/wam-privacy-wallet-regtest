"""Explicit disposable qualification of the normal managed Qt/owner bridge.

Fixture funding/mining and simulated approval clicks are TEST ONLY. Actual
wallet/scanner/signature/broadcast and Qt code are unchanged, never mocked.
"""
from datetime import datetime,timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time

from .wallet_executor import ManagedWalletBackend
from .q05_platforms import detect_adapter
from .core import verified_core_paths
from .probe_source import verify_source
from .wsp_live import PINNED_WSP_COMMIT,_pinned_source,public_regtest_mining_address,_public_fixture_payment

PASSWORD=b'public-q05-gui-disposable-only'


class LabBackend(ManagedWalletBackend):
    """Only extra actions are public fixture funding/mining on the SAME owner."""
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.lab=None;self.broadcast_entered=threading.Event();self.broadcast_release=threading.Event()
        self.submissions=0
    def execute(self,action,args,kwargs):
        if action=='broadcast':
            self.broadcast_entered.set()
            if not self.broadcast_release.wait(10):raise ValueError('Q05_GUI_BROADCAST_BARRIER_TIMEOUT')
            self.submissions+=1
        if action=='network' and self.lab=='fund':
            from .managed_wallet_session import check_session
            from .wallet_session import WalletCoreCli
            from wam_sp.keystore import Keyring
            check_session(self.session)
            rpc=WalletCoreCli(self.owner.cli,self.owner.directory);rpc.attest()
            try:
                rpc._call('generatetoaddress',['101',self.mining_address])
                txid,atoms,height=_public_fixture_payment(rpc,self.session.ring.accounts()[0],self.mining_address)
            finally:
                if getattr(rpc,'_transport',None) is not None:rpc._transport.close()
            recipient=Keyring()
            try:code=recipient.accounts()[0].payment_code()
            finally:recipient.close()
            self.lab=None
            return {'fixture_payment':txid,'atoms':atoms,'height':height,'recipient':code}
        return super().execute(action,args,kwargs)


class Driver:
    def __init__(self,window,backends,record,timeout,screenshot):
        from PySide6.QtCore import QTimer
        self.window=window;self.backends=backends;self.record=record;self.stage='password'
        self.deadline=time.monotonic()+timeout;self.screenshot=screenshot;self.snapshot=None
        self.events=[];self.errors=[];self.ticks=0;self.original=None
        window.background_available=True
        window.operation_completed.connect(lambda a,r:self.events.append((a,r)))
        window.operation_failed.connect(self.errors.append)
        self.timer=QTimer(window);self.timer.setInterval(10);self.timer.timeout.connect(self.tick);self.timer.start()
    def fail(self,code):
        self.record.update(status='FAIL',failure_stage=self.stage,failure_code=code)
        self.stage='failed';self.window.request_quit()
    def idle(self):return self.window._worker is None and not self.window.session.executor.busy
    def approve(self,kind):
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
        from .fusion_pages import PaymentApproval
        self.timer.stop();problems=[]
        def click():
            dialog=QApplication.activeModalWidget()
            if type(dialog) is not PaymentApproval:
                problems.append('Q05_APPROVAL_DIALOG_MISSING')
                if dialog is not None:dialog.reject()
                return
            if not dialog.cancel.isDefault():problems.append('Q05_APPROVAL_NOT_DEFAULT_CANCEL')
            dialog.approve.click()
        QTimer.singleShot(20,click)
        self.window.approve_payment(kind)
        self.timer.start()
        if problems:raise ValueError(problems[0])
    def tick(self):
        from PySide6.QtWidgets import QApplication,QInputDialog
        self.ticks+=1
        if self.stage=='failed':return
        try:
            if time.monotonic()>self.deadline:raise ValueError('Q05_GUI_SCENARIO_TIMEOUT')
            if self.errors:raise ValueError(self.errors[-1])
            w=self.window
            if self.stage=='password':
                dialog=QApplication.activeModalWidget()
                if type(dialog) is QInputDialog:
                    dialog.setTextValue(PASSWORD.decode());dialog.accept();self.stage='opened'
                return
            if not self.backends:return
            b=self.backends[0]
            if self.stage=='opened' and self.idle() and w._snapshot is not None:
                snap=w._snapshot
                if snap.height!=0 or snap.confirmed_atoms!=0:raise ValueError('Q05_NORMAL_CREATE_NOT_EMPTY')
                self.original=b.owner.process
                if type(self.original) is not subprocess.Popen or self.original.poll() is not None:
                    raise ValueError('Q05_GUI_ORIGINAL_POPEN_REQUIRED')
                self.record['observations'].append({'normal_managed_create':True,'height':0,
                    'original_core_pid':self.original.pid,'wallet_execution_thread':w.session.executor._thread.ident})
                b.lab='fund';w.start_operation('network');self.stage='funding'
            elif self.stage=='funding' and self.idle():
                data=next((r for a,r in reversed(self.events) if a=='network'),None)
                if data is None:raise ValueError('Q05_FIXTURE_FUNDING_NOT_OBSERVED')
                self.funding=data;w.request_sync();self.stage='received'
            elif self.stage=='received' and self.idle():
                snap=w._snapshot
                if snap is None or snap.confirmed_atoms!=self.funding['atoms'] or snap.history_count!=1:
                    raise ValueError('Q05_GUI_REAL_RECEIVING_DENIED')
                self.record['observations'].append({'real_bip352_received':True,
                    'fixture_txid':self.funding['fixture_payment'],'history_sha256':snap.history_sha256})
                w.recipient.setText(self.funding['recipient']);w.amount.setText('0.00100000');w.fee.setText('0.00010000')
                w.prepare_payment();self.stage='prepared'
            elif self.stage=='prepared' and self.idle():
                if w.review is None:raise ValueError('Q05_GUI_PREPARE_DENIED')
                self.stage='signing';self.approve('sign')
            elif self.stage=='signing' and self.idle():
                if not w.signed:raise ValueError('Q05_GUI_SIGN_DENIED')
                self.stage='broadcasting';self.approve('broadcast')
            elif self.stage=='broadcasting' and b.broadcast_entered.is_set():
                before=self.ticks;w.close()
                if not w.isVisible() or not w.session.executor.busy:
                    raise ValueError('Q05_GUI_UNSAFE_INFLIGHT_CLOSE')
                self.record['observations'].append({'close_during_approved_broadcast_deferred':True,
                    'qt_timer_alive_during_operation':before>0})
                b.broadcast_release.set();self.stage='closed'
            elif self.stage=='closed' and self.idle() and w.session.locked and not w.isVisible():
                if b.owner.process is not self.original or self.original.poll() is not None:
                    raise ValueError('Q05_GUI_CLOSE_CHANGED_CORE')
                txid=next((r for a,r in reversed(self.events) if a=='broadcast'),None)
                if type(txid) is not str or not re.fullmatch('[0-9a-f]{64}',txid):
                    raise ValueError('Q05_GUI_REAL_BROADCAST_NOT_OBSERVED')
                self.sent=txid;w.reopen();self.timer.stop()
                from PySide6.QtCore import QTimer
                def password():
                    dialog=QApplication.activeModalWidget()
                    if type(dialog) is QInputDialog:dialog.setTextValue(PASSWORD.decode());dialog.accept()
                QTimer.singleShot(20,password);w.unlock_wallet();self.timer.start();self.stage='reopened'
            elif self.stage=='reopened' and self.idle() and not w.session.locked:
                w.start_operation('mine');self.stage='confirmed'
            elif self.stage=='confirmed' and self.idle():
                snap=w._snapshot
                if snap is None or not any(r.txid==self.sent and r.confirmations>0 for r in snap.history):
                    raise ValueError('Q05_GUI_CONFIRMED_HISTORY_MISSING')
                if b.submissions!=1:raise ValueError('Q05_GUI_DUPLICATE_SUBMISSION')
                if tuple(r.txid for r in w.history_page.rows)!=tuple(r.txid for r in snap.history):
                    raise ValueError('Q05_GUI_HISTORY_PRESENTATION_MISMATCH')
                self.snapshot=snap
                self.record['observations'].append({'real_gui_prepare_sign_broadcast_confirm':True,
                    'txid':self.sent,'history_sha256':snap.history_sha256,
                    'reservation_sha256':snap.reservation_sha256,'wallet_close_reopen_same_core':True,
                    'wallet_submissions':b.submissions,'simulated_test_operator_approval':True})
                if self.screenshot:
                    if not w.grab().save(str(self.screenshot)):raise ValueError('Q05_GUI_SCREENSHOT_DENIED')
                w.start_operation('lock');self.stage='locked_for_crash'
            elif self.stage=='locked_for_crash' and self.idle() and w.session.locked:
                from .supervisor_client import control
                # HMAC status is queried off the UI thread via the normal
                # control-only channel in a separate bounded test client.
                self.record['original_profile']=b.owner.profile['profile_id']
                if b.owner.process is not self.original or self.original.poll() is not None:
                    raise ValueError('Q05_GUI_CRASH_ORIGINAL_OWNER_DENIED')
                self.original.kill();self.original.wait(timeout=10)
                w._control('core_restart');self.stage='core_restarted'
            elif self.stage=='core_restarted' and self.idle():
                if b.owner.process is self.original or b.owner.process.poll() is not None:
                    raise ValueError('Q05_GUI_SAME_OWNER_CRASH_RECOVERY_DENIED')
                w._control('open',PASSWORD);self.stage='restored'
            elif self.stage=='restored' and self.idle():
                snap=w._snapshot;before=self.snapshot
                if snap is None or any(getattr(snap,k)!=getattr(before,k) for k in
                        ('height','tip','receive_code','history_sha256','reservation_sha256','confirmed_atoms')):
                    raise ValueError('Q05_GUI_CRASH_RECOVERY_IDENTITY_CHANGED')
                if b.submissions!=1:raise ValueError('Q05_GUI_UNCERTAIN_REPLAY')
                self.record['observations'].append({'same_owner_core_crash_recovered':True,
                    'same_wallet_tip_history_reservations':True,'original_popen_reaped':self.original.poll() is not None,
                    'automatic_wallet_replay':False})
                self.record['status']='PASS';self.stage='quitting';w.request_quit()
        except Exception as error:
            code=error.args[0] if len(error.args)==1 and type(error.args[0]) is str else 'Q05_GUI_SCENARIO_DENIED'
            if not re.fullmatch('[A-Z][A-Z0-9_]{1,95}',code):code='Q05_GUI_SCENARIO_DENIED'
            self.fail(code)


def run_scenario(core,source,root,receipt,*,confirmed=False,linux_manifest=None,
                 linux_witness=None,test_witness=False,max_seconds=300):
    if (confirmed is not True or not root.is_absolute() or root.exists() or root.is_symlink()
            or not re.fullmatch('wam-fusion-core-[0-9a-f]{16}',root.name)
            or not receipt.is_absolute() or receipt.exists() or receipt.is_symlink()
            or type(max_seconds) is not int or not 60<=max_seconds<=600):
        raise ValueError('Q05_GUI_DISPOSABLE_SCOPE_DENIED')
    project=Path(__file__).resolve().parents[2];proof=verify_source(project)
    adapter=detect_adapter();adapter.enforce_host();_pinned_source(source)
    record={'schema':'q05-executor-gui-native/v1','status':'FAIL','source_provenance':proof,
        'source_sha':proof['candidate_source_sha'],'checkout_sha':proof['checkout_sha'],
        'platform':adapter.platform_id,'core_version':'v0.1.11','core_trust':adapter.core_trust,
        'official_signed_release':adapter.official_signed,'wsp_source_commit':PINNED_WSP_COMMIT,
        'synthetic_rpc':False,'frozen':False,'physical_acceptance':False,'mainnet_allowed':False,
        'test_root_witness':test_witness,'profile_root':str(root),'observations':[]}
    backends=[];window_holder=[]
    try:
        adapter.prepare_trust(core,linux_manifest,linux_witness,test_witness=test_witness)
        node,cli,_=verified_core_paths(core)
        record['core_sha256']={p.name:sha256(p.read_bytes()).hexdigest() for p in (node,cli)}
        address=public_regtest_mining_address(source)
        def factory():
            b=LabBackend(root,core,source,mining_address=address,_anchor_factory=adapter.make_anchor)
            backends.append(b);return b
        def hook(window):
            window_holder.append(window)
            window._qualification_driver=Driver(window,backends,record,max_seconds,
                receipt.with_name(receipt.stem+'-window.png'))
        from .managed_gui import launch_managed
        launch_managed(root,core,source,authorized=True,create=True,_backend_factory=factory,_window_hook=hook)
        if not window_holder[0].session.executor.closed:raise ValueError('Q05_GUI_ORIGINAL_OWNER_STILL_ACTIVE')
        record['owner_shutdown_verified']=True
    except Exception as error:
        record['status']='FAIL';record['failure_type']=type(error).__name__
        record.setdefault('failure_code','Q05_GUI_SCENARIO_DENIED')
    finally:
        safe=not window_holder or window_holder[0].session.executor.closed
        if safe:adapter.teardown()
        else:record['original_owner_retained']=True
        # Profiles and all failed ciphertext/runtime remain untouched.
        record['timestamp_utc']=datetime.now(timezone.utc).isoformat()
        with receipt.open('x') as out:json.dump(record,out,indent=2);out.write('\n')
    return record
