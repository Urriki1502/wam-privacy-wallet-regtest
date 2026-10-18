"""T-06 operator-approved inspection of an ALREADY-RUNNING REGTEST Core.

No daemon adoption, wallet/chain modification, private-path display, or write.
Only publicly observable chain identity and readiness are emitted.
"""
import argparse
import json
from pathlib import Path
import sys

from .attached_core import attach_existing_core


def main(argv=None):
    ap=argparse.ArgumentParser(prog="wam-fusion-attach-regtest-readonly")
    ap.add_argument("--core-dir",required=True,type=Path)
    ap.add_argument("--datadir",required=True,type=Path)
    ap.add_argument("--pid",required=True,type=int)
    ap.add_argument("--linux-developer-manifest")
    ap.add_argument("--linux-root-witness",type=Path)
    ap.add_argument("--gui",action="store_true",
                    help="Open the isolated read-only Core status window")
    ap.add_argument("--confirm-disposable-regtest-readonly-attach",action="store_true")
    args=ap.parse_args(argv)
    if not args.confirm_disposable_regtest_readonly_attach:
        print("ATTACH_EXPLICIT_CONSENT_REQUIRED",file=sys.stderr)
        return 2
    try:
        if args.gui:
            # Qt is optional. External-Core GUI has no wallet or stop action.
            if sys.platform=="linux":
                if (not args.linux_developer_manifest
                        or args.linux_root_witness is None):
                    raise ValueError("ATTACH_LINUX_ROOT_WITNESS_REQUIRED")
                from .linux_runtime import configure
                configure(args.core_dir,args.linux_developer_manifest,
                          args.linux_root_witness,authorized=True)
            from .attached_core_gui import launch_attached_readonly_gui
            return launch_attached_readonly_gui(
                args.core_dir,args.datadir,args.pid)
        if sys.platform=="linux":
            if (not args.linux_developer_manifest
                    or args.linux_root_witness is None):
                raise ValueError("ATTACH_LINUX_ROOT_WITNESS_REQUIRED")
            from .linux_runtime import configure
            configure(args.core_dir,args.linux_developer_manifest,
                      args.linux_root_witness,authorized=True)
        with attach_existing_core(
                args.core_dir,args.datadir,args.pid,
                authorized_readonly=True) as attached:
            first=attached.attest()
            height=first["blocks"]
            tip=first["bestblockhash"]
            if (attached.call("getblockhash",[height])!=tip
                    or attached.call("getbestblockhash")!=tip
                    or attached.call("getblockcount")!=height):
                raise ValueError("ATTACH_CHAIN_CHANGED")
            # These are API-scope denials. Neither code path can reach Core.
            from .json_rpc import RpcError
            try:attached.call("stop")
            except RpcError as error:
                if error.args!=("RPC_READ_SCOPE_DENIED",):raise
            else:raise ValueError("ATTACH_WRITE_CALL_ACCEPTED")
            try:attached._reader.write_owned_regtest(
                "sendrawtransaction",["00"],authorized=True)
            except RpcError as error:
                if error.args!=("RPC_ATTACHED_WRITE_DENIED",):raise
            else:raise ValueError("ATTACH_BROADCAST_AUTHORITY_ACCEPTED")
            result={
                "status":"T06_EXISTING_CORE_REGTEST_READONLY_PASS",
                "chain":"regtest","height":height,"tip":tip,
                "read_only":True,"process_owned_by_fusion":False,
                "core_lifecycle_mutation":False,"wallet_mutation":False,
                "signer_allowed":False,"broadcast_allowed":False,
                "mainnet_allowed":False,"synthetic_rpc":False,
            }
        print(json.dumps(result,sort_keys=True,separators=(",",":")))
        return 0
    except Exception:
        # No PID, datadir, RPC headers, wallet/secret or Python exception leak.
        print("ATTACH_EXISTING_REGTEST_READONLY_DENIED",file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
