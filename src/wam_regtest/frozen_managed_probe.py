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
    parser.add_argument('--confirm-owned-core-crash', action='store_true')
    args = parser.parse_args(argv)
    from .supervisor_store import _root
    _root(args.root)
    if not args.confirm_disposable_regtest_probe:
        raise ValueError('FROZEN_PROBE_CONSENT_REQUIRED')
    _root(args.report_root)
    if args.report_root == args.root:
        raise ValueError('FROZEN_PROBE_REPORT_ROOT_DENIED')
    if args.role == 'supervisor':
        if not args.confirm_owned_core_crash:
            raise ValueError('FROZEN_PROBE_CORE_CRASH_CONSENT_REQUIRED')
        if (args.expected_height is not None
                or args.wait_for_crash or args.expected_before is not None
                or args.max_blocks is not None):
            raise ValueError('FROZEN_PROBE_ROLE_ARGUMENT_DENIED')
    else:
        if args.confirm_owned_core_crash:
            raise ValueError('FROZEN_PROBE_ROLE_ARGUMENT_DENIED')
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


def _crash_owned_core(owner, report_root, *, authorized=False):
    """CI-only fault on this supervisor's actual verified Popen, never a PID."""
    if (authorized is not True or not getattr(sys, 'frozen', False)
            or not hasattr(sys, '_MEIPASS')):
        raise ValueError('FROZEN_PROBE_CORE_CRASH_SCOPE_DENIED')
    if owner.status()['state'] != 'ready':
        raise ValueError('FROZEN_PROBE_CORE_CRASH_NOT_READY')
    height = owner.read.call('getblockcount', [])
    tip = owner.read.call('getblockhash', [height])
    process = owner.process
    # Last check before the destructive test fault: retain the real ownership,
    # exact image/metadata and live-Popen boundary. No lookup/adoption by PID.
    owner.binding._assert_image()
    if process is None or process.poll() is not None:
        raise ValueError('FROZEN_PROBE_CORE_CRASH_OWNERSHIP_DENIED')
    process.kill()
    exit_code = process.wait(timeout=15)
    # Popen.kill is SIGKILL on POSIX, TerminateProcess(..., 1) on Windows.
    # A different failure must not be relabelled as our injected kill.
    if exit_code != (1 if sys.platform == 'win32' else -9):
        raise ValueError('FROZEN_PROBE_CORE_CRASH_NOT_OBSERVED')
    if owner.status()['state'] != 'recovery-needed':
        raise ValueError('FROZEN_PROBE_CORE_CRASH_STATE_DENIED')
    del process
    if not (owner.directory/'regtest').is_dir():
        raise ValueError('FROZEN_PROBE_CORE_CRASH_DATADIR_LOST')
    owner.start()
    if (owner.status()['core_process_owned'] is not True
            or owner.read.call('getblockcount', []) != height
            or owner.read.call('getblockhash', [height]) != tip):
        raise ValueError('FROZEN_PROBE_CORE_CRASH_RESTART_DENIED')
    publish_report(report_root, {
        'frozen_entrypoint': True,
        'explicit_owned_core_crash_authorized': True,
        'owned_core_image_verified_before_kill': True,
        'actual_owned_core_kill_observed': True,
        'owned_core_crash_exit_code': exit_code,
        'crash_state': 'recovery-needed',
        'same_tip_after_core_restart': True,
        'same_height_after_core_restart': height,
        'persistent_chain_after_core_crash': True,
        'core_restart_owned': True,
        'wamd_sha256': owner.receipt['wamd_sha256'],
        'wam_cli_sha256': owner.receipt['wam_cli_sha256'],
        'mainnet_allowed': False, 'synthetic_rpc': False,
    })


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
        # Capture while QApplication is alive. The clean probe publishes its
        # result AFTER shutdown_qt; never recreate/access QApplication there.
        qt_platform = qt_application().platformName()
        def report(value):
            publish_report(args.report_root, {**value, 'frozen_entrypoint': True,
                'qt_platform': qt_platform})
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
        crashed = False
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
                if started and not crashed and owner.process is not None:
                    _crash_owned_core(owner, args.report_root,
                                      authorized=args.confirm_owned_core_crash)
                    crashed = True
                if started and owner.process is None and owner.status()['state'] == 'stopped':
                    stopped = True
                    break
            if not stopped or not crashed:
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
