"""Independent official v0.1.13 pins. Intake is not wallet activation.

Values observed from freshly downloaded, GPG-authenticated archives on 2026-11-05.
No mutable receipt can authorize different executable bytes.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import struct
import tarfile
import tempfile

VERSION = 'v0.1.13'
SOURCE = 'b3fb899ddb1ceab7e9b3b12ccd034ad1b4be8186'
SUMS_SHA256 = 'fab37640d6860fd28cadd547ca4e3312f60ec1441df4574029ff2cf6536c3907'
SIGNATURE_SHA256 = '2014ce6a2fceb446448219ed16e1b923f457582cbeaf05bb57f62258ca9c1a73'
ARCHIVES = {
 'linux-x86_64': ('wam-coin-v0.1.13-x86_64-linux-gnu.tar.gz', 13163409, '1adb703f9c881f1ce20ee1d085c7d0d07395b61751faa02a532f947bb97d594a'),
 'windows-x64': ('wam-coin-v0.1.13-x86_64-w64-mingw32.zip', 16333094, 'db6bcb58e909a72a69ab7bb74a95ab3837298c12fd847dc83fdb37fca10732b4'),
 'macos-arm64': ('wam-coin-v0.1.13-arm64-apple-darwin.tar.gz', 11133091, '2e6d4cb34e4e1ca800db82591295ede775e5ba1769fec737db70ebaa38ab5894'),
}
MEMBERS = {
 'linux-x86_64': {'wamd':'a3e3bf810e74824e3739fd4cbd1a45037cae997056b8c978c4dc1a61d674f0c7','wam-cli':'d99fc90e3aa4233979056d9981a388360e5d7ff77090d00b9bc37191a2425300'},
 'windows-x64': {'wamd.exe':'5fbeb6e07a83b337209edf0efbe342201bc3bf2e0c113dea8fdf7bf0e07d49e3','wam-cli.exe':'a6171ed6cddfeea58b9a6a8b722f2c07c0d332f0f1a7263f52193e4ef9f6f326'},
 'macos-arm64': {'wamd':'fe04a61f17eb8047f1d2a537ebcb61b45cbde14c491bc332d2a2ab7ee18237ba','wam-cli':'2b19fdac692cbed5810b6fa9663ac89f25ab8f346da84c5fd13bf2b8535e3e19'},
}


def stage_tar(platform, destination, gpg_exe="gpg"):
    """New private directory only; no extraction of unrelated binaries or links."""
    from .release import _download_exact, _validate_signed_sums, ReleaseError, FINGERPRINT
    if platform not in ('linux-x86_64','macos-arm64') or not destination.is_absolute() or destination.exists() or destination.is_symlink():
        raise ReleaseError('V013_NEW_TAR_DESTINATION_REQUIRED')
    if any(parent.is_symlink() for parent in destination.parents):
        raise ReleaseError('V013_DESTINATION_ANCESTOR_LINK_DENIED')
    asset,size,digest=ARCHIVES[platform]
    with tempfile.TemporaryDirectory(prefix='wam-official-v013-') as temp:
        root=Path(temp);root.chmod(0o700)
        for remote,name,bound in [('/SIGNING-KEY.asc','SIGNING-KEY.asc',32768),
            ('/downloads/v0.1.13/SHA256SUMS','SHA256SUMS',963),
            ('/downloads/v0.1.13/SHA256SUMS.asc','SHA256SUMS.asc',833),
            ('/downloads/v0.1.13/'+asset,asset,size)]:
            _download_exact(remote,bound,root/name)
        if sha256((root/'SHA256SUMS').read_bytes()).hexdigest()!=SUMS_SHA256 or sha256((root/'SHA256SUMS.asc').read_bytes()).hexdigest()!=SIGNATURE_SHA256:
            raise ReleaseError('V013_SIGNED_MANIFEST_PIN_DENIED')
        if _validate_signed_sums(gpg_exe,root,asset)!=digest or (root/asset).stat().st_size!=size or sha256((root/asset).read_bytes()).hexdigest()!=digest:
            raise ReleaseError('V013_SIGNED_ARCHIVE_PIN_DENIED')
        payloads={};seen=set();total=0
        with tarfile.open(root/asset,'r:gz') as tar:
            entries=tar.getmembers()
            if not 1<=len(entries)<=64:raise ReleaseError('V013_ARCHIVE_COUNT_DENIED')
            for entry in entries:
                n=entry.name.rstrip('/');total+=entry.size
                if (n.casefold() in seen or '\\' in n or ':' in n or n.split('/')[0]!='wam-coin-v0.1.13'
                    or any(b in ('','.','..') for b in n.split('/')) or not (entry.isfile() or entry.isdir())
                    or not 0<=entry.size<=128*1024*1024 or total>512*1024*1024):
                    raise ReleaseError('V013_ARCHIVE_MEMBER_DENIED')
                seen.add(n.casefold())
                for name in MEMBERS[platform]:
                    if n=='wam-coin-v0.1.13/bin/'+name:
                        if not entry.isfile():raise ReleaseError('V013_BINARY_TYPE_DENIED')
                        with tar.extractfile(entry) as stream: b=stream.read(128*1024*1024+1)
                        if len(b)!=entry.size or sha256(b).hexdigest()!=MEMBERS[platform][name]:raise ReleaseError('V013_BINARY_PIN_DENIED')
                        if platform=='linux-x86_64':
                            from .linux_developer_core import inspect_elf
                            inspect_elf(b)
                        elif len(b)<32 or struct.unpack('<IiiI',b[:16])[:2]!=(0xFEEDFACF,0x0100000C) or struct.unpack_from('<I',b,12)[0]!=2:
                            raise ReleaseError('V013_MACHO_ARM64_DENIED')
                        payloads[name]=b
        if set(payloads)!=set(MEMBERS[platform]):raise ReleaseError('V013_BINARY_MISSING')
        destination.mkdir(mode=0o700)
        for name,b in payloads.items():
            with (destination/name).open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
            (destination/name).chmod(0o700)
        receipt={'tag':VERSION,'platform':platform,'archive':asset,'archive_sha256':digest,
            'wamd_sha256':MEMBERS[platform]['wamd'],'wam_cli_sha256':MEMBERS[platform]['wam-cli'],
            'publisher_fingerprint':FINGERPRINT,'signed_archive_verified':True,
            'loader_process_binding_qualified':False,'real_wsp_e2e_qualified':False,'mainnet_allowed':False}
        (destination/'receipt.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
        for name in ('SIGNING-KEY.asc','SHA256SUMS','SHA256SUMS.asc'):shutil.copyfile(root/name,destination/name)
        return receipt
