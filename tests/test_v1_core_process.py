"""Kernel output parser negatives; no fake Core acceptance."""
import unittest
from wam_regtest.core_process import _lsof_match,OwnedCoreBinding,CoreBindingError
from wam_regtest.json_rpc import ManagedReadRpc,RpcError

class OwnedEndpointContracts(unittest.TestCase):
    def test_exact_server_half_of_established_connection(self):
        data='p123\nf7\nn127.0.0.1:10001->127.0.0.1:20002\nTST=ESTABLISHED\nf8\nn127.0.0.1:10001->127.0.0.1:20003\nTST=ESTABLISHED\n'
        self.assertTrue(_lsof_match(data,123,10001,20002))
        for pid,server,client in [(124,10001,20002),(123,20002,10001),(123,1000,20002),(123,10001,2000)]:
            self.assertFalse(_lsof_match(data,pid,server,client))
        self.assertFalse(_lsof_match(data.replace('ESTABLISHED','LISTEN'),123,10001,20002))

    def test_process_scope_is_required_before_credentials_or_socket(self):
        from pathlib import Path
        with self.assertRaises(CoreBindingError):OwnedCoreBinding(None,Path('/missing'),Path('/missing'))
        with self.assertRaisesRegex(RpcError,'^RPC_MANAGED_PROCESS_REQUIRED$'):
            ManagedReadRpc(None,None,authorized_readonly=True)

    def test_t04_pair_metadata_is_stable_across_verified_core_hash(self):
        """UNIT fixture only; genuine Core E2E independently exercises binding."""
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        import subprocess
        import sys
        import os
        with TemporaryDirectory(prefix="t04-pair-fixture-") as temporary:
            core=Path(temporary).resolve(strict=True)
            suffix=".exe" if sys.platform=="win32" else ""
            node=core/("wamd"+suffix)
            cli=core/("wam-cli"+suffix)
            node.write_bytes(b"PUBLIC_TEST_DUMMY_CORE")
            cli.write_bytes(b"PUBLIC_TEST_DUMMY_CLI")
            directory=core/"disposable-chain"
            directory.mkdir()
            argv=[str(node),f"-datadir={directory}","-daemon=0"]
            class FakePopen:
                def __init__(self):
                    self.args=list(argv)
                    self.pid=12345
                def poll(self):return None
            receipt={"wamd_sha256":"a"*64,"wam_cli_sha256":"b"*64}
            with (patch("wam_regtest.core_process.subprocess.Popen",FakePopen),
                  patch("wam_regtest.core_process.verified_core_paths",
                        return_value=(node,cli,receipt)) as verified,
                  patch("wam_regtest.core_process._image",return_value=str(node))):
                bound=OwnedCoreBinding(FakePopen(),core,directory)
                verified.assert_called_once_with(core)
                self.assertEqual(bound._files[0][1],node.stat().st_ino)
                self.assertEqual(bound._files[1][1],cli.stat().st_ino)
                # Ongoing native image/file identity is inexpensive; no
                # repeated signed-byte hash in a normal read/RPC.
                with patch("wam_regtest.core_process.verified_core_paths",
                           side_effect=AssertionError("PER_RPC_REHASH_FORBIDDEN")):
                    bound._assert_image()

    def test_t04_replacement_during_hash_denies_before_image_or_rpc(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import patch,Mock
        import sys
        with TemporaryDirectory(prefix="t04-replace-fixture-") as temporary:
            core=Path(temporary).resolve(strict=True)
            suffix=".exe" if sys.platform=="win32" else ""
            node=core/("wamd"+suffix)
            cli=core/("wam-cli"+suffix)
            node.write_bytes(b"PUBLIC_NODE_FIXTURE")
            cli.write_bytes(b"PUBLIC_CLI_FIXTURE")
            directory=core/"disposable-chain"
            directory.mkdir()
            argv=[str(node),f"-datadir={directory}","-daemon=0"]
            class FakePopen:
                def __init__(self):
                    self.args=list(argv)
                    self.pid=12345
                def poll(self):return None
            receipt={"wamd_sha256":"a"*64,"wam_cli_sha256":"b"*64}
            def swapped_during_verify(_):
                displaced=core/"discarded-public-cli"
                cli.replace(displaced)
                # Same name AND same length, but a different native inode.
                cli.write_bytes(b"ALTERED_CLI_FIXTURE")
                return node,cli,receipt
            with (patch("wam_regtest.core_process.subprocess.Popen",FakePopen),
                  patch("wam_regtest.core_process.verified_core_paths",
                        side_effect=swapped_during_verify) as verified,
                  patch("wam_regtest.core_process._image") as image):
                with self.assertRaisesRegex(
                        CoreBindingError,"^RPC_EXECUTABLE_CHANGED_DURING_VERIFY$"):
                    OwnedCoreBinding(FakePopen(),core,directory)
                verified.assert_called_once_with(core)
                image.assert_not_called()

    def test_t04_wrong_launch_path_denied_before_any_byte_hash(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        import sys
        with TemporaryDirectory(prefix="t04-path-fixture-") as temporary:
            core=Path(temporary).resolve(strict=True)
            directory=core/"disposable-chain"
            class FakePopen:
                def __init__(self):
                    self.args=[str(core/"other-daemon"),f"-datadir={directory}","-daemon=0"]
                def poll(self):return None
            with (patch("wam_regtest.core_process.subprocess.Popen",FakePopen),
                  patch("wam_regtest.core_process.verified_core_paths",
                        side_effect=AssertionError("UNTRUSTED_PATH_MUST_NOT_HASH"))):
                with self.assertRaisesRegex(CoreBindingError,"^RPC_OWNED_PROCESS_REQUIRED$"):
                    OwnedCoreBinding(FakePopen(),core,directory)
