"""Explicit experimental Linux source-build trust; never signed-release intake.

An operator supplies the independently reviewed manifest SHA-256. A writable
receipt, source revision string or environment variable alone authorizes nothing.
This is not fd-to-loader binding, production custody or a signed WAM release.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import re
import stat
import struct
import subprocess
import sys

WAM_REVISION = '82a1487fd86f7021b1b9fc1524d267fca126f7d4'
BITCOIN_REVISION = '32efe850438ef22e2de39e562af557872a402c31'
RANDOMX_REVISION = '102f8acf90a7649ada410de5499a7ec62e49e1da'
SOURCES = {'wam': WAM_REVISION, 'bitcoin': BITCOIN_REVISION, 'randomx': RANDOMX_REVISION}
SCHEMA = 'wam-linux-regtest-developer-core/v1'


class LinuxCoreError(ValueError):
    pass


def native():
    if sys.platform != 'linux' or platform.machine().lower() != 'x86_64':
        raise LinuxCoreError('LINUX_NATIVE_X86_64_REQUIRED')


def inspect_elf(data):
    """Inspect bytes without executing an ELF or trusting readelf's text."""
    if (type(data) is not bytes or len(data) < 64 or data[:7] != b'\x7fELF\x02\x01\x01'
            or struct.unpack_from('<H', data, 18)[0] != 62
            or struct.unpack_from('<H', data, 16)[0] not in (2, 3)):
        raise LinuxCoreError('LINUX_ELF_AMD64_DENIED')
    offset = struct.unpack_from('<Q', data, 32)[0]
    size, count = struct.unpack_from('<HH', data, 54)
    if (size != 56 or not 1 <= count <= 1024 or offset < 64
            or offset + size * count > len(data)):
        raise LinuxCoreError('LINUX_ELF_PROGRAM_HEADERS_DENIED')
    stacks, loaders = [], []
    for i in range(count):
        kind, flags, start, _, _, length, _, _ = struct.unpack_from('<IIQQQQQQ', data, offset+i*size)
        if start + length > len(data):
            raise LinuxCoreError('LINUX_ELF_SEGMENT_BOUNDS_DENIED')
        if kind == 0x6474e551:
            stacks.append(flags)
        if kind == 1 and flags & 3 == 3:
            raise LinuxCoreError('LINUX_ELF_WRITABLE_EXECUTABLE_DENIED')
        if kind == 3:
            raw = data[start:start+length]
            if not raw.endswith(b'\0') or b'\0' in raw[:-1]:
                raise LinuxCoreError('LINUX_ELF_LOADER_DENIED')
            loaders.append(raw[:-1].decode('ascii', errors='strict'))
    if stacks != [6]:
        raise LinuxCoreError('LINUX_GNU_STACK_MUST_BE_RW')
    if len(loaders) != 1 or loaders[0] not in (
            '/lib64/ld-linux-x86-64.so.2', '/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2'):
        raise LinuxCoreError('LINUX_ELF_SYSTEM_LOADER_REQUIRED')
    return {'architecture': 'ELF64-x86_64', 'gnu_stack': 'RW', 'interpreter': loaders[0]}


def _read_binary(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        before = os.fstat(descriptor)
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                or before.st_mode & 0o022 or not before.st_mode & 0o111
                or before.st_uid not in (0, os.geteuid())
                or not 64 <= before.st_size <= 512*1024*1024):
            raise LinuxCoreError('LINUX_BINARY_CUSTODY_DENIED')
        with os.fdopen(os.dup(descriptor), 'rb') as stream:
            data = stream.read(512*1024*1024+1)
        after = os.fstat(descriptor)
        if any(getattr(before, key) != getattr(after, key) for key in
               ('st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')):
            raise LinuxCoreError('LINUX_BINARY_CHANGED')
        return data
    finally:
        os.close(descriptor)


def _system_file(path):
    actual = Path(path).resolve(strict=True)
    info = actual.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise LinuxCoreError('LINUX_SYSTEM_LIBRARY_CUSTODY_DENIED')
    return {'path': str(actual), 'sha256': sha256(actual.read_bytes()).hexdigest()}


def library_identity(binary):
    """Only after static ELF and developer trust checks; no inherited LD_* env."""
    environment = {'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'}
    dynamic = subprocess.check_output(['/usr/bin/readelf', '-dW', str(binary)], env=environment, timeout=15, text=True)
    if '(RPATH)' in dynamic or '(RUNPATH)' in dynamic:
        raise LinuxCoreError('LINUX_DYNAMIC_SEARCH_PATH_DENIED')
    needed = re.findall(r'\(NEEDED\).*\[([^\]]+)\]', dynamic)
    if not needed or any(not re.fullmatch(r'[A-Za-z0-9_.+-]+', name) for name in needed):
        raise LinuxCoreError('LINUX_LIBRARY_NAME_DENIED')
    output = subprocess.check_output(['/usr/bin/ldd', str(binary)], env=environment, timeout=15, text=True)
    if 'not found' in output:
        raise LinuxCoreError('LINUX_LIBRARY_UNAVAILABLE')
    records = {}
    for line in output.splitlines():
        match = re.fullmatch(r'\s*([A-Za-z0-9_.+-]+) => (/[^\s]+) \(0x[0-9a-f]+\)\s*', line)
        if match:
            records[match[1]] = _system_file(match[2])
        elif not re.fullmatch(r'\s*(?:linux-vdso\.so\.1|/[^\s]+) \(0x[0-9a-f]+\)\s*', line):
            raise LinuxCoreError('LINUX_LIBRARY_REPLY_DENIED')
    if not set(needed).issubset(records):
        raise LinuxCoreError('LINUX_LIBRARY_CLOSURE_DENIED')
    return records


def build_manifest(directory, sources):
    native()
    if sources != SOURCES:
        raise LinuxCoreError('LINUX_SOURCE_REVISION_DENIED')
    files = {}
    for name in ('wamd', 'wam-cli'):
        payload = _read_binary(directory/name)
        elf = inspect_elf(payload)
        files[name] = {'sha256': sha256(payload).hexdigest(), 'elf': elf,
                       'loader': _system_file(elf['interpreter']), 'libraries': library_identity(directory/name)}
    return {'schema': SCHEMA, 'sources': SOURCES, 'platform': 'linux-x86_64',
            'policy': 'EXPERIMENTAL_SOURCE_BUILD_REGTEST_ONLY',
            'official_signed_release': False, 'mainnet_allowed': False,
            'process_loader_binding_qualified': False, 'files': files}


def verify(directory, manifest_sha256, *, authorized=False):
    native()
    if authorized is not True or not re.fullmatch(r'[0-9a-f]{64}', manifest_sha256 or ''):
        raise LinuxCoreError('LINUX_DEVELOPER_MANIFEST_APPROVAL_REQUIRED')
    if not directory.is_absolute() or directory.is_symlink():
        raise LinuxCoreError('LINUX_CORE_DIRECTORY_DENIED')
    from .linux_private_storage import _walk
    held=_walk(directory,private=False)
    os.close(held)
    path = directory/'DEVELOPER_CORE_MANIFEST.json'
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or not 1 <= info.st_size <= 65536
                or info.st_uid not in (0,os.geteuid()) or info.st_mode&0o022):
            raise LinuxCoreError('LINUX_MANIFEST_SHAPE_DENIED')
        raw = os.read(fd, 65537)
    finally:
        os.close(fd)
    if sha256(raw).hexdigest() != manifest_sha256:
        raise LinuxCoreError('LINUX_MANIFEST_APPROVED_HASH_DENIED')
    record = json.loads(raw)
    if (record.get('schema') != SCHEMA or record.get('sources') != SOURCES
            or record.get('platform') != 'linux-x86_64'
            or record.get('policy') != 'EXPERIMENTAL_SOURCE_BUILD_REGTEST_ONLY'
            or record.get('official_signed_release') is not False
            or record.get('mainnet_allowed') is not False
            or record.get('process_loader_binding_qualified') is not False
            or set(record.get('files', {})) != {'wamd', 'wam-cli'}):
        raise LinuxCoreError('LINUX_DEVELOPER_POLICY_DENIED')
    for name, expected in record['files'].items():
        payload = _read_binary(directory/name)
        if sha256(payload).hexdigest() != expected['sha256']:
            raise LinuxCoreError('LINUX_BINARY_APPROVED_HASH_DENIED')
        elf = inspect_elf(payload)
        if (elf != expected['elf'] or _system_file(elf['interpreter']) != expected['loader']
                or library_identity(directory/name) != expected['libraries']):
            raise LinuxCoreError('LINUX_LOADER_LIBRARY_IDENTITY_DENIED')
    return directory/'wamd', directory/'wam-cli', record
