"""LF-only SHA256SUMS.txt. Runs on Windows with the other test_windows_* cases."""
from hashlib import sha256
from pathlib import Path
import subprocess
import tempfile
import unittest

from wam_regtest.release_candidate import verify_portable_sha256sums, write_portable_sha256sums


class PortableSha256SumsTests(unittest.TestCase):
    def test_binary_write_is_lf_only_and_checks(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            payload = root / 'payload.bin'
            payload.write_bytes(b'abc')
            write_portable_sha256sums(root)
            raw = (root / 'SHA256SUMS.txt').read_bytes()
            self.assertNotIn(b'\r', raw)
            self.assertTrue(raw.endswith(b'\n'))
            self.assertNotIn(b'SHA256SUMS.txt', raw)
            seen = verify_portable_sha256sums(root)
            self.assertEqual(seen, {'payload.bin'})
            self.assertEqual(sha256(b'abc').hexdigest(), raw.split(b'  ')[0].decode())
            if subprocess.call(['sha256sum', '--version'], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL) == 0:
                subprocess.run(['sha256sum', '-c', 'SHA256SUMS.txt'], cwd=root, check=True)

    def test_crlf_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'payload.bin').write_bytes(b'abc')
            digest = sha256(b'abc').hexdigest()
            (root / 'SHA256SUMS.txt').write_bytes(
                (digest + '  payload.bin\r\n').encode('ascii'))
            with self.assertRaises(ValueError):
                verify_portable_sha256sums(root)


if __name__ == '__main__':
    unittest.main()
