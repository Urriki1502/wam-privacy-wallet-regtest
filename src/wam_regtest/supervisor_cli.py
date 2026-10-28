"""Opt-in Stage A developer entry; ordinary packaged launch is not wired yet."""
import argparse
import json
from pathlib import Path
import sys

from .core_supervisor import CoreSupervisor
from .supervisor_client import control


def main(argv=None):
    parser = argparse.ArgumentParser(prog='wam-managed-core')
    parser.add_argument('action', choices=('serve','status','start','shutdown','recover-stop','recover-dead','release'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--core-dir', type=Path)
    parser.add_argument('--confirm-regtest-managed-core', action='store_true')
    parser.add_argument('--linux-developer-manifest')
    parser.add_argument('--linux-root-witness', type=Path)
    args = parser.parse_args(argv)
    if args.action != 'status' and not args.confirm_regtest_managed_core:
        print('MANAGED_EXPLICIT_CONSENT_REQUIRED', file=sys.stderr)
        return 2
    try:
        if args.action == 'serve':
            if args.core_dir is None:
                raise ValueError
            if sys.platform == 'linux':
                from .linux_runtime import configure
                if args.linux_developer_manifest is None or args.linux_root_witness is None:
                    raise ValueError
                configure(args.core_dir, args.linux_developer_manifest,
                          args.linux_root_witness, authorized=True)
            from .custody import create_directory
            if not args.root.exists() and not args.root.is_symlink():
                create_directory(args.root)
            owner = CoreSupervisor(args.root, args.core_dir, authorized=True)
            # Disconnecting a control client cannot terminate this loop/Core.
            # Stop Core explicitly over authenticated IPC before exiting serve.
            try:
                while True:
                    try:
                        owner.serve()
                        break  # Authenticated release completed with no live child.
                    except KeyboardInterrupt:
                        if owner.process is not None and owner.process.poll() is None:
                            print('MANAGED_EXPLICIT_SHUTDOWN_REQUIRED', file=sys.stderr)
                            continue
                        break
            finally:
                owner.close()
            return 0
        if (args.core_dir is not None or args.linux_developer_manifest is not None
                or args.linux_root_witness is not None):
            raise ValueError
        result = control(args.root, args.action,
                         authorized=args.confirm_regtest_managed_core,
                         timeout=120 if args.action in ('start','shutdown','recover-stop','recover-dead') else 3)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, RuntimeError):
        print('MANAGED_SUPERVISOR_DENIED', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
