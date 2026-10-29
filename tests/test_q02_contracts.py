"""Q02 SOURCE contracts only. Child Python output is NOT Core E2E evidence."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from wam_regtest.cli_rpc import validate,decode,execute,CliRpcError,LIMIT
from wam_regtest.core import CoreSmokeError
from wam_regtest.wsp_live import LiveCoreReadOnlyCli,RealWspScanError,REGTEST_GENESIS
from wam_regtest.wallet_session import WalletCoreCli,WalletSession,WalletSessionError
from wam_regtest.gui_errors import operation_error,error_text


class Q02Contracts(unittest.TestCase):
    def test_option_overrides_and_unknown_capabilities_denied(self):
        for args in (['-rpcconnect=127.0.0.1','getblockcount'],
                     ['getblockcount','-rpcport=12345'],['getblockhash','-1'],
                     ['-rpcwallet=other','getnewaddress'],['getnewaddress'],
                     ['-rpcwallet=test','stop'],['dumpprivkey','test'],
                     ['sendrawtransaction','00','-conf=other'],
                     ['getblockhash','0\n-rpcconnect=remote'],
                     ['getblockhash',True],['generatetoaddress','102','wamrt1q'+'q'*40]):
            with self.subTest(args=args),self.assertRaises(CliRpcError):validate(args)
        self.assertEqual(validate(['-rpcwallet=test','getnewaddress']),('getnewaddress',[]))
        self.assertEqual(validate(['getblockhash','0']),('getblockhash',['0']))
        tip='ab'*32
        quoted='"'+tip+'"'
        self.assertEqual(validate(['gettxoutsetinfo','none',quoted,'true']),
                         ('gettxoutsetinfo',['none',quoted,'true']))
        for args in (['gettxoutsetinfo'],['gettxoutsetinfo','none',tip,'true'],
                     ['gettxoutsetinfo','none',quoted,'false'],
                     ['gettxoutsetinfo','none',tip,'false'],
                     ['gettxoutsetinfo','"'+tip+'"','true'],
                     ['gettxoutsetinfo','none',tip]):
            with self.subTest(args=args),self.assertRaises(CliRpcError):validate(args)
        stats=('{"height":103,"bestblock":"'+tip+'","total_amount":50.0}').encode()
        self.assertEqual(decode(stats,'gettxoutsetinfo',['none',quoted,'true'])['height'],103)
        with self.assertRaises(CliRpcError):
            decode(b'{"height":103,"bestblock":"'+b'cd'*32+b'"}','gettxoutsetinfo',['none',quoted,'true'])

    def test_bare_hash_and_address_are_strings_not_json_numbers(self):
        self.assertEqual(decode(b'0'*64,'getblockhash',['0']),'0'*64)
        self.assertEqual(decode(REGTEST_GENESIS.encode()+b'\n','getbestblockhash',[]),REGTEST_GENESIS)
        address='wamrt1q'+'q'*40
        self.assertEqual(decode(address.encode(),'getnewaddress',[]),address)

    def test_strict_result_types_duplicates_unicode_nonfinite_and_bounds(self):
        for raw,method,params in ((b'"0"','getblockcount',[]),(b'true','getblockcount',[]),
            (b'{"result":0,"error":null,"id":1}','getblockcount',[]),
            (b'{"chain":"regtest","chain":"main"}','getblockchaininfo',[]),
            (b'{"x":NaN}','getblockchaininfo',[]),(b'\xff','getblockcount',[]),
            (b'0'+b' '*LIMIT,'getblockcount',[]),(b'[]','getnetworkinfo',[]),
            (b'','getblockcount',[]),(b'{}','getblock',['0'*64,'3'])):
            with self.subTest(method=method,raw=raw[:40]),self.assertRaises(CliRpcError):decode(raw,method,params)

    def test_stream_limits_are_enforced_while_reading_both_pipes(self):
        with tempfile.TemporaryDirectory() as temp:
            for code in ('import os;os.write(2,b"x"*8192)',
                         'import os;os.write(1,b"x"*(9*1024*1024))'):
                with self.assertRaisesRegex(CliRpcError,'CORE_RPC_REPLY_BOUNDS_DENIED'):
                    execute([sys.executable,'-c',code],'getblockcount',[],directory=Path(temp),
                            env=os.environ.copy(),timeout=5)

    def test_timeout_reaps_owned_child_and_never_retries(self):
        with tempfile.TemporaryDirectory() as temp:
            start=time.monotonic()
            with self.assertRaisesRegex(CliRpcError,'CORE_RPC_TIMEOUT_UNCERTAIN'):
                execute([sys.executable,'-c','import time;time.sleep(20)'],'getblockcount',[],
                    directory=Path(temp),env=os.environ.copy(),timeout=.2)
            self.assertLess(time.monotonic()-start,5)

    def test_errors_never_return_stderr_secrets(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(CliRpcError) as caught:
                execute([sys.executable,'-c',
                    'import sys;sys.stderr.write("Authorization failed: private-canary");sys.exit(1)'],
                    'getblockcount',[],directory=Path(temp),env=os.environ.copy(),timeout=5)
            self.assertEqual(caught.exception.args,('CORE_RPC_AUTHENTICATION_DENIED',))
            self.assertNotIn('private-canary',str(caught.exception))

    def test_rejected_fresh_attestation_invalidates_cached_genesis(self):
        rpc=LiveCoreReadOnlyCli(Path('source-contract-signed-cli').absolute(),Path('source-contract-private-chain').absolute())
        rpc._genesis=REGTEST_GENESIS
        with patch('wam_regtest.core._read_cli',return_value={'chain':'main','blocks':0}):
            with self.assertRaisesRegex(RealWspScanError,'WSP_LIVE_CHAIN_DENIED'):rpc.attest()
        self.assertIsNone(rpc._genesis)
        with self.assertRaisesRegex(RealWspScanError,'WSP_LIVE_METHOD_DENIED'):rpc.call('getblockcount')

    def test_authenticated_failure_latches_wallet_and_safe_error(self):
        faulted=[]
        rpc=WalletCoreCli(Path('source-contract-signed-cli').absolute(),Path('source-contract-private-chain').absolute(),on_trust_failure=lambda:faulted.append(True))
        with patch('wam_regtest.core._read_cli',side_effect=CoreSmokeError('CORE_RPC_AUTHENTICATION_DENIED')):
            with self.assertRaises(WalletSessionError) as caught:rpc.attest()
        self.assertEqual(faulted,[True])
        self.assertEqual(operation_error('sync',caught.exception),'WALLET_CORE_AUTHENTICATION_DENIED')
        self.assertNotIn('private-canary',error_text('WALLET_CORE_AUTHENTICATION_DENIED private-canary'))

    def test_unknown_external_error_does_not_become_trusted_diagnostic(self):
        faulted=[]
        rpc=WalletCoreCli(Path('source-contract-signed-cli').absolute(),Path('source-contract-private-chain').absolute(),on_trust_failure=lambda:faulted.append(True))
        with patch('wam_regtest.core._read_cli',side_effect=CoreSmokeError('rpcpassword=private-canary')):
            with self.assertRaisesRegex(WalletSessionError,'^WALLET_CORE_UNVERIFIED$'):rpc.attest()
        self.assertEqual(faulted,[True])

    def test_unlock_requires_explicit_core_consent_and_password_before_reauthentication(self):
        import threading
        from unittest.mock import Mock
        from wam_regtest.vault import VaultError
        session=object.__new__(WalletSession)
        session._lock=threading.RLock();session.ring=None
        session._core_reauthentication_required=True
        session.vault=SimpleNamespace(restore=Mock(side_effect=VaultError('VAULT_AUTHENTICATION_DENIED')))
        session.runtime=Path('/unused-source-contract.sqlite')
        with patch('wam_regtest.rpc_scope.reauthenticate_owned') as reauth:
            with self.assertRaisesRegex(WalletSessionError,'WALLET_CORE_REAUTHENTICATION_REQUIRED'):
                session.unlock(b'wrong-source-contract-password')
            session.vault.restore.assert_not_called();reauth.assert_not_called()
            with self.assertRaises(VaultError):
                session.unlock(b'wrong-source-contract-password',True)
            reauth.assert_not_called()

    def test_windows_vault_fixture_allows_identity_read_but_no_scanner_capability_expansion(self):
        from wam_regtest.windows_vault_probe import WindowsVaultFixtureRpc,WindowsVaultProbeError
        rpc=WindowsVaultFixtureRpc(Path('source-cli').absolute(),Path('source-chain').absolute(),12345,{})
        reply={'version':111,'subversion':'/WAM:0.1.11/','protocolversion':70016}
        with patch('wam_regtest.windows_vault_probe._rpc',return_value=reply) as invoke:
            self.assertEqual(rpc._call('getnetworkinfo',[]),reply)
            invoke.assert_called_once()
        with self.assertRaises(WindowsVaultProbeError):rpc._call('dumpprivkey',[])
        with self.assertRaises(RealWspScanError):rpc.call('getnetworkinfo',[])

    def test_cli_identity_never_uses_relative_path_or_working_directory_search(self):
        from wam_regtest.core import _read_cli
        with patch('wam_regtest.network_policy.local_rpc_port') as profile,patch('wam_regtest.rpc_scope.route') as route:
            for binary,directory in (('wam-cli',str(Path.cwd())),(str(Path.cwd()/'wam-cli'),'relative-chain')):
                with self.assertRaisesRegex(CoreSmokeError,'CORE_LOCAL_RPC_COMMAND_DENIED'):
                    _read_cli([binary,'-datadir='+directory,'getblockcount'])
            profile.assert_not_called();route.assert_not_called()

    def test_preready_scope_reattest_refuses_ready_exited_and_foreign_process(self):
        from wam_regtest.q02_probe import recover_unready_owned_scope
        directory=Path('/source-contract-private-chain').resolve()
        process=SimpleNamespace(poll=lambda:None)
        ready=SimpleNamespace(ready=True,binding=SimpleNamespace(process=process))
        exited=SimpleNamespace(poll=lambda:0)
        foreign=SimpleNamespace(poll=lambda:None)
        unready=SimpleNamespace(ready=False,binding=SimpleNamespace(process=process))
        with patch('wam_regtest.q02_probe.reauthenticate_owned') as reauth:
            with patch('wam_regtest.q02_probe.identity',return_value=ready):
                self.assertFalse(recover_unready_owned_scope(directory,process))
            with patch('wam_regtest.q02_probe.identity',return_value=unready):
                self.assertFalse(recover_unready_owned_scope(directory,exited))
                self.assertFalse(recover_unready_owned_scope(directory,foreign))
                self.assertFalse(recover_unready_owned_scope(directory,None))
                self.assertTrue(recover_unready_owned_scope(directory,process))
            reauth.assert_called_once_with(directory,authorized=True)

    def test_profile_failure_revokes_scope_before_transport_and_file_restore_cannot_revive_it(self):
        import threading
        from wam_regtest.core import _read_cli
        from wam_regtest.network_policy import NetworkPolicyError
        from wam_regtest import rpc_scope
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp).resolve()
            context=SimpleNamespace(lock=threading.RLock(),faulted=False)
            command=[str(Path('source-cli').absolute()),'-datadir='+str(directory),'getblockcount']
            with patch.dict(rpc_scope._contexts,{str(directory):context}),patch('wam_regtest.cli_rpc.execute') as invoke:
                with patch('wam_regtest.network_policy.local_rpc_port',side_effect=NetworkPolicyError('LOCAL_RPC_CONFIG_DENIED')):
                    with self.assertRaisesRegex(CoreSmokeError,'CORE_LOCAL_NETWORK_POLICY_DENIED'):_read_cli(command)
                self.assertTrue(context.faulted)
                with patch('wam_regtest.network_policy.local_rpc_port',return_value=12345):
                    with self.assertRaisesRegex(CoreSmokeError,'CORE_RPC_SCOPE_FAULTED'):_read_cli(command)
                invoke.assert_not_called()

    def test_mac_socket_probe_translate_subprocess_and_decode_failures(self):
        import subprocess
        from unittest.mock import Mock,patch
        from wam_regtest.core_process import _mac_socket,CoreBindingError
        good_stat=Mock(st_mode=0o100644,st_uid=0)
        with patch('wam_regtest.core_process.sys.platform','darwin'):
            with patch('wam_regtest.core_process.Path.lstat',return_value=good_stat):
                with patch('wam_regtest.core_process.subprocess.run',side_effect=subprocess.TimeoutExpired('lsof',2)):
                    with self.assertRaisesRegex(CoreBindingError,'RPC_SOCKET_PROOF_DENIED'):
                        _mac_socket(1,12345,54321)
                bad_stdout=Mock(stdout=b'\xff'*8,returncode=0)
                with patch('wam_regtest.core_process.subprocess.run',return_value=bad_stdout):
                    with self.assertRaisesRegex(CoreBindingError,'RPC_SOCKET_PROOF_DENIED'):
                        _mac_socket(1,12345,54321)

    def test_headless_core_reauth_requires_explicit_typed_approval(self):
        from unittest.mock import patch
        from wam_regtest import linux_headless
        class Session:
            def __init__(self,flag):self._core_reauthentication_required=flag
        self.assertTrue(linux_headless._core_reauth_prompt(Session(False)))
        need=Session(True)
        with patch('sys.stdin.isatty',return_value=True),patch('sys.stderr.isatty',return_value=True):
            with patch('builtins.input',return_value='REAUTH'):
                self.assertTrue(linux_headless._core_reauth_prompt(need))
            with patch('builtins.input',return_value='no'):
                with self.assertRaises(WalletSessionError):linux_headless._core_reauth_prompt(need)
        with patch('sys.stdin.isatty',return_value=False):
            with self.assertRaises(WalletSessionError):linux_headless._core_reauth_prompt(need)

    def test_owner_acceptance_harness_registers_owned_scope(self):
        text=(Path(__file__).resolve().parents[1]/'scripts'/'owner_acceptance.py').read_text()
        self.assertIn('register(proc,core,data,authorized_disposable_mutation=True)',text)
        self.assertIn('unregister(data)',text)

    def test_directory_stability_ignores_child_creation_and_keeps_owner_mode(self):
        from wam_regtest.private_directory import _directory_stability as mac
        from wam_regtest.linux_private_storage import _directory_stability as lin
        from wam_regtest.linux_private_storage import _identity
        base=dict(st_dev=1,st_ino=2,st_mode=0o40700,st_uid=3,st_gid=4,
                  st_nlink=2,st_size=0,st_mtime_ns=5,st_ctime_ns=6)
        original=SimpleNamespace(**base)
        child=SimpleNamespace(**{**base,'st_nlink':3,'st_mtime_ns':9,'st_ctime_ns':10})
        for stability in (mac,lin):
            self.assertEqual(stability(original),stability(child))
            self.assertNotEqual(stability(original),stability(SimpleNamespace(**{**base,'st_mode':0o40750})))
            self.assertNotEqual(stability(original),stability(SimpleNamespace(**{**base,'st_ino':99})))
            self.assertNotEqual(stability(original),stability(SimpleNamespace(**{**base,'st_uid':8})))
        changed=SimpleNamespace(**{**base,'st_mtime_ns':11})
        self.assertNotEqual(_identity(original),_identity(changed))

    @unittest.skipUnless(sys.platform=='darwin','macOS temp ACL regression only')
    def test_private_temporary_directory_avoids_inherited_system_temp_acl(self):
        from wam_regtest.custody import private_temporary_directory
        from wam_regtest.private_directory import open_macos_private_directory
        with private_temporary_directory(prefix='q02-contract-') as t:
            p=Path(t)
            fd=open_macos_private_directory(p)
            os.close(fd)
            self.assertTrue(p.exists())
        self.assertFalse(p.exists())


if __name__=='__main__':unittest.main()
