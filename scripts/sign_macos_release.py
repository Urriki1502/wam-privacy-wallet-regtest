#!/usr/bin/env python3
"""Developer ID signing + notarization of the EXACT macOS production app.

Never operates in place: the qualified ad-hoc artifact stays untouched and a
new signed copy (new executable identity) is written to --output-dir with its
own receipt. No credential is read from argv/env/files: the identity must be a
valid codesigning identity in the user's keychain and notarization uses a
pre-stored notarytool keychain profile name only.

--hardened-runtime-dry-run signs the copy AD-HOC with hardened runtime and the
reviewed entitlements, then executes it; this proves runtime readiness only,
is not distributable and is never notarized.

Policy conflict enforced here: official Core v0.1.13 wamd/wam-cli are pinned
by exact bytes and are ad-hoc linker-signed by the publisher. Re-signing them
changes their bytes, and Apple notarization requires every nested executable
to carry a Developer ID + hardened runtime + secure timestamp. Core is NEVER
re-signed; a notarization request is refused unless the bundled Core already
carries such a signature (publisher action) — BLOCKED otherwise.
"""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import plistlib
import re
import subprocess
import sys
import tempfile

PRODUCTION_BUNDLE_ID = 'org.wamcoin.privacywallet.regtest'
APP_NAME = 'WAM Privacy Wallet REGTEST.app'
CORE_PINS = {'wamd': 'fe04a61f17eb8047f1d2a537ebcb61b45cbde14c491bc332d2a2ab7ee18237ba',
             'wam-cli': '2b19fdac692cbed5810b6fa9663ac89f25ab8f346da84c5fd13bf2b8535e3e19'}
MACHO = {b'\xcf\xfa\xed\xfe', b'\xce\xfa\xed\xfe', b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca'}


def _deny(code):
    raise SystemExit('MACOS_SIGNING_' + code + '_DENIED')


def _run(args, **kw):
    return subprocess.run(args, capture_output=True, text=True, **kw)


def _digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def codesigning_identities():
    out = _run(['/usr/bin/security', 'find-identity', '-v', '-p', 'codesigning']).stdout
    return re.findall(r'\d+\) ([0-9A-F]{40}) "([^"]+)"', out)


def _core_members(app):
    found = {}
    for name in CORE_PINS:
        files = [p for p in app.rglob(name) if p.is_file() and not p.is_symlink()]
        if len(files) != 1 or _digest(files[0]) != CORE_PINS[name]:
            _deny('CORE_PIN')
        found[name] = files[0]
    return found


def _core_has_developer_id_runtime(path):
    details = _run(['codesign', '-dvv', str(path)]).stderr
    return ('Authority=Developer ID Application' in details
            and re.search(r'flags=0x[0-9a-f]*\(.*runtime', details) is not None
            and 'Timestamp=' in details)


def _macho_files(app, exclude):
    files = []
    for path in app.rglob('*'):
        if path.is_symlink() or not path.is_file() or path in exclude:
            continue
        with path.open('rb') as handle:
            if handle.read(4) in MACHO:
                files.append(path)
    # Deepest first so nested code is sealed before its container.
    return sorted(files, key=lambda p: len(p.parts), reverse=True)


def preflight(app, receipt, identity, dry_run, notarize, profile):
    facts = {}
    if app.name != APP_NAME or app.is_symlink() or not app.is_dir():
        _deny('APP_SHAPE')
    info = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
    if info.get('CFBundleIdentifier') != PRODUCTION_BUNDLE_ID:
        _deny('PRODUCTION_IDENTITY')  # never sign the qualification-only app as production
    data = json.loads(Path(receipt).read_text())
    executable = app / 'Contents/MacOS' / APP_NAME.removesuffix('.app')
    if (data.get('artifact_role') != 'allowlisted-regtest-wallet'
            or data.get('executable_sha256') != _digest(executable)
            or data.get('bundle_identifier') != PRODUCTION_BUNDLE_ID):
        _deny('RECEIPT_BINDING')
    facts['input_executable_sha256'] = _digest(executable)
    facts['source'] = data.get('source', {}).get('source_head_sha')
    cores = _core_members(app)
    facts['core_developer_id_runtime'] = {n: _core_has_developer_id_runtime(p) for n, p in cores.items()}
    available = codesigning_identities()
    facts['codesigning_identities_found'] = len(available)
    facts['developer_id_identities_found'] = sum('Developer ID Application' in n for _, n in available)
    if dry_run:
        if identity != '-' or notarize:
            _deny('DRY_RUN_SCOPE')
    else:
        if not any(identity in (h, n) and 'Developer ID Application' in n for h, n in available):
            _deny('DEVELOPER_ID_IDENTITY_UNAVAILABLE')
        if notarize:
            if not profile or not re.fullmatch(r'[A-Za-z0-9._-]{1,64}', profile):
                _deny('NOTARY_PROFILE_REQUIRED')
            if not all(facts['core_developer_id_runtime'].values()):
                _deny('CORE_PIN_CONFLICT_PUBLISHER_DEVELOPER_ID_REQUIRED')
    return facts, cores


def sign(app_in, output_dir, identity, entitlements, dry_run):
    output_dir.mkdir(mode=0o700)
    app = output_dir / APP_NAME
    if _run(['ditto', str(app_in), str(app)]).returncode:
        _deny('COPY')
    cores = _core_members(app)
    base = ['codesign', '--force', '--options', 'runtime', '--sign', identity]
    if not dry_run:
        base.append('--timestamp')
    for path in _macho_files(app, set(cores.values())):
        if _run([*base, str(path)]).returncode:
            _deny('NESTED_SIGN')
    effective = entitlements
    if dry_run:
        # Ad-hoc code has no Team ID, so hardened-runtime library validation
        # rejects the bundle's own dylibs. Emulate "same Team ID" for the dry
        # run ONLY; production entitlements never carry this waiver.
        reviewed = plistlib.loads(Path(entitlements).read_bytes())
        reviewed['com.apple.security.cs.disable-library-validation'] = True
        effective = output_dir / 'DRY_RUN_ONLY_team-id-emulation.entitlements'
        effective.write_bytes(plistlib.dumps(reviewed))
    if _run([*base, '--entitlements', str(effective), str(app)]).returncode:
        _deny('APP_SIGN')
    verify = _run(['codesign', '--verify', '--deep', '--strict', '--verbose=2', str(app)])
    if verify.returncode:
        _deny('VERIFY')
    _core_members(app)  # Core bytes still exactly pinned (never re-signed)
    return app


def exercise(app):
    """Hardened-runtime launch proof: self-check + every developer argv refused."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'signing_policy', Path(__file__).resolve().with_name('production_packaging.py'))
    policy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(policy)
    executable = app / 'Contents/MacOS' / APP_NAME.removesuffix('.app')
    with tempfile.TemporaryDirectory(prefix='wam-sign-exercise-') as cwd:
        env = dict(PATH='/usr/bin:/bin:/usr/sbin:/sbin', HOME=cwd, TMPDIR=cwd, LANG='C',
                   QT_QPA_PLATFORM='offscreen')
        check = subprocess.run([str(executable), '--check-bundle'], cwd=cwd, env=env,
                               stdin=subprocess.DEVNULL, capture_output=True, timeout=120)
        hostile = dict(env, CI='true', GITHUB_ACTIONS='true', WAM_Q06_CI_SPEND_QUALIFY='1')
        negatives = [subprocess.run([str(executable), *argv], cwd=cwd, env=hostile,
                                    stdin=subprocess.DEVNULL, capture_output=True,
                                    timeout=60).returncode for argv in policy.DEVELOPER_ARGV]
    return dict(check_bundle_returncode=check.returncode,
                developer_argv=len(negatives), developer_argv_all_64=all(r == 64 for r in negatives))


def notarize_and_staple(app, output_dir, profile):
    archive = output_dir / 'notarization-submission.zip'
    if _run(['ditto', '-c', '-k', '--keepParent', str(app), str(archive)]).returncode:
        _deny('ZIP')
    submit = _run(['xcrun', 'notarytool', 'submit', str(archive), '--keychain-profile', profile,
                   '--wait', '--output-format', 'json'], timeout=3600)
    result = json.loads(submit.stdout or '{}')
    if submit.returncode or result.get('status') != 'Accepted':
        return dict(status='NOTARIZATION_' + str(result.get('status', 'FAILED')).upper(),
                    submission_id=result.get('id'))
    if _run(['xcrun', 'stapler', 'staple', str(app)]).returncode:
        _deny('STAPLE')
    assess = _run(['spctl', '--assess', '--type', 'execute', '-vv', str(app)])
    return dict(status='NOTARIZED_STAPLED', submission_id=result.get('id'),
                gatekeeper_accepted=assess.returncode == 0)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--app', type=Path, required=True)
    p.add_argument('--receipt', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--identity', required=True)
    p.add_argument('--entitlements', type=Path,
                   default=Path(__file__).resolve().parents[1] / 'assets/macos-hardened-runtime.entitlements')
    p.add_argument('--hardened-runtime-dry-run', action='store_true')
    p.add_argument('--notarize', action='store_true')
    p.add_argument('--notary-profile')
    a = p.parse_args()
    a.output_dir = a.output_dir.absolute()
    if sys.platform != 'darwin' or a.output_dir.exists():
        _deny('HOST_OR_OUTPUT')
    facts, _ = preflight(a.app.resolve(), a.receipt, a.identity, a.hardened_runtime_dry_run,
                         a.notarize, a.notary_profile)
    app = sign(a.app.resolve(), a.output_dir, a.identity, a.entitlements, a.hardened_runtime_dry_run)
    executable = app / 'Contents/MacOS' / APP_NAME.removesuffix('.app')
    details = _run(['codesign', '-dvvv', str(app)]).stderr
    record = dict(facts, mode='HARDENED_RUNTIME_DRY_RUN_ADHOC' if a.hardened_runtime_dry_run else 'DEVELOPER_ID',
                  distributable=False if a.hardened_runtime_dry_run else None,
                  signed_executable_sha256=_digest(executable),
                  cdhash=re.findall(r'CDHash=([0-9a-f]+)', details),
                  team_identifier=re.findall(r'TeamIdentifier=(\S+)', details),
                  hardened_runtime=bool(re.search(r'flags=0x[0-9a-f]*\(.*runtime', details)),
                  entitlements_sha256=_digest(a.entitlements),
                  dry_run_team_id_emulation_disable_library_validation=a.hardened_runtime_dry_run,
                  core_resigned=False, exercise=exercise(app))
    if a.notarize:
        record['notarization'] = notarize_and_staple(app, a.output_dir, a.notary_profile)
    else:
        record['notarization'] = 'NOT_REQUESTED'
    (a.output_dir / 'SIGNED_RELEASE_RECEIPT.json').write_text(json.dumps(record, indent=2) + '\n')
    print('MACOS_SIGNING_RECEIPT', record['mode'], record['signed_executable_sha256'])
    return 0 if record['exercise']['check_bundle_returncode'] == 0 and record['exercise']['developer_argv_all_64'] else 2


if __name__ == '__main__':
    sys.exit(main())
