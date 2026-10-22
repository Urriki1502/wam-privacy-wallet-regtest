"""Operator entry for T05 long-lived supervisor; REGTEST-only, no wallet keys.

Run the owner separately from the GUI. A GUI close is never implicit Core stop.
"""
import argparse
import json
import re
from pathlib import Path
import sys
from .core_supervisor import CoreSupervisor,ManagedCoreError
from .supervisor_client import control,ManagedClientError
from .supervisor_store import SupervisorStorageError
from .owned_recovery import IndexRecoveryError


def main(argv=None):
    ap=argparse.ArgumentParser(prog="wam-fusion-core-supervisor")
    ap.add_argument("action",choices=("serve","status","start","shutdown","recover-index"))
    ap.add_argument("--root",required=True,type=Path)
    ap.add_argument("--core-dir",type=Path)
    ap.add_argument("--linux-developer-manifest")
    ap.add_argument("--linux-root-witness",type=Path)
    ap.add_argument("--confirm-regtest-managed-core",action="store_true")
    ap.add_argument('--confirm-reindex-existing-regtest',action='store_true')
    ap.add_argument('--expected-height',type=int)
    ap.add_argument('--expected-tip')
    args=ap.parse_args(argv)
    if args.action!="status" and not args.confirm_regtest_managed_core:
        print("MANAGED_EXPLICIT_CONSENT_REQUIRED",file=sys.stderr)
        return 2
    try:
        if args.action=='recover-index':
            if not args.confirm_reindex_existing_regtest or args.core_dir is None:
                raise ManagedCoreError('MANAGED_EXPLICIT_REINDEX_APPROVAL_REQUIRED')
            if sys.platform=='linux':
                from .linux_runtime import configure
                if args.linux_developer_manifest is None or args.linux_root_witness is None:
                    raise ManagedCoreError('MANAGED_LINUX_ROOT_WITNESS_REQUIRED')
                configure(args.core_dir,args.linux_developer_manifest,
                    args.linux_root_witness,authorized=True)
            from .owned_recovery import recover_index
            result=recover_index(args.root,args.core_dir,
                expected_height=args.expected_height,expected_tip=args.expected_tip,
                authorized_reindex=True)
            print(json.dumps(result,sort_keys=True))
            return 0
        if (args.confirm_reindex_existing_regtest or args.expected_height is not None
                or args.expected_tip is not None):
            raise ManagedCoreError('MANAGED_REINDEX_SCOPE_DENIED')
        if args.action=="serve":
            if args.core_dir is None:
                raise ManagedCoreError("MANAGED_CORE_REQUIRED")
            root=args.root
            core=args.core_dir
            if sys.platform=="linux":
                if args.linux_developer_manifest is None or args.linux_root_witness is None:
                    raise ManagedCoreError("MANAGED_LINUX_ROOT_WITNESS_REQUIRED")
                from .linux_runtime import configure
                configure(core,args.linux_developer_manifest,args.linux_root_witness,
                          authorized=True)
            # This is a new operator-approved Fusion namespace, never an
            # existing wallet/datadir. Parent's native custody is checked by
            # the platform's create_private_directory primitive.
            if not root.exists():
                from .custody import create_directory
                create_directory(root)
            owner=CoreSupervisor(root,core,authorized=True)
            try:owner.serve()
            finally:
                owner.close_listener()
                owner.stack.close()
            return 0
        if args.action in ("start","shutdown") and args.core_dir is not None:
            raise ManagedCoreError("MANAGED_REMOTE_CORE_ARGUMENT_DENIED")
        result=control(args.root,args.action,
            authorized=args.confirm_regtest_managed_core)
        print(json.dumps(result,sort_keys=True))
        return 0
    except IndexRecoveryError as error:
        code=str(error)
        print(code if re.fullmatch('RECOVERY_[A-Z_]{4,100}',code) else
            'MANAGED_SUPERVISOR_DENIED',file=sys.stderr)
        return 2
    except (OSError,ValueError,ManagedCoreError,ManagedClientError,
            SupervisorStorageError):
        # Exceptions may contain paths; redact all process-visible errors.
        print("MANAGED_SUPERVISOR_DENIED",file=sys.stderr)
        return 2


def recover_from_bundle(core,args):
    # The frozen application's independently pinned resource pair is the
    # only executable source; operator args cannot select an external Core.
    if any(a=='--core-dir' or a.startswith('--core-dir=') for a in args):
        raise ManagedCoreError('MANAGED_BUNDLE_CORE_OVERRIDE_DENIED')
    return main(['recover-index','--core-dir',str(core),*args])


if __name__=="__main__":
    raise SystemExit(main())
