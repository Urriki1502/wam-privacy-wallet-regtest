"""Independent-process Q05 REAL WSP scan continuation acceptance.

This is an explicit public REGTEST scanner fixture, NOT a wallet/GUI key
restore. Scanner processes contain no spender keys, never sign or broadcast,
and only use the separately owned Core's authenticated read-only IPC.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

from .supervisor_store import _root


class IndependentScanProbeError(ValueError):
    pass


def run(root, wsp_source, *, max_blocks, expected_before=None, authorized=False,
        core_dir=None, linux_manifest=None, linux_witness=None):
    if authorized is not True or type(root) is not type(Path()) or not root.is_absolute():
        raise IndependentScanProbeError("Q05_PUBLIC_SCAN_CONSENT_REQUIRED")
    _root(root)
    if (type(wsp_source) is not type(Path()) or not wsp_source.is_absolute()
            or type(max_blocks) is not int or not 1<=max_blocks<=100
            or expected_before is not None and
                (type(expected_before) is not int or not 0<=expected_before<=1_000_000)):
        raise IndependentScanProbeError("Q05_PUBLIC_SCAN_SCOPE_DENIED")
    if sys.platform=="linux":
        if (type(core_dir) is not type(Path()) or not core_dir.is_absolute()
                or type(linux_manifest) is not str
                or type(linux_witness) is not type(Path()) or not linux_witness.is_absolute()):
            raise IndependentScanProbeError("Q05_LINUX_ROOT_WITNESS_REQUIRED")
        from .linux_runtime import configure
        configure(core_dir,linux_manifest,linux_witness,authorized=True)
    from .wsp_live import _pinned_source
    _pinned_source(wsp_source)
    from wam_sp.keystore import ScanAccount
    from wam_sp.core import pub
    from wam_sp.scanner import Scanner
    from .managed_scan_client import ManagedScanRpc
    from .wsp_live import REGTEST_GENESIS
    from .custody import storage
    storage().validate_directory(root)
    rpc=ManagedScanRpc(root,authorized_readonly=True)
    scanner=None
    try:
        account=ScanAccount(0,1,pub(2),birthday=1)
        # Persistent PUBLIC scanner fixture, no wallet vault/seed or signing.
        path=root/"q05-public-scan-fixture.sqlite"
        scanner=Scanner(path,(account,))
        before,prior_tip=scanner.store.tip()
        if (expected_before is not None and before!=expected_before
                or before==0 and prior_tip!=REGTEST_GENESIS):
            raise IndependentScanProbeError("Q05_PUBLIC_SCAN_PREVIOUS_TIP_DENIED")
        info=rpc.attest()
        if (info["chain"]!="regtest" or type(info["blocks"]) is not int
                or info["blocks"]<before):
            raise IndependentScanProbeError("Q05_PUBLIC_SCAN_CORE_DENIED")
        if before and rpc.call("getblockhash",[before])!=prior_tip:
            raise IndependentScanProbeError("Q05_PUBLIC_SCAN_CHAIN_CHANGED")
        stats=scanner.sync(rpc,max_blocks=max_blocks)
        height,tip=scanner.store.tip()
        if (height!=min(info["blocks"],before+max_blocks)
                or stats.blocks!=height-before
                or tip!=rpc.call("getblockhash",[height])
                or rpc.call("getblockcount")!=info["blocks"]
                or info["blocks"]!=rpc.attest()["blocks"]):
            raise IndependentScanProbeError("Q05_PUBLIC_SCAN_UNVERIFIED")
        return {"status":"Q05_INDEPENDENT_REAL_WSP_SCAN_PASS",
                "before":before,"height":height,"processed":stats.blocks,
                "tip":tip,"core_height":info["blocks"],
                "scanner_ready":scanner.ready,
                "read_only":True,"wallet_adopted":False,
                "signer_allowed":False,"broadcast_allowed":False,
                "mainnet_allowed":False,"synthetic_rpc":False}
    finally:
        if scanner is not None:scanner.close()
        rpc.close()


def main(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",type=Path,required=True)
    ap.add_argument("--wsp-source",type=Path,required=True)
    ap.add_argument("--max-blocks",type=int,required=True)
    ap.add_argument("--expected-before",type=int)
    ap.add_argument("--confirm-public-regtest-scan",action="store_true")
    ap.add_argument("--core-dir",type=Path)
    ap.add_argument("--linux-developer-manifest")
    ap.add_argument("--linux-root-witness",type=Path)
    args=ap.parse_args(argv)
    if not args.confirm_public_regtest_scan:
        return 2
    try:
        evidence=run(args.root,args.wsp_source,max_blocks=args.max_blocks,
            expected_before=args.expected_before,authorized=True,
            core_dir=args.core_dir,linux_manifest=args.linux_developer_manifest,
            linux_witness=args.linux_root_witness)
        print(json.dumps(evidence,sort_keys=True,separators=(",",":")),flush=True)
        return 0
    except Exception:
        print("Q05_PUBLIC_SCAN_PROBE_DENIED",file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
