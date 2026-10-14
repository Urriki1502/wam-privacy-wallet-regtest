"""Profile denial contracts; actual network diagnostics remain real-Core E2E."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from wam_regtest.core import _write_private_config,_read_cli,CoreSmokeError
from wam_regtest.network_policy import local_rpc_port,NetworkPolicyError

class LocalNetworkContracts(unittest.TestCase):
    def test_generated_profile(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t).resolve(); _write_private_config(d,12345,12346)
            self.assertEqual(local_rpc_port(d),12345)
    def test_remote_proxy_include_duplicate_and_fallback_denied_before_cli(self):
        for text in ('rpcconnect=example.com','proxy=127.0.0.1:9050','includeconf=other.conf',
                     'rpcport=12345','connect=1','[main]','onion=127.0.0.1:9050'):
            with self.subTest(option=text.split('=')[0]),tempfile.TemporaryDirectory() as t:
                d=Path(t).resolve(); _write_private_config(d,12345,12346)
                with (d/'wam.conf').open('a') as f: f.write(text+'\n')
                with patch('wam_regtest.core.subprocess.run') as run:
                    with self.assertRaisesRegex(CoreSmokeError,'CORE_LOCAL_NETWORK_POLICY_DENIED'):
                        _read_cli(['/unknown-cli','-datadir='+str(d),'getblockcount'])
                    run.assert_not_called()
    def test_config_links_and_public_modes_denied(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t).resolve(); _write_private_config(d,12345,12346)
            os.chmod(d/'wam.conf',0o644)
            with self.assertRaises(NetworkPolicyError): local_rpc_port(d)
            os.chmod(d/'wam.conf',0o600)
            (d/'wam.conf').rename(d/'other.conf'); (d/'wam.conf').symlink_to('other.conf')
            with self.assertRaises(NetworkPolicyError): local_rpc_port(d)
