"""Actual two-owned-Core Cocoa/BIP39/BIP352 lab; no physical two-host claim.

Uses the normal owner, widgets, custody and manual Core P2P config. All profiles
are new disposable data retained after failures. No test RPC is added to GUI.
"""
from pathlib import Path
import json
import os
import secrets
import sys
import time
from datetime import datetime, timezone
from hashlib import sha256

from .shared_regtest import SharedRegtestProfile
from .wallet_executor import WalletExecutor
from .bip39_owner_backend import Bip39ReadOnlyBackend

# Same-host qualification only. Product/deployment defaults remain 29554/29555.
# The owner explicitly reserved the historical standard-port labs read-only.
LAB_PORTS=((True,45954,45955,45957),(False,45956,45957,45955))


def click_visible_approval(app, caption):
    """Click an explicit approval on any visible dialog, not only the active modal.

    Two Fusion windows make a WindowModal Sign/Broadcast dialog easy to miss via
    activeModalWidget(); the operator action is still the labeled QPushButton.
    """
    from PySide6.QtWidgets import QDialog, QPushButton
    for widget in app.allWidgets():
        if not isinstance(widget, QDialog) or not widget.isVisible():
            continue
        for control in widget.findChildren(QPushButton):
            if control.text() == caption and control.isEnabled():
                # QPushButton.click() can be delivered while the dialog is
                # still showing. Emit the same clicked signal the button uses
                # so Accept runs on the main loop that opened the dialog.
                control.clicked.emit()
                return True
    return False


def qualify(core, source):
    from .desktop import qt_application
    from .q05_platforms import DarwinArm64Adapter
    from .bip39_fusion_gui import Bip39FusionWindow
    from .custody import create_directory
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QDialog, QPushButton, QLineEdit
    app = qt_application()
    if app.platformName() != 'cocoa':
        raise ValueError('SHARED_NATIVE_COCOA_REQUIRED')
    adapter = DarwinArm64Adapter()
    adapter.enforce_host()
    parent = Path.cwd()/'bundle-input'
    parent.mkdir(mode=0o700,exist_ok=True)
    lab = parent/('shared-regtest-'+secrets.token_hex(8))
    create_directory(lab)
    report = dict(status='FAIL',network='regtest',two_physical_computers=False,
                  owner_accepted=False,independent_reviewed=False,
                  cases={f'V{i}':'NOT EXECUTED' for i in range(1,20)})
    report['cases']['V19'] = 'BLOCKED'
    report['lab_port_layout']=[dict(coordinator=c,rpc=r,p2p=p,peer=q) for c,r,p,q in LAB_PORTS]
    report['deployment_defaults']=dict(rpc=29554,p2p=29555)
    if getattr(sys,'frozen',False):
        from .q05_package_provenance import read
        report['source_sha'] = read()['candidate_source_sha']
        report['executable_sha256'] = sha256(Path(sys.executable).read_bytes()).hexdigest()
    else:
        from .build_provenance import capture,public_receipt
        from .probe_source import verify_source
        repository=Path(__file__).resolve().parents[2]
        proof=verify_source(repository)
        receipt=public_receipt(capture(repository))
        report['source_sha']=receipt['checkout_sha']
        report['source_inventory_sha256']=receipt['native_source_inventory_sha256']
        report['raw_python_tree_sha256']=proof['raw_python_tree_sha256']
        report['literal_source_verified']=True
    nodes = []
    password = b'public-disposable-shared-regtest-lab-only'
    def stage(name):
        report['last_stage'] = name
        print('SHARED_REGTEST_STAGE='+name,flush=True)
    def wait(predicate, label, timeout=240):
        deadline = time.monotonic()+timeout
        next_beat = time.monotonic()
        while not predicate():
            app.processEvents()
            if any('window' in n and idle(n) and n['window']._last_error_code for n in nodes):
                raise ValueError('SHARED_GUI_OPERATION_DENIED')
            now = time.monotonic()
            if now >= next_beat:
                next_beat = now + 5
                alive = []
                for node in nodes:
                    executor = node.get('executor')
                    window = node.get('window')
                    if executor is None or window is None:
                        continue
                    alive.append(
                        'busy=' + ('1' if executor.busy else '0')
                        + ' worker=' + ('1' if window._worker is not None else '0')
                        + ' delivering=' + ('1' if window._delivering_result else '0')
                        + ' core=' + ('1' if executor.state.core_alive is True else '0'))
                print('SHARED_REGTEST_LIVENESS wait=' + label
                      + ' modal=' + ('1' if app.activeModalWidget() is not None else '0')
                      + ' ' + ' '.join(alive), flush=True)
            if now > deadline:
                raise ValueError('SHARED_WAIT_'+label)
            time.sleep(.01)
        app.processEvents()
    def idle(node):
        w,e = node['window'],node['executor']
        return w._worker is None and not w._delivering_result and not e.busy
    def approve(node,button,caption,predicate,*,credential=None):
        if not button.isEnabled():
            raise ValueError('SHARED_GUI_APPROVAL_DISABLED')
        timer = QTimer()
        timer.setInterval(120)
        def consent():
            dialog = app.activeModalWidget()
            if credential is not None and isinstance(dialog,QDialog):
                for field in dialog.findChildren(QLineEdit):
                    if field.echoMode()==QLineEdit.EchoMode.Password:
                        field.setText(credential.decode('utf-8'))
            # Keep looking until the caller leaves this approval. Stopping
            # on the first click drops a press that the dialog did not accept.
            click_visible_approval(app, caption)
        timer.timeout.connect(consent)
        timer.start()
        try:
            button.click()
            wait(lambda:idle(node) and predicate(),'GUI_APPROVAL')
        finally:
            timer.stop()
    def state(node):
        return node['executor'].request('network_status',timeout=120)
    def connected():
        states = [state(n) for n in nodes]
        report['network_states'] = states
        return len(states)==2 and all(s['connected'] for s in states)
    def sync():
        states = [state(n) for n in nodes]
        report['network_states'] = states
        return len(states)==2 and states[0]['height']==states[1]['height'] and states[0]['tip']==states[1]['tip']
    def start(node,create):
        root,profile = node['root'],node['profile']
        options = ({'_anchor_factory':adapter.make_anchor} if create else
                   {'keychain':adapter.reopen_anchor(root)})
        e = WalletExecutor(lambda:Bip39ReadOnlyBackend(root,core,source,shared_profile=profile,**options))
        w = Bip39FusionWindow(e,shared_profile=profile)
        node.update(executor=e,window=w)
        w.show()
        w.start(password,'create' if create else 'reopen','')
        if create:
            wait(lambda:idle(node) and w._backup_flow_active,'CREATE')
            created = dict(w._backup_result)
            node['receive_code'] = created['receive_code']
            backup = w.backup_page
            backup._written_check.setChecked(True)
            backup._back_up_now.click()
            words = created.pop('mnemonic_once').split()
            for position,field in zip(backup._challenge_positions,backup._verify_inputs):
                field.setText(words[position-1])
            backup._verify_button.click()
            backup._continue_button.click()
            words = None
            wait(lambda:idle(node) and w._last_verified is not None,'BACKUP')
        else:
            wait(lambda:idle(node) and w._ready,'REOPEN')
        if w._last_error_code:
            raise ValueError('SHARED_WALLET_OPEN_DENIED')
    def stop(node):
        e,w=node['executor'],node['window']
        w._poll.stop()
        e.request('quit',timeout=120)
        if not e.join(15):raise ValueError('SHARED_OWNED_STOP_DENIED')
        # Destroy while QApplication still lives, after the original owner
        # has exited. Never leave top-level/modal wrappers to interpreter exit.
        from PySide6.QtCore import QCoreApplication, QEvent
        w._closed = True
        w.close()
        w.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        app.processEvents()
    try:
        for coordinator,rpc,p2p,peer in LAB_PORTS:
            node={'root':lab/('wam-fusion-core-'+secrets.token_hex(8)),
                  'profile':SharedRegtestProfile('127.0.0.1',coordinator=coordinator,
                               rpc_port=rpc,p2p_port=p2p,peer_port=peer)}
            nodes.append(node)
            start(node,True)
            stage('NODE_'+('A' if coordinator else 'B')+'_BIP39_BACKUP')
        a,b=nodes
        wait(connected,'HANDSHAKE',90)
        if any(s['height']!=0 or s['genesis']!='b88f3d262f285e38e184f50bf3eea1c8e615486ae67d3d9eaf0976fbd6d3d30d' for s in report['network_states']):
            raise ValueError('SHARED_GENESIS_OR_PREMINING_DENIED')
        report['premining_states'] = report['network_states']
        for i in (1,2,3,8):report['cases'][f'V{i}']='PASS'
        # Backend and original CLI route must both retain one-coordinator rule.
        try:b['executor'].request('mine',timeout=120)
        except ValueError as error:
            if error.args!=('SHARED_SINGLE_COORDINATOR_REQUIRED',):raise
        else:raise ValueError('SHARED_PARTICIPANT_MINED')
        funded = a['executor'].request('mine',timeout=240)
        wait(sync,'BLOCK_SYNC')
        report['funding'] = funded
        for i in (4,5,6,7):report['cases'][f'V{i}']='PASS'
        stage('MATURE_FUNDING_AND_BLOCK_SYNC')
        for node in nodes:
            node['window']._command('snapshot')
            wait(lambda node=node:idle(node),'SNAPSHOT')
            approve(node,node['window'].activate,'Approve',lambda node=node:node['window']._spend_enabled)
            stage('NODE_'+('A' if node['profile'].coordinator else 'B')+'_CHECKPOINT')
        w=a['window']
        w.recipient_input.setText(b['receive_code'])
        w.amount_input.setText('3')
        w.fee_input.setText('0.00010000')
        approve(a,w.send,'Approve Sign',lambda:w._signed_ready)
        report['cases']['V9']='PASS'
        approve(a,w.broadcast,'Approve Broadcast',lambda:w._pending_confirm_txid is not None)
        txid=w._pending_confirm_txid
        report['txid']=txid
        report['cases']['V10']='PASS'
        wait(lambda:txid in state(b)['mempool'],'MEMPOOL')
        report['relayed_mempool']=state(b)
        report['cases']['V11']='PASS'
        approve(a,w.confirm,'Approve',lambda:w._pending_confirm_txid is None)
        wait(sync,'CONFIRM_SYNC')
        snapshots=[]
        for node in nodes:
            node['window']._command('snapshot')
            wait(lambda node=node:idle(node),'CONFIRMED_SNAPSHOT')
            snapshots.append(node['executor'].request('snapshot',timeout=240))
        if snapshots[1]['confirmed_atoms']!=300000000 or not any(h['txid']==txid for h in snapshots[1]['history']):
            raise ValueError('SHARED_BIP352_RECEIVE_DENIED')
        if not all(n['window']._last_verified is not None and txid in n['window'].history.toPlainText() for n in nodes):
            raise ValueError('SHARED_GUI_HISTORY_DENIED')
        report['confirmed']={k:snapshots[1][k] for k in ('height','tip','confirmed_atoms','history')}
        report['reservation_counts']=[s['reservation_count'] for s in snapshots]
        for i in (12,13,14):report['cases'][f'V{i}']='PASS'
        stage('BIP352_CONFIRMED_BOTH_GUI_HISTORIES')
        for index,node in enumerate(nodes):
            node['window'].grab().save(str(lab/f'node-{index}-confirmed.png'))
        a['executor'].request('network_active',False)
        wait(lambda:not state(b)['connected'],'DISCONNECT',90)
        # No automatic sign/broadcast/mining while isolated from the peer.
        try:a['executor'].request('prepare',b['receive_code'],100000000,10000)
        except ValueError as error:
            if error.args!=('SHARED_CONFIRMED_PEER_REQUIRED',):raise
        else:raise ValueError('SHARED_DISCONNECTED_PREPARE_ALLOWED')
        a['executor'].request('network_active',True)
        wait(connected,'RECONNECT',120)
        wait(sync,'RECONNECT_SYNC')
        report['cases']['V15']='PASS'
        stage('DISCONNECT_RECONNECT_PRESERVED')
        for node in reversed(nodes):stop(node)
        for node in nodes:start(node,False)
        wait(connected,'RESTART_HANDSHAKE',120)
        for index,node in enumerate(nodes):
            approve(node,node['window'].activate,'Approve',lambda node=node:node['window']._spend_enabled)
            current=node['executor'].request('snapshot',timeout=240)
            if (current['receive_code']!=node['receive_code'] or current['confirmed_atoms']!=snapshots[index]['confirmed_atoms']
                    or current['reservation_count']!=snapshots[index]['reservation_count']):
                raise ValueError('SHARED_RESTART_STATE_CHANGED')
        report['cases']['V16']='PASS'
        stage('SAME_PROFILES_RESTART_CHECKPOINTS_PRESERVED')
        for node in reversed(nodes):stop(node)
        report['reorg'] = qualify_reorg(nodes,core,source,password,txid)
        stage('REAL_REORG_FAIL_CLOSED_PASS')
        for node in nodes:start(node,False)
        wait(connected,'REORG_RECOVERY_PEERS',120)
        reconciled=[]
        for index,node in enumerate(nodes):
            window=node['window']
            approve(node,window.reconcile_button,'Reconcile',
                    lambda window=window:window._last_reconciliation is not None,credential=password)
            proof=window._last_reconciliation
            if (window._spend_enabled or proof['signing_authorized'] is not False
                    or proof['automatic_broadcast'] is not False or proof['reservations_preserved'] is not True):
                raise ValueError('SHARED_REORG_CONSENT_SCOPE_DENIED')
            approve(node,window.activate,'Approve',lambda window=window:window._spend_enabled)
            observed=node['executor'].request('snapshot',timeout=240)
            if (observed['receive_code']!=node['receive_code']
                    or observed['confirmed_atoms']!=snapshots[index]['confirmed_atoms']
                    or observed['reservation_count']!=snapshots[index]['reservation_count']
                    or sum(h['txid']==txid for h in observed['history'])!=1
                    or txid not in window.history.toPlainText()):
                raise ValueError('SHARED_REORG_RECONCILED_HISTORY_DENIED')
            node['reconciled_state']=tuple(observed[k] for k in ('height','tip','confirmed_atoms','reservation_count'))
            reconciled.append(dict(proof))
            window.grab().save(str(lab/f'node-{index}-reconciled.png'))
        for node in reversed(nodes):stop(node)
        for node in nodes:start(node,False)
        wait(connected,'RECONCILED_RESTART_PEERS',120)
        for node in nodes:
            approve(node,node['window'].activate,'Approve',lambda node=node:node['window']._spend_enabled)
            observed=node['executor'].request('snapshot',timeout=240)
            if tuple(observed[k] for k in ('height','tip','confirmed_atoms','reservation_count'))!=node['reconciled_state']:
                raise ValueError('SHARED_REORG_RESTART_CHANGED')
        report['reorg'].update(status='PASS_EXPLICIT_AUTHENTICATED_GUI_RECOVERY',
            reconciliation=reconciled,explicit_gui_reconciliation=True,
            post_recovery_same_profile_restart=True,recovery_status='PASS',automatic_reorg_wallet_recovery=False)
        report['cases']['V17']='PASS'
        stage('REAL_REORG_GUI_RECONCILIATION_AND_RESTART_PASS')
        report['status']='PASS_SCOPED_EXECUTED_CASES'
        return report
    except Exception as error:
        if isinstance(error,ValueError) and error.args and type(error.args[0]) is str:
            report['denied']=error.args[0]
        report['gui_denied']=[n['window']._last_error_code for n in nodes if 'window' in n]
        raise
    finally:
        # Persist before touching Qt: even a native GUI cleanup crash must
        # leave an honest failed-case receipt and retained profile paths.
        report['timestamp_utc']=datetime.now(timezone.utc).isoformat()
        report['retained_lab']=str(lab)
        (lab/'public-evidence.json').write_text(json.dumps(report,indent=2)+'\n')
        retained=False
        for node in reversed(nodes):
            if 'executor' not in node or node['executor'].closed:
                continue
            if node['executor'].busy:
                stage('UNCERTAIN_ORIGINAL_OWNER_RETAINED')
                retained=True
                continue
            try:stop(node)
            except Exception:
                stage('UNCERTAIN_ORIGINAL_OWNER_RETAINED')
                retained=True
        (lab/'public-evidence.json').write_text(json.dumps(report,indent=2)+'\n')
        if retained:
            # QApplication.shutdown() destroys QThread children while the
            # original ControlWorker/owner threads are still running (SIGABRT).
            # Leave those processes as original owners; do not Qt-teardown them.
            os._exit(2)


def run(core,source):
    result=qualify(core,source)
    Path('shared-network-evidence.json').write_text(json.dumps(result,indent=2)+'\n')
    return 0


def qualify_reorg(nodes,core,source,password,txid):
    """Reopen original disposable profiles, fork via existing Core RPC only.

    No test-only command is added to the wallet executor or GUI. These are
    original main-thread Popen owners after both GUI executors cleanly quit.
    """
    from .core_supervisor import CoreSupervisor
    from .core import _read_cli
    from .shared_regtest import peer_status
    from .bip39_spend_session import open_owned_spend_session
    from .wsp_live import public_regtest_mining_address
    owners,sessions=[],[]
    result=None
    def rpc(owner,method,*args):
        return _read_cli([str(owner.cli),'-datadir='+str(owner.directory),method,*args])
    def wait_for(predicate):
        deadline=time.monotonic()+120
        while not predicate():
            if time.monotonic()>deadline:raise ValueError('SHARED_REORG_SYNC_TIMEOUT')
            time.sleep(.2)
    try:
        for node in nodes:
            owner=CoreSupervisor(node['root'],core,authorized=True,shared_profile=node['profile'])
            owners.append(owner)
            owner.start()
        wait_for(lambda:all(peer_status(o.directory)['connected'] for o in owners))
        for owner,node in zip(owners,nodes):
            folders=[p for p in owner.directory.glob('bip39-12-*') if not p.name.startswith('bip39-12-scan-')]
            if len(folders)!=1:raise ValueError('SHARED_REORG_ORIGINAL_SEED_REQUIRED')
            sessions.append(open_owned_spend_session(owner,folders[0],source,password,
                            authorized=True,keychain=node['root']/'q05-disposable.keychain-db'))
        before=[s.snapshot() for s in sessions]
        original_tip=before[0].tip
        height=before[0].height
        rpc(owners[0],'invalidateblock',original_tip)
        # Native Q06 deliberately refuses a non-descendant anchor advance.
        # A live Core reorg must retain irreversible reservations and lock
        # custody; this probe must not weaken that floor to force recovery.
        held=sessions[0].scanner.store.db.execute('SELECT txid,vout,token,state,created FROM reservations ORDER BY txid,vout').fetchall()
        anchor=sessions[0].vault.anchor.read()
        try:sessions[0].snapshot()
        except ValueError as error:
            if error.args!=('Q06_SPEND_ANCHORED_SAVE_DENIED',):raise
        else:raise ValueError('SHARED_REORG_NATIVE_FLOOR_BYPASSED')
        if (not sessions[0].faulted or not sessions[0]._q06_uncertain
                or sessions[0].vault.anchor.read()!=anchor
                or sessions[0].scanner.store.db.execute('SELECT txid,vout,token,state,created FROM reservations ORDER BY txid,vout').fetchall()!=held):
            raise ValueError('SHARED_REORG_RESERVATION_OR_ANCHOR_CHANGED')
        blocks=rpc(owners[0],'generatetoaddress','2',public_regtest_mining_address(source))
        wait_for(lambda:all(o.read.call('getbestblockhash')==blocks[-1] for o in owners))
        if rpc(owners[1],'getblockhash',str(height))==original_tip:
            raise ValueError('SHARED_REORG_BRANCH_DID_NOT_CHANGE')
        try:sessions[1].snapshot()
        except ValueError as error:
            if error.args!=('Q06_SPEND_ANCHORED_SAVE_DENIED',):raise
        else:raise ValueError('SHARED_REORG_PARTICIPANT_NATIVE_FLOOR_BYPASSED')
        result=dict(status='PASS_FAIL_CLOSED_SAFETY_ONLY',original_height=height,original_tip=original_tip,
                    rollback_height=height-1,new_height=height+1,new_tip=blocks[-1],
                    both_nodes_same_tip=True,reservations_preserved=True,automatic_rebroadcast=False,
                    only_node_a_mined=True,consensus_modified=False,
                    custody_fail_closed=True,automatic_reorg_wallet_recovery=False,
                    recovery_status='BLOCKED_EXPLICIT_NATIVE_CHECKPOINT_RECONCILIATION_REQUIRED')
        return result
    finally:
        cleanup_errors=close_reorg_owners(sessions,owners)
        if result is not None:result['cleanup_errors']=cleanup_errors
        if cleanup_errors:raise ValueError('SHARED_REORG_ORIGINAL_OWNER_RETAINED')


def close_reorg_owners(sessions,owners):
    """A retained uncertain wallet must never skip original-owner shutdown."""
    from .rpc_scope import identity
    errors=[]
    for session in reversed(sessions):
        try:session.lock()
        except ValueError as error:
            if error.args!=('Q06_SPEND_RUNTIME_PRESERVED',):errors.append('SESSION_LOCK_DENIED')
        except Exception:errors.append('SESSION_LOCK_DENIED')
    for owner in reversed(owners):
        try:
            scope=identity(owner.directory)
            if owner._faulted or scope is not None and scope.faulted:owner.recover_stop()
            else:owner.shutdown()
            owner.release()
            owner.close()
        except Exception:
            errors.append('ORIGINAL_OWNER_STOP_DENIED')
            retain_original_owner(owner)
    return errors


def retain_original_owner(owner):
    """Keep the real handle alive for existing authenticated Core control.

    A failed stop must not turn the next exception into a foreign-PID problem.
    This reuses CoreSupervisor.serve; no new manager or wallet RPC is added.
    """
    import threading
    if owner.process is None or owner.process.poll() is not None:
        return
    def serve():
        try:owner.serve()
        finally:
            if owner.process is None or owner.process.poll() is not None:
                owner.close()
    thread=threading.Thread(target=serve,name='WAM-retained-original-control',daemon=False)
    thread.start()
