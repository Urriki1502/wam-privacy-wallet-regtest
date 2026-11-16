"""Bind macOS production and qualification-only outputs of ONE build to ONE commit.

Used by hosted workflows after `scripts/build_macos_bundle.sh` (no arguments),
which writes the allowlisted production app to <root>/package-output and the
separately identified qualification-only app to <root>/qualification-only/.
Only production payloads are published as the wallet; qualification-only
DMG/ZIP bytes are never published. Receipts from different commits, roles or
executables are refused. This is a consistency check, not an attestation, and
grants no acceptance: production_qualified stays false until real normal-UI E2E.

Two stages run before anything is published (CDX-AUD-008):
  1. binding: receipts/roles/commit/hashes/bundle ids are mutually consistent;
  2. payload: the actual bytes are opened and must agree with that metadata --
     PyInstaller PYZ inventory equals the reviewed allowlist (and the producer's
     inventory claim), every DEVELOPER_ARGV case is re-executed on the actual
     binary and returns 64, the ZIP and read-only-mounted DMG contain exactly
     the same production executable, bundle id and pinned Core bytes, the
     bundled WSP manifest names the pinned commit, codesign verifies, and the
     qualification ZIP holds only the qualification identity.
The command line always runs both stages; binding-only exists for unit fixtures.
"""
import argparse
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile

PRODUCTION_APP = 'WAM Privacy Wallet REGTEST.app'
QUALIFICATION_APP = 'WAM Privacy Wallet REGTEST QUALIFICATION.app'
PRODUCTION_BUNDLE_ID = 'org.wamcoin.privacywallet.regtest'
QUALIFICATION_BUNDLE_ID = 'org.wamcoin.privacywallet.regtest.qualification'
PRODUCTION_FILES = ('WAM-Privacy-Wallet-REGTEST-macOS-ARM64.dmg',
                    'WAM-Privacy-Wallet-REGTEST-macOS-ARM64.app.zip')
QUALIFICATION_FILES = ('WAM-Privacy-Wallet-REGTEST-QUALIFICATION-ONLY-macOS-ARM64.dmg',
                       'WAM-Privacy-Wallet-REGTEST-QUALIFICATION-ONLY-macOS-ARM64.app.zip')
PRODUCTION_RECEIPTS = ('PRODUCTION_BUILD_RECEIPT.json', 'PRODUCTION_MODULE_INVENTORY.json',
                       'PRODUCTION_DISPATCH_NEGATIVES.json')
CORE_PINS = {'wamd': 'fe04a61f17eb8047f1d2a537ebcb61b45cbde14c491bc332d2a2ab7ee18237ba',
             'wam-cli': '2b19fdac692cbed5810b6fa9663ac89f25ab8f346da84c5fd13bf2b8535e3e19'}
WSP_PIN = 'ac55f13423620252bdbf848c7e8a280c3b84721e'
PRIVATE_SUFFIXES = ('.sqlite', '.db', '.enc', '.keychain-db', '.conf', '.cookie')
MAX_EVIDENCE_BYTES = 32 * 1024 * 1024


def _deny(code):
    raise ValueError('MACOS_CI_OUTPUT_' + code + '_DENIED')


def _digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def _json(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 8 * 1024 * 1024:
        _deny('RECEIPT_SHAPE')
    return json.loads(path.read_text())


def _app(directory, name, bundle_id):
    app = Path(directory) / name
    if app.is_symlink() or not app.is_dir():
        _deny('APP_SHAPE')
    if plistlib.loads((app / 'Contents/Info.plist').read_bytes()).get('CFBundleIdentifier') != bundle_id:
        _deny('BUNDLE_IDENTITY')
    executable = app / 'Contents/MacOS' / name.removesuffix('.app')
    if executable.is_symlink() or not executable.is_file():
        _deny('EXECUTABLE_SHAPE')
    return _digest(executable)


def _sums(directory):
    lines = [f'{_digest(p)}  {p.name}\n' for p in sorted(Path(directory).iterdir())
             if p.is_file() and not p.is_symlink() and p.name != 'SHA256SUMS.txt']
    (Path(directory) / 'SHA256SUMS.txt').write_bytes(''.join(lines).encode())


def verify(build_root, expected_sha, publish, *, payload_audit=True):
    build_root, publish = Path(build_root), Path(publish)
    if not re.fullmatch('[0-9a-f]{40}', expected_sha):
        _deny('COMMIT_SHAPE')
    if publish.exists():
        _deny('PUBLISH_EXISTS')
    prod = build_root / 'package-output'
    qual_root = build_root / 'qualification-only'
    qual = qual_root / 'package-output'

    # Production: one allowlisted executable bound to the expected commit.
    receipt = _json(prod / 'PRODUCTION_BUILD_RECEIPT.json')
    source = receipt.get('source') or {}
    if (receipt.get('artifact_role') != 'allowlisted-regtest-wallet'
            or source.get('checkout_sha') != expected_sha
            or source.get('source_head_sha') != expected_sha
            or source.get('tracked_source_matches_head') is not True
            or source.get('source_unchanged_across_build') is not True):
        _deny('PRODUCTION_SOURCE')
    if receipt.get('mainnet_allowed') is not False or receipt.get('production_qualified') is not False:
        _deny('PRODUCTION_SCOPE')
    if receipt.get('core_sha256') != CORE_PINS or receipt.get('wsp_source_commit') != WSP_PIN:
        _deny('PRODUCTION_PINS')
    files = receipt.get('files_sha256')
    if type(files) is not dict or set(files) != set(PRODUCTION_FILES):
        _deny('PRODUCTION_FILES')
    production_hashes = {}
    for name in PRODUCTION_FILES:
        path = prod / name
        if path.is_symlink() or not path.is_file() or _digest(path) != files[name]:
            _deny('PRODUCTION_HASH')
        production_hashes[name] = files[name]
    listed = {}
    for line in (prod / 'SHA256SUMS.txt').read_bytes().decode().splitlines():
        digest, _, name = line.partition('  ')
        listed[name] = digest
    if any(listed.get(n) != _digest(prod / n) for n in PRODUCTION_FILES + PRODUCTION_RECEIPTS):
        _deny('PRODUCTION_SUMS')
    inventory = _json(prod / 'PRODUCTION_MODULE_INVENTORY.json')
    if inventory.get('status') != 'PASS_EXACT_PRODUCTION_ALLOWLIST' or inventory.get('developer_dispatch') is not False:
        _deny('PRODUCTION_INVENTORY')
    negatives = _json(prod / 'PRODUCTION_DISPATCH_NEGATIVES.json')
    if type(negatives) is not list or not negatives or any(n.get('returncode') != 64 for n in negatives):
        _deny('PRODUCTION_DISPATCH')
    production_executable = _app(build_root / 'dist', PRODUCTION_APP, PRODUCTION_BUNDLE_ID)
    if receipt.get('executable_sha256') != production_executable:
        _deny('PRODUCTION_EXECUTABLE')

    # Qualification-only: same commit, explicit role, distinct identity/bytes.
    marker = _json(qual_root / 'NOT_FOR_DISTRIBUTION.json')
    if marker.get('artifact_role') != 'qualification-only' or marker.get('production_binary_qualified') is not False:
        _deny('QUALIFICATION_MARKER')
    qreceipt = _json(qual / 'SHA256SUMS.json')
    if (qreceipt.get('artifact_role') != 'qualification-only'
            or qreceipt.get('distribution_allowed') is not False
            or qreceipt.get('source_commit') != expected_sha
            or qreceipt.get('qualification_scope') != 'full'
            or qreceipt.get('full_exact_commit_Q01_Q06_qualified') is not True
            or qreceipt.get('mainnet_allowed') is not False):
        _deny('QUALIFICATION_SOURCE')
    if (qreceipt.get('wamd_sha256') != CORE_PINS['wamd']
            or qreceipt.get('wam_cli_sha256') != CORE_PINS['wam-cli']):
        _deny('QUALIFICATION_PINS')
    qfiles = qreceipt.get('files')
    if type(qfiles) is not dict or set(qfiles) != set(QUALIFICATION_FILES):
        _deny('QUALIFICATION_FILES')
    qualification_hashes = {}
    for name in QUALIFICATION_FILES:
        path = qual / name
        if path.is_symlink() or not path.is_file() or _digest(path) != qfiles[name].get('sha256'):
            _deny('QUALIFICATION_HASH')
        qualification_hashes[name] = qfiles[name]['sha256']
    qualification_executable = _app(qual_root / 'dist', QUALIFICATION_APP, QUALIFICATION_BUNDLE_ID)
    if (set(production_hashes.values()) & set(qualification_hashes.values())
            or production_executable == qualification_executable
            or any((prod / n).exists() for n in QUALIFICATION_FILES)
            or any((qual / n).exists() for n in PRODUCTION_FILES)):
        _deny('ROLE_MIXING')

    payload = None
    if payload_audit is not False:
        payload = verify_payload(build_root, production_executable, qualification_executable,
                                 production_hashes, inventory, negatives)

    # Publish into a private sibling, then rename: no partial publish on denial.
    staging = publish.with_name(publish.name + '.staging')
    if staging.exists():
        _deny('PUBLISH_EXISTS')
    try:
        (staging / 'production').mkdir(parents=True)
        for name in PRODUCTION_FILES + PRODUCTION_RECEIPTS:
            shutil.copyfile(prod / name, staging / 'production' / name)
        (staging / 'production/README.txt').write_text(
            'WAM Fusion REGTEST - macOS ARM64 allowlisted wallet (review only)\n\n'
            f'Commit: {expected_sha}\nBundle identifier: {PRODUCTION_BUNDLE_ID}\n'
            f'WSP pin: {WSP_PIN}\nwamd: {CORE_PINS["wamd"]}\nwam-cli: {CORE_PINS["wam-cli"]}\n\n'
            'Ad-hoc signed, not Developer ID, not notarized. Not a release, not mainnet,\n'
            'not Q06 acceptance. production_qualified=false until real normal-UI E2E.\n'
            'Qualification-only bytes are NOT included; their JSON evidence is separate.\n')
        _sums(staging / 'production')
        evidence = staging / 'qualification-only-evidence'
        evidence.mkdir()
        shutil.copyfile(qual_root / 'NOT_FOR_DISTRIBUTION.json', evidence / 'NOT_FOR_DISTRIBUTION.json')
        for path in sorted(qual.rglob('*')):
            if path.is_symlink():
                _deny('EVIDENCE_SYMLINK')
            if not path.is_file() or path.name in QUALIFICATION_FILES:
                continue
            if path.suffix.lower() in PRIVATE_SUFFIXES or path.name == 'wam.conf':
                _deny('EVIDENCE_PRIVATE')
            if path.stat().st_size > MAX_EVIDENCE_BYTES:
                _deny('EVIDENCE_SIZE')
            target = evidence / path.relative_to(qual)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        binding = dict(schema='wam-macos-ci-output-binding/v1', source_commit=expected_sha,
                       production=dict(bundle_identifier=PRODUCTION_BUNDLE_ID,
                                       executable_sha256=production_executable, files_sha256=production_hashes),
                       qualification_only=dict(bundle_identifier=QUALIFICATION_BUNDLE_ID,
                                               executable_sha256=qualification_executable,
                                               files_sha256=qualification_hashes, published_payloads=False),
                       payload_verification=payload if payload is not None else 'NOT_RUN_BINDING_ONLY',
                       production_qualified=False, mainnet_allowed=False, acceptance=False)
        (staging / 'CI_OUTPUT_BINDING.json').write_text(json.dumps(binding, indent=2, sort_keys=True) + '\n')
        staging.rename(publish)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return binding


def _packaging():
    spec = importlib.util.spec_from_file_location(
        'wam_production_packaging_policy', Path(__file__).resolve().with_name('production_packaging.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _plist_id(data):
    try:
        return plistlib.loads(data).get('CFBundleIdentifier')
    except Exception:
        _deny('PAYLOAD_PLIST')


def _bundle_tree(app, name, bundle_id, executable_sha256):
    """Actual app bytes: identity, executable, single real pinned Core members."""
    if app.is_symlink() or not app.is_dir():
        _deny('PAYLOAD_APP_SHAPE')
    if _plist_id((app / 'Contents/Info.plist').read_bytes()) != bundle_id:
        _deny('PAYLOAD_BUNDLE_IDENTITY')
    executable = app / 'Contents/MacOS' / name.removesuffix('.app')
    if executable.is_symlink() or not executable.is_file() or _digest(executable) != executable_sha256:
        _deny('PAYLOAD_EXECUTABLE')
    for member, digest in CORE_PINS.items():
        found = [p for p in app.rglob(member) if p.is_file() and not p.is_symlink()]
        if len(found) != 1 or _digest(found[0]) != digest:
            _deny('PAYLOAD_CORE_PIN')
    manifest = app / 'Contents/Resources/wsp-source/SOURCE_SHA256.json'
    if manifest.is_symlink() or not manifest.is_file():
        _deny('PAYLOAD_WSP_MANIFEST')
    if json.loads(manifest.read_text()).get('source_commit') != WSP_PIN:
        _deny('PAYLOAD_WSP_PIN')
    others = [p.name for p in app.parent.iterdir() if p.suffix == '.app' and p.name != name]
    return others


def _zip_tree(path, name, bundle_id, executable_sha256, forbidden):
    """Structure + bytes of a ditto ZIP without extraction."""
    if not zipfile.is_zipfile(path):
        _deny('PAYLOAD_ZIP_SHAPE')
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        prefix = name + '/'
        for info in infos:
            parts = Path(info.filename).parts
            if (not info.filename.startswith(prefix) or info.filename.startswith('/')
                    or '..' in parts or '\\' in info.filename):
                _deny('PAYLOAD_ZIP_MEMBER')
        if any(info.filename.startswith(forbidden + '/') for info in infos):
            _deny('PAYLOAD_ZIP_ROLE')

        def regular(member):
            hits = [i for i in infos if i.filename == member
                    and not stat.S_ISLNK(i.external_attr >> 16)]
            if len(hits) != 1:
                _deny('PAYLOAD_ZIP_MEMBER_MISSING')
            return archive.read(hits[0])
        if _plist_id(regular(prefix + 'Contents/Info.plist')) != bundle_id:
            _deny('PAYLOAD_ZIP_BUNDLE_IDENTITY')
        if sha256(regular(prefix + 'Contents/MacOS/' + name.removesuffix('.app'))).hexdigest() != executable_sha256:
            _deny('PAYLOAD_ZIP_EXECUTABLE')
        for member, digest in CORE_PINS.items():
            hits = [i for i in infos if i.filename.endswith('/' + member)
                    and not stat.S_ISLNK(i.external_attr >> 16) and not i.is_dir()]
            if len(hits) != 1 or sha256(archive.read(hits[0])).hexdigest() != digest:
                _deny('PAYLOAD_ZIP_CORE_PIN')


def _run(args, **kwargs):
    return subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, **kwargs)


def _dmg_tree(path, executable_sha256):
    """Mount read-only, nobrowse; compare actual app; always detach."""
    if sys.platform != 'darwin':
        _deny('PAYLOAD_DMG_PLATFORM')
    if _run(['hdiutil', 'imageinfo', str(path)], timeout=120).returncode != 0:
        _deny('PAYLOAD_DMG_SHAPE')
    with tempfile.TemporaryDirectory(prefix='wam-ci-dmg-') as temporary:
        mount = Path(temporary) / 'mnt'
        mount.mkdir()
        attached = _run(['hdiutil', 'attach', '-readonly', '-nobrowse', '-noautoopen',
                         '-mountpoint', str(mount), str(path)], timeout=300)
        if attached.returncode != 0:
            _deny('PAYLOAD_DMG_ATTACH')
        try:
            apps = sorted(p.name for p in mount.iterdir() if p.suffix == '.app')
            if apps != [PRODUCTION_APP]:
                _deny('PAYLOAD_DMG_ROLE')
            _bundle_tree(mount / PRODUCTION_APP, PRODUCTION_APP, PRODUCTION_BUNDLE_ID, executable_sha256)
            if _run(['codesign', '--verify', '--deep', '--strict', str(mount / PRODUCTION_APP)],
                    timeout=300).returncode != 0:
                _deny('PAYLOAD_DMG_CODESIGN')
        finally:
            if _run(['hdiutil', 'detach', str(mount)], timeout=120).returncode != 0:
                _deny('PAYLOAD_DMG_DETACH')


def _negatives(executable, policy, receipt_negatives):
    """Re-execute EVERY reviewed developer argv on the actual binary (hostile env)."""
    singles = {tuple(argv) for argv in policy if len(argv) == 1}
    for entry in receipt_negatives:
        if type(entry) is not dict or (entry.get('mode'),) not in singles or entry.get('returncode') != 64:
            _deny('PAYLOAD_DISPATCH_RECEIPT')
    executed = []
    with tempfile.TemporaryDirectory(prefix='wam-ci-argv-') as cwd:
        env = dict(PATH='/usr/bin:/bin:/usr/sbin:/sbin', HOME=cwd, TMPDIR=cwd, LANG='C',
                   QT_QPA_PLATFORM='offscreen', CI='true', GITHUB_ACTIONS='true',
                   WAM_BUILD_SCOPE='full', WAM_QUALIFICATION='1', WAM_Q06_CI_SPEND_QUALIFY='1')
        for argv in policy:
            try:
                result = _run([str(executable), *argv], cwd=cwd, env=env, timeout=30)
            except subprocess.TimeoutExpired:
                _deny('PAYLOAD_DISPATCH_TIMEOUT')
            if result.returncode != 64:
                _deny('PAYLOAD_DISPATCH')
            executed.append(dict(argv=list(argv), returncode=64))
    return executed


def verify_payload(build_root, production_executable, qualification_executable,
                   production_hashes, inventory, receipt_negatives):
    """Open the actual payloads; producer metadata must agree with the bytes."""
    policy = _packaging()
    app = build_root / 'dist' / PRODUCTION_APP
    if _bundle_tree(app, PRODUCTION_APP, PRODUCTION_BUNDLE_ID, production_executable):
        _deny('PAYLOAD_DIST_ROLE')
    try:
        actual = policy.audit(app / 'Contents/MacOS' / PRODUCTION_APP.removesuffix('.app'), app, 'macos')
    except Exception:
        _deny('PAYLOAD_PYZ_AUDIT')
    if (actual.get('status') != 'PASS_EXACT_PRODUCTION_ALLOWLIST'
            or inventory.get('modules') != actual['modules']
            or inventory.get('entrypoint', actual['entrypoint']) != actual['entrypoint']):
        _deny('PAYLOAD_INVENTORY_MISMATCH')
    if _run(['codesign', '--verify', '--deep', '--strict', str(app)], timeout=300).returncode != 0:
        _deny('PAYLOAD_CODESIGN')
    prod = build_root / 'package-output'
    _zip_tree(prod / PRODUCTION_FILES[1], PRODUCTION_APP, PRODUCTION_BUNDLE_ID,
              production_executable, QUALIFICATION_APP)
    _dmg_tree(prod / PRODUCTION_FILES[0], production_executable)
    executed = _negatives(app / 'Contents/MacOS' / PRODUCTION_APP.removesuffix('.app'),
                          policy.DEVELOPER_ARGV, receipt_negatives)
    qual_app = build_root / 'qualification-only/dist' / QUALIFICATION_APP
    _bundle_tree(qual_app, QUALIFICATION_APP, QUALIFICATION_BUNDLE_ID, qualification_executable)
    _zip_tree(build_root / 'qualification-only/package-output' / QUALIFICATION_FILES[1],
              QUALIFICATION_APP, QUALIFICATION_BUNDLE_ID, qualification_executable, PRODUCTION_APP)
    return dict(status='PASS_ACTUAL_PAYLOAD_AGREES_WITH_RECEIPTS', pyz_modules=len(actual['modules']),
                developer_argv_executed=len(executed), developer_argv_all_returned_64=True,
                zip_and_dmg_executable_sha256=production_executable,
                core_sha256=CORE_PINS, wsp_manifest_commit=WSP_PIN, codesign_deep_strict=True,
                qualification_zip_identity=QUALIFICATION_BUNDLE_ID,
                qualification_dmg_not_mounted_not_published=True,
                wam_sp_pyz_bytes_not_compared_to_pin=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build-root', required=True, type=Path)
    parser.add_argument('--expected-sha', required=True)
    parser.add_argument('--publish', required=True, type=Path)
    args = parser.parse_args()
    binding = verify(args.build_root, args.expected_sha, args.publish)
    print('MACOS_CI_OUTPUT_BINDING_PASS', binding['production']['executable_sha256'], flush=True)


if __name__ == '__main__':
    sys.exit(main())
