"""Native private Core config contracts; real signing is tested separately."""
from pathlib import Path
import os,sys,tempfile,unittest
from wam_regtest import windows_private_storage as store
from wam_regtest.windows_core_transport import write_new,read_private,local_rpc_port,WindowsCoreTransportError
from wam_regtest.windows_core_regtest_smoke import _config
from wam_regtest.network_policy import NetworkPolicyError

@unittest.skipUnless(sys.platform=='win32','Native Windows custody only')
class NativePrivateCoreContracts(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='wam-private-core-');self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'private';store.create_private_directory(self.path)
    def test_config_owner_only_nonreplacing_and_numeric_local_profile(self):
        _config(self.path,18443,18444)
        raw=read_private(self.path,'wam.conf')
        self.assertEqual(local_rpc_port(self.path),18443)
        with self.assertRaises(WindowsCoreTransportError):write_new(self.path,'wam.conf',b'replacement')
        self.assertEqual(read_private(self.path,'wam.conf'),raw)
        (self.path/'wam.conf').write_bytes(raw+b'proxy=127.0.0.1:9050\n')
        with self.assertRaises(NetworkPolicyError):local_rpc_port(self.path)
    def test_default_acl_file_and_hardlink_denied(self):
        (self.path/'wam.conf').write_bytes(b'not-native-private')
        with self.assertRaises(store.WindowsCustodyError):read_private(self.path,'wam.conf')
        (self.path/'wam.conf').unlink()
        _config(self.path,18443,18444)
        os.link(self.path/'wam.conf',self.path/'alias')
        with self.assertRaises(store.WindowsCustodyError):read_private(self.path,'wam.conf')
    def test_no_arbitrary_plaintext_file_names_or_oversized_config(self):
        for name in ('keys.sqlite','../../escape','wam.conf:stream'):
            with self.assertRaises(WindowsCoreTransportError):write_new(self.path,name,b'not-authorized')
        with self.assertRaises(WindowsCoreTransportError):write_new(self.path,'wam.conf',b'x'*4097)
