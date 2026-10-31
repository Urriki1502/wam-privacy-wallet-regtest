"""CLI entry for real Core only. No synthetic RPC mode."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .core import CoreSmokeError, smoke_real_core
from .q04_runner import Q04RunnerError, run_q04_scenario
from .external_core import ExternalAttachmentError


def main() -> int:
    ap = argparse.ArgumentParser(prog="wam-regtest")
    sub = ap.add_subparsers(dest="command", required=True)
    smoke = sub.add_parser("smoke", help="Run signed real WAM Core v0.1.11 on fresh REGTEST only")
    smoke.add_argument("--core-dir", required=True, type=Path)
    smoke.add_argument("--confirm-disposable-regtest", action="store_true", help="Approve keyless local Core process and disposable test wallet")
    smoke.add_argument("--report", type=Path, help="Write a redacted public receipt")
    smoke.add_argument("--wsp-source-root", type=Path, help="Pinned upstream WSP checkout; require actual live node and scanner")
    smoke.add_argument("--confirm-public-fixture-payment", action="store_true", help="Approve globally-known REGTEST fixture key signing and broadcast, no mainnet")
    smoke.add_argument("--confirm-real-gui-e2e", action="store_true", help="Assert native Qt UI against live Core BIP352/SQLite (CI/headless)")

    smoke.add_argument("--confirm-security-e2e", action="store_true", help="Test encrypted recovery, independent macOS Keychain anchor and actual Core reorg")

    smoke.add_argument("--confirm-wallet-e2e", action="store_true", help="Verify disposable native Qt Send/Sign/Broadcast and encrypted recovery on real Core")

    smoke.add_argument('--confirm-q02-auth-e2e',action='store_true',help='Run disposable genuine-Core Q02 auth/identity negative acceptance; no persistent RPC')
    gui = sub.add_parser("gui", help="Open native Mac read-only public-demo wallet on an ALREADY RUNNING isolated Core REGTEST daemon")
    gui.add_argument("--core-dir", required=True, type=Path)
    gui.add_argument("--datadir", required=True, type=Path)
    gui.add_argument("--wsp-source-root", required=True, type=Path)
    gui.add_argument("--confirm-disposable-regtest", action="store_true")

    demo = sub.add_parser(
        "demo", help="One command: signed v0.1.11 Core -> genuine BIP352 payment -> interactive native Qt REGTEST"
    )
    demo.add_argument("--core-dir", required=True, type=Path)
    demo.add_argument("--wsp-source-root", required=True, type=Path)
    demo.add_argument("--confirm-disposable-regtest", action="store_true")
    demo.add_argument("--confirm-public-fixture-payment", action="store_true")
    wallet = sub.add_parser("wallet", help="Launch disposable test-key native REGTEST wallet (Send/Sign/Broadcast)")
    wallet.add_argument("--core-dir",required=True,type=Path)
    wallet.add_argument("--wsp-source-root",required=True,type=Path)
    wallet.add_argument("--confirm-disposable-regtest",action="store_true")
    wallet.add_argument("--confirm-public-fixture-payment",action="store_true")
    linux=sub.add_parser('linux-wallet',help='Experimental Linux headless wallet; approved developer manifest and root witness required')
    linux.add_argument('--core-dir',type=Path,required=True)
    linux.add_argument('--manifest-sha256',required=True)
    linux.add_argument('--anchor-socket',type=Path,required=True)
    linux.add_argument('--wsp-source-root',type=Path,required=True)
    linux.add_argument('--confirm-experimental-developer-regtest',action='store_true')
    frontend=linux.add_mutually_exclusive_group()
    frontend.add_argument('--gui',action='store_true',help='Use the existing native Fusion Qt interface with the same Linux custody policy')
    frontend.add_argument('--confirm-qt-e2e',action='store_true',help='Explicit actual-Core native Qt acceptance, disposable test keys only')
    frontend.add_argument('--confirm-headless-e2e',action='store_true',help='Explicit disposable real-process acceptance operator, no personal keys')
    linux.add_argument('--recover-backup',type=Path,help='Recover the latest same-host anchored encrypted backup on this fresh disposable chain')
    linux.add_argument('--report',type=Path)
    q04 = sub.add_parser('q04-external-miner', help='Q04 external Core + solo-miner coexistence qualification')
    q04.add_argument('--core-dir', required=True, type=Path)
    q04.add_argument('--confirm-disposable-regtest', action='store_true')
    q04.add_argument('--report', type=Path, default=Path('q04-evidence.json'))
    q04.add_argument('--max-duration', type=int, default=180)
    q04.add_argument('--manifest-sha256')
    q04.add_argument('--anchor-socket', type=Path)
    q04.add_argument('--confirm-experimental-developer-regtest', action='store_true')
    attach=sub.add_parser('attach-core-readonly',help='Explicit REGTEST external-node status monitor; never stops or writes Core')
    attach.add_argument('--core-dir',type=Path,required=True)
    attach.add_argument('--datadir',type=Path,required=True)
    attach.add_argument('--pid',type=int,required=True)
    attach.add_argument('--rpc-port',type=int,required=True)
    attach.add_argument('--confirm-readonly-regtest-attachment',action='store_true')
    attach.add_argument('--manifest-sha256')
    attach.add_argument('--anchor-socket',type=Path)
    attach.add_argument('--confirm-experimental-developer-regtest',action='store_true')
    managed=sub.add_parser('managed-gui',help='Persistent owned REGTEST wallet; no automatic fixture funding')
    managed.add_argument('--core-dir',type=Path,required=True)
    managed.add_argument('--root',type=Path,required=True)
    managed.add_argument('--wsp-source-root',type=Path,required=True)
    managed.add_argument('--confirm-regtest-managed-core',action='store_true')
    managed.add_argument('--create-wallet',action='store_true')
    managed.add_argument('--linux-developer-manifest')
    managed.add_argument('--linux-root-witness',type=Path)
    args = ap.parse_args()
    try:
        if args.command=='managed-gui':
            if not args.confirm_regtest_managed_core:
                raise CoreSmokeError('MANAGED_EXPLICIT_CONSENT_REQUIRED')
            core=args.core_dir.expanduser().absolute();root=args.root.expanduser().absolute()
            source=args.wsp_source_root.expanduser().absolute()
            if sys.platform=='linux':
                if not args.linux_developer_manifest or args.linux_root_witness is None:
                    raise CoreSmokeError('LINUX_EXPLICIT_CORE_AND_WITNESS_POLICY_REQUIRED')
                from .linux_runtime import configure
                configure(core,args.linux_developer_manifest,args.linux_root_witness.expanduser().absolute(),authorized=True)
            from .managed_gui import launch_managed
            return launch_managed(root,core,source,authorized=True,create=args.create_wallet)
        if args.command=='attach-core-readonly':
            if args.confirm_readonly_regtest_attachment is not True:
                raise Q04RunnerError('Q04_ATTACH_EXPLICIT_CONSENT_REQUIRED')
            if sys.platform=='linux':
                if not args.manifest_sha256 or args.anchor_socket is None:
                    raise Q04RunnerError('Q04_LINUX_EXPLICIT_TRUST_REQUIRED')
                from .linux_runtime import configure
                configure(args.core_dir.expanduser().absolute(),args.manifest_sha256,
                    args.anchor_socket.expanduser().absolute(),authorized=args.confirm_experimental_developer_regtest)
            from .external_core import ExternalCoreAttachment
            from .external_core_gui import launch
            with ExternalCoreAttachment(pid=args.pid,rpc_port=args.rpc_port,
                    datadir=args.datadir.expanduser().absolute(),core_dir=args.core_dir.expanduser().absolute(),
                    operator_consent=True) as attachment:
                return launch(attachment)
        if args.command=='linux-wallet':
            from .linux_headless import run
            return run(args)
        if args.command == "smoke":
            outcome = smoke_real_core(args.core_dir.expanduser().absolute(), explicit_consent=args.confirm_disposable_regtest,
                                      wsp_source=(args.wsp_source_root.expanduser().absolute() if args.wsp_source_root else None),
                                      wsp_payment_e2e=args.confirm_public_fixture_payment,
                                      gui_e2e=args.confirm_real_gui_e2e,
                                      security_e2e=args.confirm_security_e2e,
                                      wallet_e2e=args.confirm_wallet_e2e,q02_e2e=args.confirm_q02_auth_e2e)
            if args.report:
                if args.report.exists() or not args.report.parent.is_dir():
                    raise CoreSmokeError("CORE_REPORT_PATH_DENIED")
                args.report.write_text(json.dumps(outcome, sort_keys=True, indent=2) + "\n")
            print(json.dumps(outcome, sort_keys=True))
            return 0
        if args.command in ("demo", "wallet"):
            if (args.confirm_disposable_regtest is not True
                    or args.confirm_public_fixture_payment is not True):
                raise CoreSmokeError("CORE_REAL_DEMO_CONSENT_DENIED")
            result = smoke_real_core(
                args.core_dir.expanduser().absolute(),
                explicit_consent=True,
                wsp_source=args.wsp_source_root.expanduser().absolute(),
                wsp_payment_e2e=True,
                interactive_demo=True,
                operational_demo=args.command=="wallet",
            )
            if not result.get("interactive_demo_closed_cleanly"):
                raise CoreSmokeError("CORE_REAL_DEMO_NOT_CLOSED")
            print(json.dumps(result, sort_keys=True))
            return 0
        if args.command == "gui":
            if args.confirm_disposable_regtest is not True:
                raise CoreSmokeError("CORE_GUI_DISPOSABLE_REGTEST_CONSENT_DENIED")
            # Separate, running signed WAM Core required; never autostart or
            # attempt to upgrade an unknown process into a wallet.
            from .desktop import launch_readonly_wallet
            return launch_readonly_wallet(
                args.core_dir.expanduser().absolute(),
                args.datadir.expanduser().absolute(),
                args.wsp_source_root.expanduser().absolute(),
            )
        if args.command == 'q04-external-miner':
            if args.confirm_disposable_regtest is not True:
                raise Q04RunnerError('Q04_RUNNER_CONSENT_REQUIRED')
            if sys.platform == 'linux':
                if not args.manifest_sha256 or args.anchor_socket is None:
                    raise Q04RunnerError('Q04_LINUX_EXPLICIT_TRUST_REQUIRED')
                from .linux_runtime import configure
                configure(args.core_dir.expanduser().absolute(), args.manifest_sha256,
                          args.anchor_socket.expanduser().absolute(),
                          authorized=args.confirm_experimental_developer_regtest)
            evidence = run_q04_scenario(
                args.core_dir.expanduser().absolute(),
                report_path=args.report.expanduser().absolute(),
                max_duration=args.max_duration)
            print(json.dumps(evidence, sort_keys=True))
            return 0
        raise CoreSmokeError("CORE_COMMAND_DENIED")
    except (CoreSmokeError, Q04RunnerError, ExternalAttachmentError) as error:
        print(str(error), file=sys.stderr)
        return 2
    finally:
        desktop = sys.modules.get("wam_regtest.desktop")
        if desktop is not None:
            desktop.shutdown_qt()


if __name__ == "__main__":
    raise SystemExit(main())
