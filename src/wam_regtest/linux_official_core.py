"""Official signed v0.1.13 Linux identity, separate from developer policy.

Member pins come from independent signed-archive intake, never a supplied
receipt. Ubuntu24.04 loader closure reviewed from native run 42060782393;
any library update requires review/requalification. Root witness stays separate.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
from .linux_developer_core import native, inspect_elf, _read_binary, _system_file, library_identity, LinuxCoreError
from .official_core_v013 import MEMBERS, SUMS_SHA256, SIGNATURE_SHA256

MANIFEST_NAME='LINUX_OFFICIAL_CORE_MANIFEST.json'
MANIFEST_SHA256='4052c4a75dee853f5a27c2fb1869aee841a075ed8d6187b90a9d1c06a88cf3c2'
EXPECTED={'schema': 'wam-linux-official-signed-core/v1', 'sources': {'wam': 'b3fb899ddb1ceab7e9b3b12ccd034ad1b4be8186'}, 'platform': 'linux-x86_64', 'policy': 'OFFICIAL_SIGNED_V013_REGTEST_ONLY', 'official_signed_release': True, 'mainnet_allowed': False, 'process_loader_binding_qualified': False, 'files': {'wam-cli': {'elf': {'architecture': 'ELF64-x86_64', 'gnu_stack': 'RW', 'interpreter': '/lib64/ld-linux-x86-64.so.2'}, 'libraries': {'libc.so.6': {'path': '/usr/lib/x86_64-linux-gnu/libc.so.6', 'sha256': '3a15d66867d83762c7f2f1e37359cb8f6c5743edb369c65285cb0b1c4f7498bf'}, 'libgcc_s.so.1': {'path': '/usr/lib/x86_64-linux-gnu/libgcc_s.so.1', 'sha256': 'd93224d2b0dab4247598be683adca02f5cf00586f99c187579cd7e92058fb7cb'}, 'libm.so.6': {'path': '/usr/lib/x86_64-linux-gnu/libm.so.6', 'sha256': 'fce00b6f25f459cf4ae0b7fae4257909a1a8a86f9149e7c029a5d617baf1ccd0'}, 'libstdc++.so.6': {'path': '/usr/lib/x86_64-linux-gnu/libstdc++.so.6.0.33', 'sha256': '1fd75fe70354a416d75aef22bcae68c47bd25d20e2d0568c30b1a9838cf62f11'}}, 'loader': {'path': '/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2', 'sha256': 'c20a2dc8917c755f02b94049356320fe1f62ac7d9f8994731f807d9df39302da'}, 'sha256': 'd99fc90e3aa4233979056d9981a388360e5d7ff77090d00b9bc37191a2425300'}, 'wamd': {'elf': {'architecture': 'ELF64-x86_64', 'gnu_stack': 'RW', 'interpreter': '/lib64/ld-linux-x86-64.so.2'}, 'libraries': {'libc.so.6': {'path': '/usr/lib/x86_64-linux-gnu/libc.so.6', 'sha256': '3a15d66867d83762c7f2f1e37359cb8f6c5743edb369c65285cb0b1c4f7498bf'}, 'libgcc_s.so.1': {'path': '/usr/lib/x86_64-linux-gnu/libgcc_s.so.1', 'sha256': 'd93224d2b0dab4247598be683adca02f5cf00586f99c187579cd7e92058fb7cb'}, 'libm.so.6': {'path': '/usr/lib/x86_64-linux-gnu/libm.so.6', 'sha256': 'fce00b6f25f459cf4ae0b7fae4257909a1a8a86f9149e7c029a5d617baf1ccd0'}, 'libstdc++.so.6': {'path': '/usr/lib/x86_64-linux-gnu/libstdc++.so.6.0.33', 'sha256': '1fd75fe70354a416d75aef22bcae68c47bd25d20e2d0568c30b1a9838cf62f11'}}, 'loader': {'path': '/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2', 'sha256': 'c20a2dc8917c755f02b94049356320fe1f62ac7d9f8994731f807d9df39302da'}, 'sha256': 'a3e3bf810e74824e3739fd4cbd1a45037cae997056b8c978c4dc1a61d674f0c7'}}}


def manifest_bytes():
    raw=(json.dumps(EXPECTED,sort_keys=True,indent=2)+'\n').encode('ascii')
    if sha256(raw).hexdigest()!=MANIFEST_SHA256:raise LinuxCoreError('LINUX_OFFICIAL_MANIFEST_SOURCE_DENIED')
    return raw


def _public(path,limit):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK)
    try:
        before=os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_uid not in (0,os.geteuid())
            or before.st_mode&0o022 or not 1<=before.st_size<=limit):raise LinuxCoreError('LINUX_OFFICIAL_METADATA_CUSTODY_DENIED')
        raw=os.read(fd,limit+1);after=os.fstat(fd)
        if len(raw)!=before.st_size or any(getattr(before,k)!=getattr(after,k) for k in ('st_dev','st_ino','st_mode','st_uid','st_nlink','st_size','st_mtime_ns','st_ctime_ns')):
            raise LinuxCoreError('LINUX_OFFICIAL_METADATA_CHANGED')
        return raw
    finally:os.close(fd)


def verify(directory,manifest_sha256,*,authorized=False):
    native()
    if authorized is not True or manifest_sha256!=MANIFEST_SHA256:raise LinuxCoreError('LINUX_OFFICIAL_MANIFEST_APPROVAL_REQUIRED')
    if not directory.is_absolute() or directory.is_symlink():raise LinuxCoreError('LINUX_CORE_DIRECTORY_DENIED')
    from .linux_private_storage import _walk
    fd=_walk(directory,private=False);os.close(fd)
    raw=_public(directory/MANIFEST_NAME,65536)
    if sha256(raw).hexdigest()!=MANIFEST_SHA256 or json.loads(raw)!=EXPECTED:raise LinuxCoreError('LINUX_OFFICIAL_MANIFEST_PIN_DENIED')
    # These exact signed public bytes were authenticated at intake. Runtime
    # never needs GnuPG, network access or mutable metadata as trust authority.
    for name,pin in (('SHA256SUMS',SUMS_SHA256),('SHA256SUMS.asc',SIGNATURE_SHA256),('SIGNING-KEY.asc','842d9419593efc8fe0a5f45feaeab86710c03b27b3e2416a2dc9205fe506ee63')):
        if sha256(_public(directory/name,32768)).hexdigest()!=pin:raise LinuxCoreError('LINUX_OFFICIAL_SIGNATURE_BYTES_DENIED')
    for name,pin in MEMBERS['linux-x86_64'].items():
        payload=_read_binary(directory/name);expected=EXPECTED['files'][name]
        if sha256(payload).hexdigest()!=pin:raise LinuxCoreError('LINUX_BINARY_APPROVED_HASH_DENIED')
        elf=inspect_elf(payload)
        if elf!=expected['elf'] or _system_file(elf['interpreter'])!=expected['loader'] or library_identity(directory/name)!=expected['libraries']:
            raise LinuxCoreError('LINUX_LOADER_LIBRARY_IDENTITY_DENIED')
    return directory/'wamd',directory/'wam-cli',EXPECTED


def stage(destination):
    from .official_core_v013 import stage_tar
    stage_tar('linux-x86_64',destination)
    (destination/MANIFEST_NAME).write_bytes(manifest_bytes())
    (destination/'manifest.sha256').write_text(MANIFEST_SHA256+'\n')
    verify(destination,MANIFEST_SHA256,authorized=True)
