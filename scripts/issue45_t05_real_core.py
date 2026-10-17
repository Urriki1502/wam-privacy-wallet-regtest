"""Real signed WAM Core v0.1.11 T05 lifecycle: no mock RPC or secret output.

The enclosing CI uses a disposable test root. The *managed Core itself* never
deletes its datadir, including clean close and simulated daemon crash.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
import tempfile
from wam_regtest.core_supervisor import CoreSupervisor,ManagedCoreError
from wam_regtest.core import _read_cli


def _closed(owner):
    owner.close_listener()
    owner.stack.close()


def _qt_reopen_probe(root, expected_height):
    """Drive actual Fusion widgets with genuine supervisor IPC; no wallet mock."""
    from wam_regtest.desktop import qt_application
    from wam_regtest.managed_gui import ManagedCoreWindow
    app=qt_application()
    for reopen in range(2):
        window=ManagedCoreWindow(root)
        window.show()
        try:
            window.request_sync()
            deadline=time.monotonic()+25
            while time.monotonic()<deadline:
                app.processEvents()
                if window._worker is None:
                    if window._managed_authenticated and window._managed_state=="ready":
                        break
                    raise AssertionError("T05_FUSION_GUI_CORE_UNVERIFIED")
                time.sleep(.01)
            else:raise AssertionError("T05_FUSION_GUI_SYNC_TIMEOUT")
            assert "READY" in window.verification_badge.text()
            assert " · height "+str(expected_height)+" · " in window.status.text()
            assert window._snapshot is None and window.session is None
            assert window.dashboard.go_send.isEnabled() is False
        finally:
            if not window.close():
                raise AssertionError("T05_FUSION_GUI_CLOSE_DENIED")
            # Deterministically release QWidget before Python's Qt teardown.
            from shiboken6 import delete
            delete(window)
            app.processEvents()


def _qt_process_probe(root, expected_height):
    """Three real GUI interpreters: clean close, abrupt crash, verified reopen."""
    import queue
    import threading
    command = [sys.executable, "-m", "wam_regtest.managed_gui_probe",
        "--root", str(root), "--expected-height", str(expected_height),
        "--confirm-disposable-regtest-probe"]
    expected = {"height": expected_height, "wallet_adopted": False,
                "authenticated_gui_ready": True}
    def clean():
        result = subprocess.run(command, stdin=subprocess.DEVNULL,
            capture_output=True, timeout=40)
        if result.returncode != 0:
            raise AssertionError("T05_GUI_CLEAN_PROCESS_EXIT_DENIED")
        assert json.loads(result.stdout) == {**expected, "native_shutdown_completed": True}
    clean()
    child = subprocess.Popen(command + ["--wait-for-crash"],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    line = queue.Queue(maxsize=1)
    # Portable bounded pipe readiness; Windows does not support select on pipes.
    reader = threading.Thread(target=lambda: line.put(child.stdout.readline(1025)), daemon=True)
    reader.start()
    try:
        ready = line.get(timeout=35)
        assert len(ready) <= 1024 and json.loads(ready) == expected
        assert child.poll() is None
        # Kill only the actual GUI Popen created above, after real Qt and IPC
        # verification. No synthetic os._exit stand-in for this acceptance case.
        child.kill()
        assert child.wait(timeout=10) != 0
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=10)
        reader.join(timeout=3)
        child.stdout.close()
        assert not reader.is_alive()
    clean()



def _qt_original_wallet_live_read_probe(root, core, expected_height, funding_address):
    """Actual macOS WSP encrypted wallet -> native GUI -> managed Core IPC.

    Builds a fresh disposable WSP account on the already independently owned
    REGTEST chain, stores its *real* Keyring and Scanner in a native-anchored
    encrypted checkpoint, and opens the real Fusion GUI twice. No mocks of
    RPC, scanner, Core, wallet state or Qt. Only the user password dialog is
    provided by the explicit test operator harness.
    """
    if sys.platform!="darwin":
        raise AssertionError("Q05_MACOS_NATIVE_ONLY")
    import secrets
    from unittest.mock import patch
    from shiboken6 import delete
    from wam_regtest import custody
    from wam_regtest.core import verified_core_paths
    from wam_regtest.managed_wallet_reopen import make,publish
    from wam_regtest.vault import CheckpointVault
    from wam_regtest.managed_scan_client import ManagedScanRpc
    from wam_regtest.wsp_live import _pinned_source
    from wam_regtest.desktop import qt_application
    from wam_regtest.managed_gui import ManagedCoreWindow
    from wam_regtest.supervisor_client import control
    from wam_sp.keystore import Keyring
    from wam_sp.scanner import Scanner

    wsp=Path(__file__).resolve().parents[1]/"wsp-upstream"
    _pinned_source(wsp)
    _,native_cli,receipt=verified_core_paths(core)
    password=b"q05-disposable-native-verified-regtest-only"
    directory=root/"chain"
    vault_dir=directory/"wallet-vault"
    custody.create_directory(vault_dir)
    ring=scanner=rpc=None
    runtime=directory/"wallet-runtime.sqlite"
    wallet_id=secrets.token_hex(16)
    anchor=custody.anchor(wallet_id)
    try:
        ring=Keyring()
        ring.backup(password)
        original_receive=ring.accounts()[-1].payment_code()
        payment_account=ring.accounts()[-1]
        scanner=Scanner(runtime,ring.accounts())
        rpc=ManagedScanRpc(root,authorized_readonly=True)
        scanner.sync(rpc)
        scanner.assert_current()
        assert scanner.store.tip()==(
            expected_height,rpc.call("getbestblockhash"))
        assert scanner.coins()==[]
        vault=CheckpointVault(vault_dir,anchor,wsp)
        vault.save(ring,scanner,password)
        publish(vault_dir,make(wallet_id,receipt),password)
    finally:
        if scanner is not None:scanner.close()
        if ring is not None:ring.close()
        if rpc is not None:rpc.close()
        if scanner is not None:runtime.unlink(missing_ok=True)

    # The public REGTEST miner coinbase was generated to scalar=31 at height
    # 1. This submits and CONFIRMS a genuine BIP352 payment to the ORIGINAL
    # encrypted WSP account after its initial checkpoint was sealed.
    from wam_regtest.wallet_session import WalletCoreCli
    from wam_regtest.wsp_live import _public_fixture_payment
    payment_rpc=WalletCoreCli(native_cli,directory)
    payment_rpc.attest()
    txid,expected_atoms,funded_height=_public_fixture_payment(
        payment_rpc,payment_account,funding_address,
        funding_height=1,expected_before_height=expected_height)
    assert funded_height==expected_height+1 and expected_atoms>0
    payment_account=None

    # A THIRD interpreter holds a REAL native GUI, reads the encrypted
    # original wallet through authenticated supervisor RPC, then terminates
    # abruptly. It sends no transaction and does not control/stop Core.
    # Password travels only through a bounded private test stdin pipe, never
    # in process arguments, logs, CLI flags or the supervisor protocol.
    crashed_gui=r'''
import json,os,sys,time
from pathlib import Path
from unittest.mock import patch
from wam_regtest.desktop import qt_application
from wam_regtest.managed_gui import ManagedCoreWindow
from wam_regtest.supervisor_client import control
root,core,wsp=(Path(x) for x in sys.argv[1:4])
password=sys.stdin.buffer.readline(1025).strip()
if not 12<=len(password)<=1024:raise SystemExit(2)
app=qt_application()
window=ManagedCoreWindow(root,core_dir=core,wsp_source=wsp)
window.show()
window._apply_managed_status(control(root,"status",timeout=10))
if not window.view_wallet_button.isEnabled():raise SystemExit(2)
with patch("wam_regtest.managed_gui.QInputDialog.getText",
           return_value=(password.decode("ascii"),True)):
    window.view_wallet_button.click()
deadline=time.monotonic()+90
while window._worker is not None and time.monotonic()<deadline:
    app.processEvents()
    time.sleep(.01)
app.processEvents()
snap=window._snapshot
if (snap is None or snap.signer_allowed or snap.broadcast_allowed
        or snap.demo_account_only or snap.synthetic_rpc
        or window.session is not None):raise SystemExit(2)
print(json.dumps({"status":"Q05_REAL_ORIGINAL_WALLET_GUI_READY_BEFORE_KILL",
                  "height":snap.height,"confirmed_atoms":snap.confirmed_atoms,
                  "history_txid":snap.history[0].txid if snap.history else None,
                  "mainnet_allowed":False},sort_keys=True),flush=True)
os._exit(41)
'''
    killed=subprocess.run(
        [sys.executable,"-X","faulthandler","-c",crashed_gui,
         str(root),str(core),str(wsp)],
        input=password+b"\n",stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
        timeout=110,check=False)
    assert killed.returncode==41
    killed_receipt=json.loads(killed.stdout)
    assert killed_receipt=={
        "status":"Q05_REAL_ORIGINAL_WALLET_GUI_READY_BEFORE_KILL",
        "height":funded_height,
        "confirmed_atoms":expected_atoms,
        "history_txid":txid,"mainnet_allowed":False,
    }
    assert not runtime.exists()
    assert control(root,"status",timeout=10)["height"]==funded_height
    assert _read_cli([str(native_cli),f"-datadir={directory}",
                     "getblockhash",str(funded_height)])==payment_rpc.call(
                         "getblockhash",[funded_height])

    app=qt_application()
    original_tip=control(root,"status",timeout=10)["height"]
    assert original_tip==funded_height
    for i in range(2):
        window=ManagedCoreWindow(root,core_dir=core,wsp_source=wsp)
        window.show()
        try:
            window._apply_managed_status(control(root,"status",timeout=10))
            assert window.view_wallet_button.isEnabled()
            with patch("wam_regtest.managed_gui.QInputDialog.getText",
                       return_value=(password.decode("ascii"),True)):
                window.view_wallet_button.click()
                assert window._worker is not None
                deadline=time.monotonic()+90
                while window._worker is not None and time.monotonic()<deadline:
                    app.processEvents()
                    time.sleep(.01)
            if window._worker is not None:
                raise AssertionError("Q05_REAL_NATIVE_WALLET_GUI_WORKER_TIMEOUT")
            app.processEvents()
            snapshot=window._snapshot
            assert snapshot is not None
            assert snapshot.demo_account_only is False
            assert snapshot.synthetic_rpc is False
            assert snapshot.signer_allowed is False
            assert snapshot.broadcast_allowed is False
            assert snapshot.mainnet_allowed is False
            assert snapshot.height==funded_height
            assert snapshot.receive_code==original_receive
            assert snapshot.confirmed_atoms==expected_atoms
            assert snapshot.confirmed_utxos==1
            assert len(snapshot.history)==1
            assert snapshot.history[0].txid==txid
            assert snapshot.history[0].credit_atoms==expected_atoms
            assert snapshot.history[0].confirmations==1
            assert window.history_page.table.rowCount()==1
            assert window.receive_page.code==original_receive
            assert window.session is None
            assert window.dashboard.go_send.isEnabled() is False
            assert control(root,"status",timeout=10)["height"]==funded_height
        finally:
            if not window.close():
                raise AssertionError("Q05_REAL_NATIVE_WALLET_GUI_CLOSE_DENIED")
            delete(window)
            app.processEvents()
    assert not runtime.exists()
    assert control(root,"status",timeout=10)["height"]==funded_height
    return {
        "real_encrypted_native_checkpoint":True,
        "genuine_wsp_original_account":True,
        "actual_signed_core_regtest_ipc":True,
        "same_receive_code_two_qt_windows":True,
        "genuine_bip352_funded_receive_history_verified":True,
        "real_native_gui_killed_after_wallet_verification":True,
        "real_native_gui_reopened_after_kill_same_wallet":True,
        "confirmed_real_payment_txid":txid,
        "confirmed_atoms":expected_atoms,
        "actual_chain_height":funded_height,
        "signer_allowed":False,
        "broadcast_allowed":False,
        "mainnet_allowed":False,
        "wallet_gui_process_crash_recovery_qualified":False,
    }

def prove(core, *, qt=False, linux_manifest=None, linux_witness=None):
    # Native acceptance source identity only, never a runtime wallet authority.
    from wam_regtest.build_provenance import capture, verify, public_receipt
    source_root = Path(__file__).resolve().parents[1]
    source = capture(source_root)
    if sys.platform=="linux":
        if type(linux_manifest) is not str or linux_witness is None:
            raise ManagedCoreError("T05_LINUX_NATIVE_WITNESS_REQUIRED")
        # Same verified developer-Core policy as existing Linux wallet; no
        # foreign signer, backup or weaker root anchor.
        from wam_regtest.linux_runtime import configure
        configure(core,linux_manifest,linux_witness,authorized=True)
    evidence={"schema":"wam-t05-real-owned-core/v1","chain":"regtest",
              "synthetic_rpc":False,"mainnet_allowed":False,
              "full_gui_q05_qualified":False,
              "test_source_provenance":public_receipt(source,
                  source_head=os.environ.get("WAM_SOURCE_HEAD"))}
    # The testing harness deletes its private disposable fixture after
    # the test, NOT the actual managed Core lifecycle.
    with tempfile.TemporaryDirectory(prefix="wam-t05-public-fixture-") as temporary:
        root=Path(temporary).resolve()/"wam-fusion-core-0123456789abcdef"
        # Native Windows requires explicit owner-only NTFS DACL, not mkdir's
        # inherited permissions or chmod emulation. POSIX retains mode 0700.
        if sys.platform=="win32":
            from wam_regtest.custody import create_directory
            create_directory(root)
        else:
            root.mkdir(mode=0o700)
        owner=CoreSupervisor(root,core,authorized=True)
        evidence["wamd_sha256"] = owner.receipt["wamd_sha256"]
        evidence["wam_cli_sha256"] = owner.receipt["wam_cli_sha256"]
        try:
            # Distinct supervisor must not acquire an existing owner lock.
            try:CoreSupervisor(root,core,authorized=True)
            except Exception:evidence["simultaneous_owner_denied"]=True
            else:raise AssertionError("T05_CONCURRENT_SUPERVISOR_ACCEPTED")
            owner.start()
            assert owner.status()["core_process_owned"] is True
            prefix=[str(owner.cli),f"-datadir={owner.directory}"]
            _read_cli(prefix+["createwallet","test"])
            address=_read_cli(prefix+["-rpcwallet=test","getnewaddress"])
            if sys.platform=="darwin" and qt:
                # Dedicated Q05 funded-wallet proof uses a globally known
                # test-only scalar. Never run the signer fixture on mainnet.
                from wam_regtest.wsp_live import public_regtest_mining_address
                address=public_regtest_mining_address(source_root/"wsp-upstream")
            blocks=_read_cli(prefix+["generatetoaddress","101",address],timeout=90)
            assert len(blocks)==101
            height=owner.read.call("getblockcount",[])
            assert height==101
            tip=owner.read.call("getblockhash",[height])
            evidence["original_height"]=height
            owner.shutdown()
            assert owner.directory.is_dir()
            assert (owner.directory/"regtest").is_dir()
            assert owner.process is None
        finally:_closed(owner)
        # New application session; existing protected chain is reused.
        restarted=CoreSupervisor(root,core,authorized=True)
        try:
            assert restarted.directory==root/"chain"
            restarted.start()
            assert restarted.read.call("getblockcount",[])==height
            assert restarted.read.call("getblockhash",[height])==tip
            evidence["clean_restart_same_tip"]=True
            # A real crash of the owned Core does not erase the chain.
            restarted.process.kill()
            restarted.process.wait(timeout=15)
            assert restarted.status()["state"]=="recovery-needed"
            assert restarted.directory.is_dir()
            restarted.start()
            assert restarted.read.call("getblockcount",[])==height
            assert restarted.read.call("getblockhash",[height])==tip
            evidence["daemon_crash_recovery_same_tip"]=True
            restarted.shutdown()
        finally:_closed(restarted)
        # Independently launched owner stays alive across disposable GUI/client exits.
        # No Core adoption: the new supervisor owns a newly started Popen itself.
        from wam_regtest.supervisor_client import control
        command=[sys.executable,"-m","wam_regtest.supervisor_cli","serve",
            "--root",str(root),"--core-dir",str(core),
            "--confirm-regtest-managed-core"]
        if sys.platform=="linux":
            command.extend(["--linux-developer-manifest",linux_manifest,
                            "--linux-root-witness",str(linux_witness)])
        server=subprocess.Popen(command,
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        stopped=False
        try:
            deadline=time.monotonic()+15
            while time.monotonic()<deadline:
                if server.poll() is not None:
                    raise AssertionError("T05_SUPERVISOR_PROCESS_DIED")
                try:
                    state=control(root,"status",timeout=3)
                    if state["state"]=="stopped":break
                except Exception:time.sleep(.1)
            else:raise AssertionError("T05_SUPERVISOR_IPC_NOT_READY")
            state=control(root,"start",authorized=True,timeout=15)
            assert state["core_process_owned"] is True
            assert state["height"]==height
            if qt:
                # Two independent REAL WSP-1 scanner interpreters. They share
                # only the OS-protected SQLite fixture, not an RPC object,
                # memory account, Core PID handle or process lifetime.
                # This still proves a public scanner fixture, NOT owner-wallet
                # restore, signer activation or complete Q05.
                wsp_source=source_root/"wsp-upstream"
                command=[sys.executable,"-m","wam_regtest.managed_scan_probe",
                    "--root",str(root),"--wsp-source",str(wsp_source),
                    "--confirm-public-regtest-scan"]
                if sys.platform=="linux":
                    command.extend(["--core-dir",str(core),
                        "--linux-developer-manifest",linux_manifest,
                        "--linux-root-witness",str(linux_witness)])
                def scan_child(before,count):
                    args=command+["--expected-before",str(before),
                                  "--max-blocks",str(count)]
                    reply=subprocess.run(args,stdin=subprocess.DEVNULL,
                        capture_output=True,timeout=100,check=False)
                    if reply.returncode!=0:
                        raise AssertionError("Q05_REAL_WSP_INDEPENDENT_PROCESS_DENIED")
                    evidence=json.loads(reply.stdout)
                    assert evidence["status"]=="Q05_INDEPENDENT_REAL_WSP_SCAN_PASS"
                    assert evidence["before"]==before
                    assert evidence["processed"]==count
                    assert evidence["height"]==before+count
                    assert evidence["core_height"]==height
                    assert evidence["read_only"] is True
                    assert evidence["wallet_adopted"] is False
                    assert evidence["signer_allowed"] is False
                    assert evidence["broadcast_allowed"] is False
                    assert evidence["mainnet_allowed"] is False
                    assert evidence["synthetic_rpc"] is False
                    return evidence
                scan1=scan_child(0,3)
                assert scan1["scanner_ready"] is False
                assert scan1["tip"]==_read_cli([str(restarted.cli),
                    f"-datadir={root/'chain'}","getblockhash","3"])
                assert server.poll() is None
                scan2=scan_child(3,5)
                assert scan2["scanner_ready"] is False
                assert scan2["tip"]==_read_cli([str(restarted.cli),
                    f"-datadir={root/'chain'}","getblockhash","8"])
                assert scan1["tip"]!=scan2["tip"]
                assert server.poll() is None
                assert control(root,"status",timeout=15)["height"]==height
                evidence["authenticated_wsp_scan_first_three_real_blocks"]=True
                evidence["authenticated_wsp_sqlite_resume_same_tip"]=True
                evidence["authenticated_wsp_reopened_client_same_supervisor"]=True
                evidence["two_independent_wsp_scanner_processes_same_sqlite"]=True
                evidence["scanner_read_only_partial_sync_only"]=True
            # This second, independent interpreter represents a GUI re-open.
            client=subprocess.run([
                sys.executable,"-m","wam_regtest.supervisor_cli",
                "status","--root",str(root)],
                stdin=subprocess.DEVNULL,capture_output=True,timeout=20)
            assert client.returncode==0
            observed=json.loads(client.stdout)
            assert observed["core_process_owned"] is True
            assert observed["height"]==height
            assert _read_cli([str(restarted.cli),f"-datadir={root/'chain'}",
                              "getblockhash",str(height)])==tip
            evidence["independent_gui_client_reopen_same_chain"]=True
            # A GUI crash must not terminate the independent supervisor.
            crashed=subprocess.run([
                sys.executable,"-c",
                "import os,sys;from wam_regtest.supervisor_client import control;"
                "control(__import__('pathlib').Path(sys.argv[1]));os._exit(41)",str(root)],
                stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,timeout=20)
            assert crashed.returncode==41
            assert server.poll() is None
            assert control(root,"status",timeout=15)["height"]==height
            evidence["disconnected_gui_client_core_survived"]=True
            if qt:
                _qt_reopen_probe(root,height)
                assert server.poll() is None
                assert control(root,"status",timeout=15)["height"]==height
                evidence["real_qt_gui_close_reopen_same_core"]=True
                _qt_process_probe(root,height)
                assert server.poll() is None
                assert control(root,"status",timeout=15)["height"]==height
                assert _read_cli([str(restarted.cli),f"-datadir={root/'chain'}",
                                  "getblockhash",str(height)])==tip
                evidence["independent_qt_process_reopen_same_chain"]=True
                evidence["actual_qt_process_killed_after_authenticated_ready"]=True
                evidence["actual_qt_crash_reconnect_same_tip"]=True
                if sys.platform=="darwin":
                    actual_wallet=_qt_original_wallet_live_read_probe(
                        root,core,height,address)
                    evidence["real_original_wallet_readonly_gui_macos"]=actual_wallet
            state=control(root,"shutdown",authorized=True,timeout=15)
            stopped=(state["state"]=="stopped" and state["core_process_owned"] is False)
            assert stopped
        finally:
            # Never terminate an unverified live Core owner to hide a test fail.
            if not stopped and server.poll() is None:
                try:
                    state=control(root,"shutdown",authorized=True,timeout=15)
                    stopped=(state["state"]=="stopped" and state["core_process_owned"] is False)
                except Exception:pass
            if stopped and server.poll() is None:
                server.terminate()
                server.wait(timeout=15)
            if not stopped:
                raise AssertionError("T05_SUPERVISOR_SHUTDOWN_UNVERIFIED")
        assert (root/"supervisor.profile").is_file()
        assert (root/"supervisor.token").is_file()
        evidence["persistent_datadir_reused"]=True
        evidence["unrelated_core_stopped"]=False
        evidence["verified_core_version"]="v0.1.11"
        evidence["real_process_lifecycle_pass"]=True
    verify(source_root, source)
    return evidence


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--core-dir",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    p.add_argument("--qt-e2e",action="store_true")
    p.add_argument("--linux-developer-manifest")
    p.add_argument("--linux-root-witness",type=Path)
    args=p.parse_args()
    result=prove(args.core_dir.resolve(strict=True),qt=args.qt_e2e,
                 linux_manifest=args.linux_developer_manifest,
                 linux_witness=args.linux_root_witness)
    with args.output.open("x") as f:json.dump(result,f,sort_keys=True,indent=2);f.write("\n")
    print("T05_REAL_CORE_PERSISTENT_DATADIR_CLEAN_AND_CRASH_RESTART_PASS")


if __name__=="__main__":main()
