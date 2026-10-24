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


if __name__=='__main__':unittest.main()
