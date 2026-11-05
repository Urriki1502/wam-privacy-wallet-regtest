"""Copy authentic third-party license material into a package stage.

PySide6 6.12.0 wheels publish a License field and no license file. The GNU
texts staged here are the unmodified files in third_party/gnu, not a summary.
This module does not decide that the result is a complete legal review.
"""
import argparse
import importlib.metadata
from pathlib import Path
import shutil


GNU_FILES = ('lgpl-3.0.txt', 'gpl-3.0.txt', 'gpl-2.0.txt', 'PROVENANCE.txt')
QT_DISTRIBUTIONS = ('PySide6', 'PySide6_Essentials', 'PySide6_Addons', 'shiboken6')
OTHER_DISTRIBUTIONS = ('coincurve', 'cryptography', 'mnemonic', 'qrcode', 'cffi', 'Pillow')


def _root():
    return Path(__file__).resolve().parents[2]


def stage_distribution_notices(output, *, qt):
    destination = Path(output)
    if destination.exists():
        raise ValueError('DISTRIBUTION_NOTICES_DESTINATION_EXISTS')
    destination.mkdir()
    gnu = _root() / 'third_party' / 'gnu'
    for name in GNU_FILES:
        source = gnu / name
        data = source.read_bytes()
        if b'\r' in data or not data.startswith(b' '):
            if name != 'PROVENANCE.txt':
                raise ValueError('DISTRIBUTION_NOTICES_GNU_TEXT_DENIED')
        if name != 'PROVENANCE.txt' and b'GNU' not in data[:80]:
            raise ValueError('DISTRIBUTION_NOTICES_GNU_TEXT_DENIED')
        shutil.copyfile(source, destination / name)
    names = list(QT_DISTRIBUTIONS if qt else ()) + list(OTHER_DISTRIBUTIONS)
    found = []
    for name in names:
        try:
            dist = importlib.metadata.distribution(name)
        except importlib.metadata.PackageNotFoundError:
            if name in QT_DISTRIBUTIONS:
                raise ValueError('DISTRIBUTION_NOTICES_QT_METADATA_MISSING')
            continue
        info = Path(dist._path)
        target = destination / (dist.metadata['Name'] + '-' + dist.version)
        target.mkdir()
        shutil.copyfile(info / 'METADATA', target / 'METADATA')
        for path in info.rglob('*'):
            if not path.is_file():
                continue
            label = path.name.upper()
            if any(token in label for token in ('LICENSE', 'COPYING', 'NOTICE')):
                shutil.copyfile(path, target / path.name)
        found.append(dist.metadata['Name'] + '==' + dist.version
                     + ' License=' + (dist.metadata.get('License') or ''))
    if qt and not any(item.startswith('PySide6==') for item in found):
        raise ValueError('DISTRIBUTION_NOTICES_QT_METADATA_MISSING')
    notice = destination / 'DISTRIBUTION_NOTICES.txt'
    body = (
        'Third-party notices for this REGTEST package.\n'
        'The GNU license files in this directory are the unmodified texts\n'
        'described by PROVENANCE.txt. Wheel METADATA is copied from the\n'
        'installed distribution. PySide6 6.12.0 metadata declares\n'
        'LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only and the wheel\n'
        'dist-info contains no license file of its own.\n'
        'Qt and Shiboken libraries are shipped as separate shared libraries.\n'
        'Corresponding sources are the public Qt for Python 6.12.0 release\n'
        'at https://pyside.org and https://download.qt.io.\n'
        'Including these files does not complete a legal review of the\n'
        'source offer, Qt trademarks, or GPL-only Qt modules.\n'
        '\n'
        'Installed distributions recorded at package time:\n'
        + '\n'.join(found) + '\n'
    )
    if '\r' in body:
        raise ValueError('DISTRIBUTION_NOTICES_CR_DENIED')
    with notice.open('wb') as stream:
        stream.write(body.encode('utf-8'))
    return destination


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--qt', action='store_true')
    args = parser.parse_args()
    stage_distribution_notices(args.output, qt=args.qt)
    print('DISTRIBUTION_NOTICES_STAGED')


if __name__ == '__main__':
    main()
