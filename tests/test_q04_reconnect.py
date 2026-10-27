"""Credential continuity is not implied by the same external PID and port."""
from pathlib import Path
import unittest
from unittest.mock import patch
from wam_regtest.external_recovery import ExternalCoreSession,ExternalRecoveryError


class ReconnectCredentialContracts(unittest.TestCase):
    def test_cookie_change_cannot_be_adopted_during_reconnect(self):
        spec={'pid':123,'rpc_port':18443,'datadir':str(Path.cwd()),
              'core_dir':str(Path.cwd()),'operator_consent':True}
        class Attachment:
            def __init__(self,auth):self._auth=auth;self.closed=False
            def close(self):self.closed=True
        first=Attachment('old-private-cookie');second=Attachment('new-private-cookie')
        with patch('wam_regtest.external_recovery.ExternalCoreAttachment',side_effect=[first,second]):
            session=ExternalCoreSession(authorize=lambda:spec)
            session._connect()
            with self.assertRaisesRegex(ExternalRecoveryError,'EXTERNAL_RECOVERY_CREDENTIAL_CHANGED'):
                session._connect(spec)
            self.assertTrue(second.closed)

    def test_changed_cookie_is_refused_before_endpoint_authentication(self):
        from wam_regtest import external_core as mod
        root=Path.cwd()
        instance=mod.ExternalCoreAttachment.__new__(mod.ExternalCoreAttachment)
        with patch.object(mod.ExternalCoreAttachment,'_verified_core_paths',return_value=(root/'wamd',root/'wam-cli',{})), \
             patch.object(mod.ExternalCoreAttachment,'_assert_process_image'), \
             patch.object(mod.ExternalCoreAttachment,'_load_auth',return_value='different-private-cookie'), \
             patch.object(mod.ExternalCoreAttachment,'_attest_endpoint') as attest, \
             patch.object(mod,'_metadata',return_value=(1,2,3,4,5,6,7,8)):
            with self.assertRaisesRegex(mod.ExternalAttachmentError,'EXTERNAL_ATTACHMENT_CREDENTIAL_CHANGED'):
                instance.__init__(pid=123,rpc_port=18443,datadir=root,core_dir=root,
                    operator_consent=True,_expected_credential_digest='a'*64)
            attest.assert_not_called()
            self.assertTrue(instance._closed)
            self.assertIsNone(instance._auth)
