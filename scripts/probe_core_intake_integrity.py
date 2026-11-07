"""Q15 offline intake integrity: real GPG, real binaries, no network, no Core start.

Re-verifies the retained signed v0.1.13 manifest with the production verifier,
then proves genuine refusals: a throwaway (non-publisher) signer, a tampered
manifest, and the macOS runtime gate against tampered, wrong-platform, linked
and wrong-receipt Core directories. All mutations happen on private copies in
a new temporary directory; official binaries and the trust root are never
modified. Optionally records official member hashes inside a frozen .app.
"""
from hashlib import sha256
import argparse, json, os, platform, shutil, subprocess, tempfile
from datetime import datetime, timezone
from pathlib import Path


def sha(p): return sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--core-dir', type=Path, required=True)
    ap.add_argument('--other-platform-wamd', type=Path, required=True)
    ap.add_argument('--app', type=Path); ap.add_argument('--report', type=Path, required=True)
    a = ap.parse_args()
    if a.report.exists(): ap.error('new report required')
    root = Path(__file__).resolve().parents[1]
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--'], cwd=root, check=True)
    from wam_regtest import official_core_v013 as v
    from wam_regtest.release import _validate_signed_sums, ReleaseError, FINGERPRINT
    from wam_regtest.core import verified_core_paths, CoreSmokeError
    core = a.core_dir.resolve(strict=True)
    before = {n: sha(core / n) for n in ('wamd', 'wam-cli', 'SIGNING-KEY.asc', 'SHA256SUMS', 'SHA256SUMS.asc', 'receipt.json')}
    r = dict(source_sha=head, status='FAIL', network_used=False, official_bytes_modified=False, cases={})
    gpg = shutil.which('gpg'); assert gpg
    cleanup = []
    try:
        _run(a, core, r, v, gpg, cleanup, _validate_signed_sums, ReleaseError, FINGERPRINT,
             verified_core_paths, CoreSmokeError)
    finally:
        for home in cleanup:
            subprocess.run(['gpgconf', '--kill', 'gpg-agent'], env=dict(os.environ, GNUPGHOME=str(home)), capture_output=True)
            shutil.rmtree(home, ignore_errors=True)
    after = {n: sha(core / n) for n in before}
    assert after == before; r['official_intake_bytes_unchanged'] = True
    finish(a, r, gpg, root, head, v)


def _run(a, core, r, v, gpg, cleanup, _validate_signed_sums, ReleaseError, FINGERPRINT, verified_core_paths, CoreSmokeError):
    with tempfile.TemporaryDirectory(prefix='wam-q15-intake-') as temp:
        t = Path(temp); t.chmod(0o700)

        def manifest_dir(name, key=None, sums=None, sig=None):
            d = t / name; d.mkdir(mode=0o700)
            shutil.copyfile(key or core / 'SIGNING-KEY.asc', d / 'SIGNING-KEY.asc')
            shutil.copyfile(sums or core / 'SHA256SUMS', d / 'SHA256SUMS')
            shutil.copyfile(sig or core / 'SHA256SUMS.asc', d / 'SHA256SUMS.asc')
            return d

        # 1. Genuine signed manifest with the production verifier.
        assert sha(core / 'SHA256SUMS') == v.SUMS_SHA256 and sha(core / 'SHA256SUMS.asc') == v.SIGNATURE_SHA256
        got = _validate_signed_sums(gpg, manifest_dir('genuine'), v.ARCHIVES['macos-arm64'][0])
        assert got == v.ARCHIVES['macos-arm64'][2]
        listed = dict(reversed(line.split()) for line in (core / 'SHA256SUMS').read_text().splitlines() if line.strip())
        for plat, (asset, size, digest) in v.ARCHIVES.items():
            assert listed.get(asset) == digest, plat
        r['cases']['signed_manifest_genuine'] = dict(status='PASS', fingerprint=FINGERPRINT,
            archives_authenticated=sorted(v.ARCHIVES), macos_archive_sha256=got)

        # 2. Genuine non-publisher signer (throwaway key, empty passphrase, temp keyring only).
        # Short private home: gpg-agent sockets must fit macOS's path limit.
        home = Path(tempfile.mkdtemp(prefix='wq15-', dir='/tmp')); home.chmod(0o700)
        env = dict(os.environ, GNUPGHOME=str(home))
        cleanup.append(home)
        subprocess.run([gpg, '--batch', '--pinentry-mode', 'loopback', '--passphrase', '', '--quick-gen-key',
                        'WAM Phase4 throwaway test signer <invalid@invalid.invalid>', 'ed25519', 'sign', '1d'],
                       env=env, check=True, capture_output=True)
        subprocess.run([gpg, '--batch', '--armor', '--export', '--output', str(t / 'throwaway.asc')], env=env, check=True, capture_output=True)
        subprocess.run([gpg, '--batch', '--pinentry-mode', 'loopback', '--passphrase', '', '--armor', '--detach-sign',
                        '--output', str(t / 'throwaway.sig'), str(core / 'SHA256SUMS')], env=env, check=True, capture_output=True)
        tampered = t / 'tampered-SHA256SUMS'
        raw = bytearray((core / 'SHA256SUMS').read_bytes()); raw[0] ^= 1; tampered.write_bytes(bytes(raw))
        for name, kwargs in [('wrong_signer_key_and_signature', dict(key=t / 'throwaway.asc', sig=t / 'throwaway.sig')),
                             ('publisher_key_with_foreign_signature', dict(sig=t / 'throwaway.sig')),
                             ('tampered_manifest_with_publisher_signature', dict(sums=tampered))]:
            try:
                _validate_signed_sums(gpg, manifest_dir(name, **kwargs), v.ARCHIVES['macos-arm64'][0])
            except ReleaseError as error:
                r['cases'][name] = dict(status='PASS_REFUSED', code=error.args[0])
            else:
                raise AssertionError(name + '_ACCEPTED')

        # 3. Runtime macOS gate on private copies.
        def core_copy(name, wamd=None, receipt=None, link=None):
            d = t / name; d.mkdir(mode=0o700)
            for n in ('wam-cli',):
                shutil.copyfile(core / n, d / n); (d / n).chmod(0o700)
            if link == 'symlink':
                (d / 'wamd').symlink_to(core / 'wamd')
            else:
                shutil.copyfile(wamd or core / 'wamd', d / 'wamd'); (d / 'wamd').chmod(0o700)
                if link == 'hardlink':
                    os.link(d / 'wamd', t / (name + '-second-link'))
            data = json.loads((core / 'receipt.json').read_text()); data.update(receipt or {})
            (d / 'receipt.json').write_text(json.dumps(data))
            return d
        node, cli, receipt = verified_core_paths(core_copy('genuine-copy'))
        assert receipt['wamd_sha256'] == v.MEMBERS['macos-arm64']['wamd']
        r['cases']['runtime_gate_genuine_copy'] = dict(status='PASS')
        flipped = t / 'flipped-wamd'; b = bytearray((core / 'wamd').read_bytes()); b[-1] ^= 1; flipped.write_bytes(bytes(b))
        assert sha(a.other_platform_wamd) == v.MEMBERS['linux-x86_64']['wamd']
        negatives = [('tampered_wamd_one_byte', dict(wamd=flipped)),
                     ('official_linux_wamd_substituted', dict(wamd=a.other_platform_wamd)),
                     ('official_mac_cli_as_wamd', dict(wamd=core / 'wam-cli')),
                     ('symlinked_wamd', dict(link='symlink')),
                     ('hardlinked_wamd', dict(link='hardlink')),
                     ('receipt_wrong_version', dict(receipt={'tag': 'v0.1.11'})),
                     ('receipt_wrong_signer', dict(receipt={'publisher_fingerprint': '0' * 40})),
                     ('receipt_unsigned', dict(receipt={'signed_archive_verified': False})),
                     ('receipt_mainnet', dict(receipt={'mainnet_allowed': True})),
                     ('receipt_hash_matches_tampered_binary', dict(wamd=flipped, receipt={'wamd_sha256': sha(flipped)}))]
        for name, kwargs in negatives:
            try:
                verified_core_paths(core_copy(name, **kwargs))
            except CoreSmokeError as error:
                r['cases'][name] = dict(status='PASS_REFUSED', code=error.args[0])
            else:
                raise AssertionError(name + '_ACCEPTED')


def finish(a, r, gpg, root, head, v):
    if a.app:
        found = {}
        for name, digest in v.MEMBERS['macos-arm64'].items():
            hits = [p for p in a.app.rglob(name) if p.is_file() and not p.is_symlink()]
            assert len(hits) == 1 and sha(hits[0]) == digest, name
            found[name] = digest
        r['frozen_app_members'] = dict(app=str(a.app), members=found, byte_identical_to_signed_pins=True)
    r.update(status='PASS_Q15_OFFLINE_INTAKE_INTEGRITY', host=dict(os=platform.system(), arch=platform.machine()),
             gpg=subprocess.check_output([gpg, '--version'], text=True).splitlines()[0],
             timestamp_utc=datetime.now(timezone.utc).isoformat())
    subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--'], cwd=root, check=True)
    with a.report.open('x') as f: json.dump(r, f, indent=2); f.write('\n')
    print(r['status'])


if __name__ == '__main__':
    main()
