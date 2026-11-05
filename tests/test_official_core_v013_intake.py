"""Supply-chain failure tests; fixture authority never qualifies native execution."""
from hashlib import sha256
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from wam_regtest import official_core_v013 as intake
from wam_regtest.release import ReleaseError


class IntakeRefusal(unittest.TestCase):
    def fixture(self, name):
        buf=io.BytesIO()
        with tarfile.open(fileobj=buf,mode='w:gz') as tar:
            m=tarfile.TarInfo(name);m.size=1;tar.addfile(m,io.BytesIO(b'x'))
        return buf.getvalue()

    def run_fixture(self,archive,*,signed=None,manifest=b'manifest'):
        with tempfile.TemporaryDirectory() as temp:
            dest=Path(temp)/'new'
            digest=sha256(archive).hexdigest()
            def download(remote,maximum,target):
                target.write_bytes(archive if target.name=='fixture.tar.gz' else manifest if target.name=='SHA256SUMS' else b'sig' if target.name.endswith('.asc') else b'key')
            with patch.dict(intake.ARCHIVES,{'linux-x86_64':('fixture.tar.gz',len(archive),digest)}),patch.object(intake,'SUMS_SHA256',sha256(b'manifest').hexdigest()),patch.object(intake,'SIGNATURE_SHA256',sha256(b'sig').hexdigest()),patch('wam_regtest.release._download_exact',side_effect=download),patch('wam_regtest.release._validate_signed_sums',return_value=signed or digest):
                with self.assertRaises(ReleaseError):intake.stage_tar('linux-x86_64',dest)
            self.assertFalse(dest.exists())

    def test_wrong_signed_archive_denies_before_output(self):
        self.run_fixture(self.fixture('wam-coin-v0.1.13/bin/wamd'),signed='0'*64)

    def test_changed_manifest_denies_before_output(self):
        self.run_fixture(self.fixture('wam-coin-v0.1.13/bin/wamd'),manifest=b'changed')

    def test_traversal_and_wrong_member_refuse(self):
        for name in ('wam-coin-v0.1.13/../outside','/wam-coin-v0.1.13/bin/wamd','wam-coin-v0.1.13/bin/wamd'):
            with self.subTest(name=name):self.run_fixture(self.fixture(name))

    def test_existing_destination_never_modified(self):
        with tempfile.TemporaryDirectory() as temp:
            dest=Path(temp);(dest/'preserve').write_bytes(b'original')
            with self.assertRaises(ReleaseError):intake.stage_tar('linux-x86_64',dest)
            self.assertEqual((dest/'preserve').read_bytes(),b'original')


class SignerStatusRefusal(unittest.TestCase):
    def test_revoked_expired_and_error_status_deny_even_with_validsig(self):
        from wam_regtest.release import _validate_signed_sums, FINGERPRINT
        for status in ('REVKEYSIG','EXPKEYSIG','EXPSIG','KEYEXPIRED','FAILURE','ERROR'):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as t:
                p=Path(t)
                key='pub:-:4096:1:KEY:0:0::::::\nfpr:::::::::'+FINGERPRINT+':\n'
                checks='[GNUPG:] VALIDSIG '+FINGERPRINT+' 2026-10-31 0\n[GNUPG:] '+status+' fixture\n'
                with patch('wam_regtest.release._gpg',side_effect=[(0,key),(0,''),(0,checks)]):
                    with self.assertRaisesRegex(ReleaseError,'RELEASE_SIGNATURE_DENIED'):
                        _validate_signed_sums('gpg',p,'fixture.tar.gz')
