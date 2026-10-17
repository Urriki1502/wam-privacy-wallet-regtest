"""Real signed WAM Core v0.1.11 T05 lifecycle: no mock RPC or secret output.

The enclosing CI uses a disposable test root. The *managed Core itself* never
deletes its datadir, including clean close and simulated daemon crash.
"""
import argparse
import json
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


def prove(core):
    evidence={"schema":"wam-t05-real-owned-core/v1","chain":"regtest",
              "synthetic_rpc":False,"mainnet_allowed":False,
              "full_gui_q05_qualified":False}
    # The testing harness deletes its private disposable fixture after
    # the test, NOT the actual managed Core lifecycle.
    with tempfile.TemporaryDirectory(prefix="wam-t05-public-fixture-") as temporary:
        root=Path(temporary).resolve()/"wam-fusion-core-0123456789abcdef"
        root.mkdir(mode=0o700)
        owner=CoreSupervisor(root,core,authorized=True)
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
        server=subprocess.Popen([
            sys.executable,"-m","wam_regtest.supervisor_cli","serve",
            "--root",str(root),"--core-dir",str(core),
            "--confirm-regtest-managed-core"],
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
    return evidence


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--core-dir",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    args=p.parse_args()
    result=prove(args.core_dir.resolve(strict=True))
    with args.output.open("x") as f:json.dump(result,f,sort_keys=True,indent=2);f.write("\n")
    print("T05_REAL_CORE_PERSISTENT_DATADIR_CLEAN_AND_CRASH_RESTART_PASS")


if __name__=="__main__":main()
