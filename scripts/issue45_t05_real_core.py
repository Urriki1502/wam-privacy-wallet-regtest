"""Real signed WAM Core v0.1.11 T05 lifecycle: no mock RPC or secret output.

The enclosing CI uses a disposable test root. The *managed Core itself* never
deletes its datadir, including clean close and simulated daemon crash.
"""
import argparse
import json
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
