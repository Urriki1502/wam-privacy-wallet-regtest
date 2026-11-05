#!/usr/bin/env python3
"""Record V2.2 requalification on existing ports. No Win/Linux PASS from macOS."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

PREVIOUS_UI_PIN = 'b844dd371d4ac5dc3d0469eb899d6709e8ac407f'
RC1 = '144d87700b87a241467172adfad3692b41e1d273'
SUITES = (
    'tests.test_platform_reuse_contracts',
    'tests.test_linux_developer_core',
    'tests.test_fusion_design',
    'tests.test_fusion_v21_layout',
    'tests.test_q06_bip39_fusion_gui',
    'tests.test_q04_frozen_dispatch',
)


def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()


def main():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / 'src'))
    os.chdir(root)
    head = git('-C', str(root), 'rev-parse', 'HEAD')
    pin_ok = subprocess.call(
        ['git', '-C', str(root), 'merge-base', '--is-ancestor', PREVIOUS_UI_PIN, 'HEAD']) == 0
    rc1_ancestor = subprocess.call(
        ['git', '-C', str(root), 'merge-base', '--is-ancestor', RC1, PREVIOUS_UI_PIN]) == 0
    merge_base = subprocess.run(
        ['git', '-C', str(root), 'merge-base', RC1, PREVIOUS_UI_PIN], capture_output=True, text=True)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for name in SUITES:
        suite.addTests(loader.loadTestsFromName(name))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    evidence = {
        'schema': 'wam-fusion-v22-platform-requalify/v1',
        'recorded_at_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'functional_source_pin': head,
        'previous_ui_pin': PREVIOUS_UI_PIN,
        'checkout_sha': head,
        'pin_is_ancestor_of_head': pin_ok,
        'rc1_sha': RC1,
        'rc1_is_git_ancestor_of_pin': rc1_ancestor,
        'rc1_pin_merge_base': merge_base.stdout.strip() or None,
        'historical_ci': {
            'macos': 38747153198,
            'windows': 38747163508,
            'linux': 38747174307,
            'artifacts': 'expired_empty_total_count_0',
            'qualifies_v22': False,
        },
        'source_unittests': {
            'suites': list(SUITES),
            'tests_run': result.testsRun,
            'failures': len(result.failures),
            'errors': len(result.errors),
            'status': 'PASS' if result.wasSuccessful() else 'FAIL',
        },
        'native_frozen': {
            'macos-arm64': 'NOT EXECUTED',
            'windows-x64': 'BLOCKED / NOT EXECUTED',
            'linux-x86_64-desktop': 'BLOCKED / NOT EXECUTED',
            'linux-x86_64-headless': 'BLOCKED / NOT EXECUTED',
        },
        'v19': 'BLOCKED / NOT EXECUTED',
        'q06_accepted': False,
        'g6': 'BLOCKED',
        'g7': 'BLOCKED',
        'mainnet_allowed': False,
        'builders_reused': [
            'scripts/build_macos_bundle.sh',
            'scripts/build_windows_bundle.py',
            'scripts/build_linux_wallet.py',
            'scripts/build_linux_developer_core.sh',
        ],
    }
    out = root / 'release-candidates' / 'b844dd3' / 'evidence' / 'REQUALIFY_V22_LOCAL.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(evidence, indent=2, sort_keys=True) + '\n'
    out.write_text(payload)
    digest = sha256(payload.encode()).hexdigest()
    print('REQUALIFY_V22_SOURCE_TESTS=' + evidence['source_unittests']['status'])
    print('REQUALIFY_V22_EVIDENCE=' + str(out))
    print('REQUALIFY_V22_EVIDENCE_SHA256=' + digest)
    print('REQUALIFY_V22_WINDOWS=BLOCKED / NOT EXECUTED')
    print('REQUALIFY_V22_LINUX=BLOCKED / NOT EXECUTED')
    print('REQUALIFY_V22_V19=BLOCKED / NOT EXECUTED')
    return 0 if result.wasSuccessful() and pin_ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
