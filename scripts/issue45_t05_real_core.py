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


def _qt_reopen_probe(root, expected_height, core, wsp_source):
    """Drive actual Fusion widgets with genuine supervisor IPC; no wallet mock."""
    from wam_regtest.desktop import qt_application
    from wam_regtest.managed_gui import ManagedCoreWindow
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QInputDialog
    app=qt_application()
    for reopen in range(2):
        window=ManagedCoreWindow(root,core_dir=core,wsp_source=wsp_source)
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
            # Drive the actual native password dialog, including its nested
            # event loop. Cancel supplies no password or wallet authority.
            modal=[]
            def cancel_dialog():
                dialog=app.activeModalWidget()
                try:
                    window.request_sync()
                    modal.extend((isinstance(dialog,QInputDialog),
                        window._managed_dialog_open,window._worker is None,
                        not window.close()))
                finally:
                    if isinstance(dialog,QInputDialog):
                        dialog.reject()
            assert window.verify_wallet_button.isEnabled()
            QTimer.singleShot(100,cancel_dialog)
            window._verify_wallet()
            assert modal==[True,True,True,True]
            assert window._managed_dialog_open is False
            assert window._worker is None
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
                _qt_reopen_probe(root,height,core,source_root/"wsp-upstream")
                assert server.poll() is None
                assert control(root,"status",timeout=15)["height"]==height
                evidence["real_qt_gui_close_reopen_same_core"]=True
                evidence["real_qt_modal_cancel_no_concurrent_worker"]=True
                _qt_process_probe(root,height)
                assert server.poll() is None
                assert control(root,"status",timeout=15)["height"]==height
                assert _read_cli([str(restarted.cli),f"-datadir={root/'chain'}",
                                  "getblockhash",str(height)])==tip
                evidence["independent_qt_process_reopen_same_chain"]=True
                evidence["actual_qt_process_killed_after_authenticated_ready"]=True
                evidence["actual_qt_crash_reconnect_same_tip"]=True
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
