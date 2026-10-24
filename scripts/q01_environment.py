"""Create-only, isolated Q01 build environment. No wallet/Core operations.

Run with declared CPython (macOS/Windows 3.12.10, Linux 3.12.15): python -I scripts/q01_environment.py ...
OS tools/libraries and Linux witness provisioning remain declared prerequisites;
this is dependency/source provenance, not host or supply-chain attestation.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

PIN = 'ac55f13423620252bdbf848c7e8a280c3b84721e'


def locked_versions(root, profile):
    versions = {}
    for name in ('headless', 'gui') if profile == 'gui' else ('headless',):
        for line in (root / 'requirements' / ('q01-' + name + '.lock')).read_text().splitlines():
            match = re.match(r'^([\w.-]+)==([\w.]+)(?: ; sys_platform == "(\w+)")?', line)
            if match and (not match[3] or match[3] == sys.platform):
                versions[re.sub(r'[-_.]+', '-', match[1]).lower()] = match[2]
    return versions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--profile', choices=('headless', 'gui'), required=True)
    ap.add_argument('--environment', type=Path, required=True)
    ap.add_argument('--receipt', type=Path, required=True)
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    expected_python = (3, 12, 15) if sys.platform == 'linux' else (3, 12, 10)
    if not sys.flags.isolated or sys.version_info[:3] != expected_python:
        raise SystemExit('Q01_DECLARED_ISOLATED_CPYTHON_REQUIRED')
    if any(os.environ.get(k) for k in ('PYTHONPATH', 'PYTHONHOME')):
        raise SystemExit('Q01_HIDDEN_PYTHON_ENVIRONMENT_DENIED')
    target = args.environment.absolute()
    if target.exists() or target.is_symlink() or target.resolve().is_relative_to(root):
        raise SystemExit('Q01_NEW_EXTERNAL_ENVIRONMENT_REQUIRED')
    if args.receipt.exists() or args.receipt.is_symlink():
        raise SystemExit('Q01_RECEIPT_EXISTS')
    # Authenticate ALL tracked source, including the build backend declarations,
    # before any editable installation can execute it. Do not import wam_sp.
    sys.path.insert(0, str(root / 'src'))
    from wam_regtest.build_provenance import capture, verify, public_receipt
    source = capture(root)
    source_head = os.environ.get('WAM_SOURCE_HEAD')
    dispatch = os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch'
    public_receipt(source, source_head=source_head, dispatch=dispatch)
    wsp = root / 'wsp-upstream'
    upstream = capture(wsp)
    if upstream['checkout_sha'] != PIN:
        raise SystemExit('Q01_WSP_PIN_DENIED')
    subprocess.run([sys.executable, '-I', '-m', 'venv', str(target)], check=True)
    python = target / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    environment = {k: v for k, v in os.environ.items()
                   if not k.startswith('PIP_') and k not in ('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV')}
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    # --isolated alone still permits global pip configuration. The null config
    # explicitly disables all config files; index/cache policy is command-line.
    environment['PIP_CONFIG_FILE'] = os.devnull
    pip = [str(python), '-I', '-m', 'pip', '--isolated', 'install',
           '--disable-pip-version-check', '--no-cache-dir']
    lock = root / 'requirements' / ('q01-' + args.profile + '.lock')
    with tempfile.TemporaryDirectory(prefix='wam-q01-pip-') as temporary:
        report = Path(temporary) / 'wheels.json'
        subprocess.run([*pip, '--index-url', 'https://pypi.org/simple',
                        '--only-binary=:all:', '--require-hashes', '-r', str(lock),
                        '--report', str(report)], env=environment, check=True)
        wheel_receipts = []
        for item in json.loads(report.read_text())['install']:
            download = item['download_info']
            wheel_receipts.append({'name': item['metadata']['name'],
                'version': item['metadata']['version'], 'url': download['url'],
                'sha256': download['archive_info']['hashes']['sha256']})
    verify(root, source)
    verify(wsp, upstream)
    # No build isolation/resolver that could fetch undeclared backend versions.
    # WSP's declared backend ==84.0.0 is installed from the hashed lock above.
    subprocess.run([*pip, '--no-deps', '--no-build-isolation', '-e', str(root),
                    '-e', str(wsp)], env=environment, check=True)
    subprocess.run([str(python), '-I', '-m', 'pip', '--isolated', 'check'],
                   env=environment, check=True)
    inventory = json.loads(subprocess.check_output([str(python), '-I', '-c',
        'import importlib.metadata as m,json,re,sys;'
        'assert sys.prefix!=sys.base_prefix and not __import__("site").ENABLE_USER_SITE;'
        'print(json.dumps({re.sub(r"[-_.]+","-",d.metadata["Name"]).lower():d.version for d in m.distributions()}))'],
        env=environment, text=True))
    expected = locked_versions(root, args.profile)
    expected.update({'wam-privacy-wallet-regtest': '0.1.0', 'wam-silent-payments': '1.0.0.dev0'})
    if inventory != expected:
        raise SystemExit('Q01_UNDECLARED_OR_MISSING_DEPENDENCY_DENIED')
    subprocess.run([str(python), '-I', '-c',
        'from pathlib import Path;from wam_regtest.wsp_live import _pinned_source;'
        '_pinned_source(Path.cwd()/"wsp-upstream")'], cwd=root, env=environment, check=True)
    verify(root, source)
    verify(wsp, upstream)
    receipt = {'schema': 'wam-q01-clean-environment/v1', 'status': 'SOURCE_INSTALL_PASS',
        'timestamp_utc': datetime.now(timezone.utc).isoformat(), 'platform': sys.platform,
        'python_version': sys.version.split()[0], 'profile': args.profile,
        'source': public_receipt(source, source_head=source_head, dispatch=dispatch),
        'wsp_source_commit': PIN, 'system_site_packages': False, 'pip_cache_used': False,
        'dependency_versions': inventory, 'downloaded_wheels': wheel_receipts,
        'lock_sha256': {p.name: sha256(p.read_bytes()).hexdigest() for p in
                        (root / 'requirements').glob('q01-*.lock')},
        'core_e2e_qualified': False, 'frozen_qualified': False,
        'physical_accepted': False, 'independent_reviewed': False}
    with args.receipt.open('x') as output:
        json.dump(receipt, output, sort_keys=True, indent=2)
        output.write('\n')
    # Subsequent job steps use ONLY the new environment (not setup-python/site).
    if os.environ.get('GITHUB_PATH'):
        with open(os.environ['GITHUB_PATH'], 'a') as output:
            output.write(str(python.parent) + '\n')
    print('Q01_FRESH_HASH_LOCKED_SOURCE_INSTALL_PASS')


if __name__ == '__main__':
    main()
