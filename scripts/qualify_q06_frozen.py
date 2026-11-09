"""Qualify the exact final Windows/Linux frozen Q06 executable, never source.

One new owned REGTEST profile, real Core and native custody. A failure keeps
chain/native witness and the precise bounded diagnostic receipt for review.
"""
from hashlib import sha256
import argparse
import json
import os
from pathlib import Path
import platform
import secrets
import subprocess
import sys
import tempfile


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--executable", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--headless", action="store_true")
    a=p.parse_args()
    exe=a.executable.absolute()
    receipt=a.output.absolute()
    if (platform.system() not in ("Windows","Linux")
            or a.headless and platform.system()!="Linux"
            or not exe.is_file() or exe.is_symlink()
            or receipt.exists() or receipt.is_symlink()):
        raise ValueError("Q06_FINAL_FROZEN_SCOPE_DENIED")
    parent=Path(tempfile.mkdtemp(prefix="wam-q06-final-")).resolve(strict=True)
    root=parent/("wam-fusion-core-"+secrets.token_hex(8))
    args=[str(exe),"--ci-q06-owned-spend","--root",str(root),
          "--receipt",str(receipt),"--confirm-disposable-regtest"]
    if a.headless:args.append("--headless")
    env={k:v for k,v in os.environ.items()
         if k not in ("PYTHONPATH","PYTHONHOME","VIRTUAL_ENV")
         and not k.startswith(("DYLD_","QT_","QML_"))}
    env["QT_QPA_PLATFORM"]="windows" if sys.platform=="win32" else "xcb"
    witness=None
    safe=False
    if sys.platform=="win32":
        system=Path(os.environ["SystemRoot"])
        env["PATH"]=str(system/"System32")+os.pathsep+str(system)
        env["QT_SCALE_FACTOR"]="1.25"
    else:
        env["PATH"]="/usr/bin:/bin:/usr/sbin:/sbin"
    try:
        if sys.platform=="linux":
            tests=Path(__file__).resolve().parents[1]/"tests"
            sys.path.insert(0,str(tests))
            os.environ["WAM_ROOT_WITNESS_NATIVE_TESTS"]="1"
            from test_linux_anchor_witness import NativeRootWitness
            NativeRootWitness.setUpClass()
            witness=NativeRootWitness
            args+=["--linux-developer-manifest",
                   "4052c4a75dee853f5a27c2fb1869aee841a075ed8d6187b90a9d1c06a88cf3c2",
                   "--linux-root-witness",str(witness.root/"anchor.sock")]
        # Capture only fixed public phase names. A frozen windowed Windows
        # executable has no stdout; receipt is always the proof authority.
        outcome=subprocess.run(args,env=env,cwd=parent,
                               stdin=subprocess.DEVNULL,timeout=900)
        if not receipt.is_file():
            raise ValueError("Q06_FINAL_FROZEN_MISSING_RECEIPT")
        data=json.loads(receipt.read_text(encoding="utf8"))
        print("Q06_FINAL_DIAGNOSTIC_STAGE="+str(data.get("failure_stage")),flush=True)
        expected_platform="windows-x64" if sys.platform=="win32" else "linux-x86_64"
        checks={
            "process_exit":outcome.returncode==0,
            "receipt_status":data.get("status")=="Q06_NATIVE_FROZEN_REAL_CORE_PASS",
            "platform":data.get("platform")==expected_platform,
            "frozen":data.get("frozen") is True,
            "real_rpc":data.get("synthetic_rpc") is False,
            "native_custody":data.get("native_custody") is True,
            "regtest_only":data.get("mainnet_allowed") is False,
            "signed_confirmed":data.get("signed_core_transaction_confirmed") is True,
            "seed_rescan":data.get("same_chain_mnemonic_history_recovered") is True,
            "reopen":data.get("same_owner_reopened") is True,
            "txid_readonly":data.get("post_reopen_txid_verified") is True,
            "no_fictional_history":data.get("fresh_chain_full_history_recovered") is False,
            "fresh_profile_identity":data.get("fresh_profile_seed_identity_restored") is True,
            "fresh_same_chain_history":data.get("fresh_same_chain_profile_full_history_recovered") is True,
            "native_gui":data.get("native_gui_checked") is (not a.headless),
            "frozen_binary_sha256":data.get("frozen_executable_sha256")==sha256(exe.read_bytes()).hexdigest(),
        }
        if not a.headless:
            checks.update({
                "gui_backup":data.get("normal_gui_backup_verified") is True,
                "gui_cancel_sign":data.get("gui_cancel_does_not_sign") is True,
                "gui_duplicate_send":data.get("gui_duplicate_send_one_reservation") is True,
                "gui_sign_broadcast":data.get("normal_gui_separate_sign_broadcast") is True,
            })
        expected_source = os.environ.get("WAM_SOURCE_HEAD") or subprocess.check_output(
            ['git','rev-parse','HEAD'],text=True).strip()
        checks["source_sha"] = data.get("source_sha") == expected_source
        # Public, bounded diagnostic keys ONLY. Keep strict failure on ANY
        # mismatched gate (especially native binary hash and process exit).
        # No args, datadirs, raw errors, keys, RPC bodies or seed words.
        for key,passed in checks.items():
            if not passed:
                print("Q06_FINAL_FAILED_GATE="+key.upper(),flush=True)
        if not all(checks.values()):
            raise ValueError("Q06_FINAL_FROZEN_E2E_DENIED")
        safe=True
        print("Q06_FINAL_"+data["platform"].upper().replace("-","_")+
              ("_HEADLESS" if a.headless else "_GUI")+"_PASS",flush=True)
    finally:
        if witness is not None:
            if safe:
                witness.tearDownClass()
            else:
                with receipt.with_name(receipt.stem+"-retained-witness.json").open("x") as f:
                    json.dump({"status":"BLOCKED","reason":"Q06_FAILED_OR_UNCERTAIN",
                               "witness_root":str(witness.root),
                               "action":"Preserve test profile and original witness for manual review"},f)
        # Intentionally retain test profile even on success for checkable
        # provenance; failures NEVER delete or replay potentially signed state.


if __name__=="__main__":
    main()
