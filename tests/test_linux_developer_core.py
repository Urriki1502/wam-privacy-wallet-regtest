"""Negative ELF contracts; synthetic byte fixtures are NOT real Core E2E."""
import os
from pathlib import Path
import struct
import sys
import unittest
from wam_regtest.linux_developer_core import inspect_elf,LinuxCoreError,verify


def elf(flags=6):
    loader=b'/lib64/ld-linux-x86-64.so.2\0'
    data=bytearray(64+112+len(loader))
    data[:7]=b'\x7fELF\x02\x01\x01'
    struct.pack_into('<HHI',data,16,3,62,1)
    struct.pack_into('<Q',data,32,64)
    struct.pack_into('<HHH',data,52,64,56,2)
    struct.pack_into('<IIQQQQQQ',data,64,0x6474e551,flags,0,0,0,0,0,16)
    struct.pack_into('<IIQQQQQQ',data,120,3,4,176,0,0,len(loader),len(loader),1)
    data[176:]=loader
    return data


class LinuxCoreContracts(unittest.TestCase):
    def test_rw_stack_and_exact_architecture_required(self):
        self.assertEqual(inspect_elf(bytes(elf()))['gnu_stack'],'RW')
        for flags in (0,4,5,7):
            with self.assertRaisesRegex(LinuxCoreError,'GNU_STACK'):inspect_elf(bytes(elf(flags)))
        data=elf();struct.pack_into('<H',data,18,183)
        with self.assertRaises(LinuxCoreError):inspect_elf(bytes(data))
    def test_missing_stack_and_out_of_bounds_headers_deny(self):
        data=elf();struct.pack_into('<I',data,64,0)
        with self.assertRaises(LinuxCoreError):inspect_elf(bytes(data))
        for cut in (0,63,100,175):
            with self.assertRaises(LinuxCoreError):inspect_elf(bytes(elf()[:cut]))
    def test_foreign_interpreter_denies_before_execution(self):
        data=elf();data[176]=ord('x')
        with self.assertRaisesRegex(LinuxCoreError,'LOADER'):inspect_elf(bytes(data))
    def test_writable_executable_segment_denied(self):
        data=elf();struct.pack_into('<II',data,120,1,7)
        with self.assertRaisesRegex(LinuxCoreError,'WRITABLE_EXECUTABLE'):inspect_elf(bytes(data))
    def test_no_ambient_developer_authorization(self):
        with self.assertRaises(LinuxCoreError):verify(Path('/nonexistent'),None)
        with self.assertRaises(LinuxCoreError):verify(Path('/nonexistent'),'0'*64,authorized=False)
    @unittest.skipUnless(sys.platform=='linux' and os.uname().machine=='x86_64','native Linux ELF only')
    def test_actual_system_elf_has_no_executable_stack(self):
        self.assertEqual(inspect_elf(Path('/usr/bin/true').read_bytes())['architecture'],'ELF64-x86_64')
