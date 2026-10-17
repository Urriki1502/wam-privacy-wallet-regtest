"""Fixed, explicit CI roles in the FINAL bootloader; never a Python -m proxy.

Only public disposable REGTEST probes. Core and WSP come from the platform's
verified bundle entry, never CLI paths. No wallet, signing or anchor operations.
"""
import argparse
import json
from pathlib import Path
import socket
import sys
import time

FLAG = '--ci-managed-process'


def arguments(argv):
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument('role', choices=('supervisor', 'gui', 'scan'))
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--report-root', type=Path)
    parser.add_argument('--expected-height', type=int)
    parser.add_argument('--wait-for-crash', action='store_true')
    parser.add_argument('--expected-before', type=int)
    parser.add_argument('--max-blocks', type=int)
    parser.add_argument('--linux-developer-manifest')
    parser.add_argument('--linux-root-witness', type=Path)
    parser.add_argument('--confirm-disposable-regtest-probe', action='store_true')
    args = parser.parse_args(argv)
    from .supervisor_store import _root
    _root(args.root)
    if not args.confirm_disposable_regtest_probe:
        raise ValueError('FROZEN_PROBE_CONSENT_REQUIRED')
    if args.role == 'supervisor':
        if (args.report_root is not None or args.expected_height is not None
                or args.wait_for_crash or args.expected_before is not None
                or args.max_blocks is not None):
            raise ValueError('FROZEN_PROBE_ROLE_ARGUMENT_DENIED')
    else:
        _root(args.report_root)
        if args.report_root == args.root:
            raise ValueError('FROZEN_PROBE_REPORT_ROOT_DENIED')
        if args.role == 'gui':
            if (type(args.expected_height) is not int
                    or not 0 <= args.expected_height <= 1_000_000
                    or args.expected_before is not None or args.max_blocks is not None):
                raise ValueError('FROZEN_PROBE_ROLE_ARGUMENT_DENIED')
        elif (args.expected_height is not None or args.wait_for_crash
                or type(args.expected_before) is not int
                or not 0 <= args.expected_before <= 1_000_000
                or type(args.max_blocks) is not int or not 1 <= args.max_blocks <= 100):
            raise ValueError('FROZEN_PROBE_ROLE_ARGUMENT_DENIED')
    if sys.platform != 'linux' and (args.linux_developer_manifest is not None
                                  or args.linux_root_witness is not None):
        raise ValueError('FROZEN_PROBE_FOREIGN_POLICY_DENIED')
    return args


def publish_report(root, value):
    # Separate fresh native-private fixture, NOT the supervisor's control root.
    # Reuse its bounded no-follow/create-only native descriptor implementation.
    # This also works with Windows windowed bootloaders lacking stdout/stderr.
    from .supervisor_store import create_once
    raw = (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode('ascii')
    create_once(root, 'supervisor.profile', raw)


def run(argv, core, source):
    if not getattr(sys, 'frozen', False) or not hasattr(sys, '_MEIPASS'):
        raise ValueError('FROZEN_PROBE_BOOTLOADER_REQUIRED')
    args = arguments(argv)
    if sys.platform == 'linux':
        if args.linux_developer_manifest is None or args.linux_root_witness is None:
            raise ValueError('FROZEN_PROBE_LINUX_WITNESS_REQUIRED')
        if args.role != 'scan':
            # Existing scan entry performs its own one-shot binding. Never
            # rebind LinuxPolicy or suppress LINUX_POLICY_ALREADY_BOUND.
            from .linux_runtime import configure
            configure(core, args.linux_developer_manifest, args.linux_root_witness, authorized=True)
    if args.role == 'gui':
        from .managed_gui_probe import probe
        from .desktop import qt_application
        def report(value):
            publish_report(args.report_root, {**value, 'frozen_entrypoint': True,
                'qt_platform': qt_application().platformName()})
        probe(args.root, args.expected_height, wait_for_crash=args.wait_for_crash,
              report=report)
    elif args.role == 'scan':
        from .managed_scan_probe import run as scan
        result = scan(args.root, source, max_blocks=args.max_blocks,
            expected_before=args.expected_before, authorized=True, core_dir=core,
            linux_manifest=args.linux_developer_manifest, linux_witness=args.linux_root_witness)
        publish_report(args.report_root, {**result, 'frozen_entrypoint': True})
    else:
        from .core_supervisor import CoreSupervisor
        owner = CoreSupervisor(args.root, core, authorized=True)
        started = False
        stopped = False
        deadline = time.monotonic() + 300
        try:
            # Existing authenticated request dispatch, replay protection and
            # native ownership checks, without changing the runtime server.
            # Exit only AFTER an owned Core was started and verified stopped.
            while time.monotonic() < deadline:
                try:
                    conn, _ = owner.listener.accept()
                except socket.timeout:
                    continue
                with conn:
                    owner._serve_client(conn)
                started = started or owner.process is not None
                if started and owner.process is None and owner.status()['state'] == 'stopped':
                    stopped = True
                    break
            if not stopped:
                raise ValueError('FROZEN_PROBE_SUPERVISOR_TIMEOUT')
        finally:
            # No kill or unverified PID cleanup. shutdown retains the existing
            # process/config binding gate, including timeout/failure paths.
            try:
                if not stopped:
                    owner.shutdown()
            finally:
                owner.close_listener()
                owner.stack.close()
    return 0
