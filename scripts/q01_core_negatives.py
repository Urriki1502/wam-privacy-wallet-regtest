"""Native checksum refusal against copies of the genuine pinned Core pair.

Never launch Core, open a wallet, touch an anchor, or mutate the input directory.
The genuine Core chain acceptance remains a separate mandatory workflow step.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile

LINUX_MANIFEST = 'e77a5745263b8fdbcffdb282af22800b6f7805f033c09f00738e997150a0f806'


def qualify(directory):
    if sys.platform == 'win32':
        from wam_regtest.windows_release_preflight import BINARY_SHA256
        from wam_regtest.windows_core_transport import verified_core_paths as verify, write_new, WindowsCoreTransportError
        from wam_regtest.windows_private_storage import create_private_directory
        pins = BINARY_SHA256
        metadata_name = 'receipt.json'
        error = WindowsCoreTransportError
    elif sys.platform == 'darwin':
        from wam_regtest.core import verified_core_paths as verify, CoreSmokeError
        from wam_regtest.release import ARCHIVES, CLI_SHA256
        pins = {'wamd': ARCHIVES['macos-arm64'][1], 'wam-cli': CLI_SHA256['macos-arm64']}
        metadata_name = 'receipt.json'
        error = CoreSmokeError
    elif sys.platform == 'linux':
        from wam_regtest.linux_developer_core import verify as linux_verify, LinuxCoreError
        pins = {'wamd': 'ccc9f0f1d299a1e98a49ff83859aa03e994e83e6ea4b7cd60c327eb1e0e8e4d6',
                'wam-cli': 'ada9dabd56d0859b9d64c0b20a05c33cb039b2573f75088443b45c35d5379652'}
        verify = lambda path: linux_verify(path, LINUX_MANIFEST, authorized=True)
        metadata_name = 'DEVELOPER_CORE_MANIFEST.json'
        error = LinuxCoreError
    else:
        raise ValueError('Q01_NATIVE_PLATFORM_REQUIRED')
    directory = directory.resolve(strict=True)
    # Authenticate both ORIGINAL binaries independently before reading fixtures.
    raw = {name: (directory / name).read_bytes() for name in pins}
    assert {name: sha256(value).hexdigest() for name, value in raw.items()} == pins
    metadata = (directory / metadata_name).read_bytes()
    results = []
    with tempfile.TemporaryDirectory(prefix='wam-q01-public-core-negative-') as temporary:
        for index, changed in enumerate((None, *pins, 'missing-cli')):
            target = Path(temporary).resolve() / str(index)
            if sys.platform == 'win32':
                create_private_directory(target)
                put = lambda name, value: write_new(target, name, value)
            else:
                target.mkdir(mode=0o700)
                put = lambda name, value: (target / name).write_bytes(value)
            put(metadata_name, metadata)
            for name, value in raw.items():
                if changed == 'missing-cli' and name == list(pins)[1]:
                    continue
                if name == changed:
                    value = value[:-1] + bytes([value[-1] ^ 1])
                put(name, value)
                if sys.platform != 'win32':
                    (target / name).chmod(0o700)
            if changed is None:
                verify(target)
                results.append({'case': 'genuine-pair-private-copy', 'status': 'PASS'})
            else:
                try:
                    verify(target)
                except FileNotFoundError as missing:
                    # Linux's existing verifier exposes the OS missing-file
                    # refusal. Accept ONLY the deliberately absent CLI, never
                    # a missing loader/tool/library or a different failure.
                    expected = target / list(pins)[1]
                    if (changed != 'missing-cli' or Path(missing.filename) != expected
                            or expected.exists() or expected.is_symlink()):
                        raise
                    results.append({'case': 'refuse-missing-cli', 'status': 'PASS',
                                    'reason_code': 'Q01_CORE_REQUIRED_CLI_MISSING'})
                except error as refusal:
                    results.append({'case': 'refuse-' + changed, 'status': 'PASS',
                                    'reason_code': str(refusal)})
                else:
                    raise AssertionError('Q01_CORE_NEGATIVE_ACCEPTED')
    assert {name: sha256((directory / name).read_bytes()).hexdigest() for name in pins} == pins
    root = Path(__file__).resolve().parents[1]
    return {'schema': 'wam-q01-real-core-input-negatives/v1', 'layer': 'SOURCE',
        'source_checkout_sha': subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip(),
        'timestamp_utc': datetime.now(timezone.utc).isoformat(), 'platform': sys.platform,
        'core_version': 'v0.1.11', 'core_sha256': pins,
        'core_trust': 'reviewed-developer-source-build' if sys.platform == 'linux' else 'official-signed-v0.1.11',
        'original_pair_unchanged': True, 'core_process_started': False,
        'cases': results, 'core_e2e_qualified': False, 'frozen_qualified': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--core-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    receipt = qualify(args.core_dir)
    with args.output.open('x') as output:
        json.dump(receipt, output, sort_keys=True, indent=2)
        output.write('\n')
    print('Q01_GENUINE_CORE_PAIR_CHECKSUM_AND_MISSING_FILE_REFUSALS_PASS')


if __name__ == '__main__':
    main()
