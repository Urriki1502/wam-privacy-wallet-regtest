"""Unit tests for Q04 external Core attachment boundary."""
import unittest
from pathlib import Path

from wam_regtest.external_core import ExternalCoreAttachment, ExternalAttachmentError


class ExternalAttachmentContracts(unittest.TestCase):
    def test_consent_required(self):
        with self.assertRaises(ExternalAttachmentError) as ctx:
            ExternalCoreAttachment(
                pid=1234, rpc_port=18443, datadir=Path('/tmp/wam'),
                core_dir=Path('/tmp/core'), operator_consent=False)
        self.assertEqual(ctx.exception.args[0], 'EXTERNAL_ATTACHMENT_CONSENT_REQUIRED')

    def test_pid_must_be_positive(self):
        with self.assertRaises(ExternalAttachmentError):
            ExternalCoreAttachment(
                pid=0, rpc_port=18443, datadir=Path('/tmp/wam'),
                core_dir=Path('/tmp/core'), operator_consent=True)

    def test_port_must_be_in_range(self):
        with self.assertRaises(ExternalAttachmentError):
            ExternalCoreAttachment(
                pid=1234, rpc_port=80, datadir=Path('/tmp/wam'),
                core_dir=Path('/tmp/core'), operator_consent=True)

    def test_datadir_must_be_absolute(self):
        with self.assertRaises(ExternalAttachmentError):
            ExternalCoreAttachment(
                pid=1234, rpc_port=18443, datadir=Path('relative'),
                core_dir=Path('/tmp/core'), operator_consent=True)

    def test_core_dir_must_be_absolute(self):
        with self.assertRaises(ExternalAttachmentError):
            ExternalCoreAttachment(
                pid=1234, rpc_port=18443, datadir=Path('/tmp/wam'),
                core_dir=Path('relative'), operator_consent=True)

    def test_read_scope_denies_writes(self):
        # Patch Core verification so we can exercise the read() scope boundary.
        import sys
        from unittest.mock import patch
        mod = sys.modules['wam_regtest.external_core']
        with patch.object(mod.ExternalCoreAttachment, '_verified_core_paths',
                          return_value=(Path('/tmp/wamd'), Path('/tmp/wam-cli'), {})), \
             patch.object(mod.ExternalCoreAttachment, '_assert_process_image'), \
             patch.object(mod.ExternalCoreAttachment, '_load_auth', return_value='dXNlcjpwYXNz'), \
             patch.object(mod.ExternalCoreAttachment, '_attest_endpoint'), \
             patch.object(mod, '_metadata', return_value=(1, 2, 3, 4, 5, 6, 7, 8)):
            attachment = ExternalCoreAttachment(
                pid=1234, rpc_port=18443, datadir=Path('/tmp/wam'),
                core_dir=Path('/tmp/core'), operator_consent=True)
            with self.assertRaises(ExternalAttachmentError) as ctx:
                attachment.read('sendrawtransaction', ['deadbeef'])
            self.assertEqual(ctx.exception.args[0], 'EXTERNAL_ATTACHMENT_READ_SCOPE_DENIED')


if __name__ == '__main__':
    unittest.main()
