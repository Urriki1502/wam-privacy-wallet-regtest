"""Funding/cleanup contracts with deterministic RPC fixtures, NOT Core proof."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import unittest
from unittest.mock import Mock,patch

from wam_regtest.q05_gui_scenario import LabBackend,_funding_code,_funding_failure
from wam_regtest.wallet_session import WalletSessionError
from wam_regtest.wsp_live import RealWspScanError


class FundingContracts(unittest.TestCase):
    def backend(self):
        b=LabBackend(None,None,None,mining_address='wamrt1q'+'q'*40)
        b.owner=SimpleNamespace(cli=Path.cwd()/'fixture-cli',directory=Path.cwd(),_faulted=False)
        b.session=SimpleNamespace(ring=Mock());b.lab='fund'
        b.session.ring.accounts.return_value=[Mock()]
        return b

    def test_session_refusal_precedes_rpc_and_preserves_original_exception(self):
        b=self.backend();error=WalletSessionError('WALLET_MANAGED_OWNER_UNVERIFIED')
        with patch('wam_regtest.managed_wallet_session.check_session',side_effect=error), \
                patch('wam_regtest.wallet_session.WalletCoreCli') as rpc:
            with self.assertRaises(WalletSessionError) as caught:b.execute('network',(),{})
        self.assertIs(caught.exception,error);rpc.assert_not_called()
        self.assertEqual(b.funding_failure,{'stage':'session','code':error.args[0]})

    def test_attestation_refusal_closes_transport_before_any_mutation(self):
        b=self.backend();rpc=Mock();error=RealWspScanError('WSP_LIVE_RPC_AUTHENTICATION_DENIED')
        rpc.attest.side_effect=error
        with patch('wam_regtest.managed_wallet_session.check_session'), \
                patch('wam_regtest.wallet_session.WalletCoreCli',return_value=rpc):
            with self.assertRaises(RealWspScanError) as caught:b.execute('network',(),{})
        self.assertIs(caught.exception,error);rpc._call.assert_not_called()
        rpc._transport.close.assert_called_once_with()
        self.assertEqual(b.funding_failure,{'stage':'attestation','code':error.args[0]})

    def test_success_attests_before_generation_and_payment_on_same_client(self):
        b=self.backend();rpc=Mock();order=[]
        rpc.attest.side_effect=lambda:order.append('attest')
        rpc._call.side_effect=lambda *a:order.append('generate')
        def payment(client,account,address):
            self.assertIs(client,rpc);self.assertEqual(address,b.mining_address)
            order.append('payment');return 'a'*64,12345,102
        with patch('wam_regtest.managed_wallet_session.check_session',side_effect=lambda s:order.append('session')), \
                patch('wam_regtest.wallet_session.WalletCoreCli',return_value=rpc), \
                patch('wam_regtest.q05_gui_scenario._public_fixture_payment',side_effect=payment), \
                patch('wam_sp.keystore.Keyring') as keyring:
            keyring.return_value.accounts.return_value[0].payment_code.return_value='public-test-recipient'
            result=b.execute('network',(),{})
        self.assertEqual(order,['session','attest','generate','payment'])
        rpc._call.assert_called_once_with('generatetoaddress',['101',b.mining_address])
        rpc._transport.close.assert_called_once_with();keyring.return_value.close.assert_called_once_with()
        self.assertEqual(result,{'fixture_payment':'a'*64,'atoms':12345,'height':102,
            'recipient':'public-test-recipient'})
        self.assertIsNone(b.lab);self.assertIsNone(b.funding_failure)

    def test_generation_timeout_quarantines_scope_independently_of_supervisor(self):
        from wam_regtest import rpc_scope
        from wam_regtest.cli_rpc import CliRpcError
        from wam_regtest.wsp_live import REGTEST_GENESIS
        b=self.backend()
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp).resolve();binary=directory/'fixture-cli';binary.write_bytes(b'fixture')
            b.owner.cli=binary;b.owner.directory=directory
            binding=SimpleNamespace(cli=binary,_assert_image=Mock())
            context=SimpleNamespace(binding=binding,lock=threading.RLock(),faulted=False,
                authorized=True,credentials=Mock(port=12345),assert_endpoint=Mock(),ready=True)
            methods=[]
            def execute(argv,method,params,**kwargs):
                methods.append(method)
                if method=='generatetoaddress':
                    self.assertEqual(kwargs['timeout'],10)
                    raise CliRpcError('CORE_RPC_TIMEOUT_UNCERTAIN')
                return {'getblockchaininfo':{'chain':'regtest','blocks':0},
                    'getblockhash':REGTEST_GENESIS,
                    'getconnectioncount':0,
                    'getnetworkinfo':{'version':111,'subversion':'/WAM:0.1.11/','protocolversion':70016}}[method]
            with patch.dict(rpc_scope._contexts,{str(directory):context}), \
                    patch('wam_regtest.managed_wallet_session.check_session'), \
                    patch('wam_regtest.wsp_live.LiveCoreReadOnlyCli._http_enabled',False), \
                    patch('wam_regtest.network_policy.local_rpc_port',return_value=12345), \
                    patch('wam_regtest.rpc_scope.execute',side_effect=execute), \
                    patch('wam_regtest.q05_gui_scenario._public_fixture_payment') as payment:
                with self.assertRaisesRegex(RealWspScanError,'^WSP_LIVE_RPC_DENIED$'):
                    b.execute('network',(),{})
                payment.assert_not_called()
            self.assertTrue(context.faulted);self.assertFalse(b.owner._faulted)
            self.assertEqual(methods.count('generatetoaddress'),1)
            self.assertEqual(b.funding_failure,{'stage':'generation','code':'WSP_LIVE_RPC_DENIED',
                'cli_code':'CORE_RPC_TIMEOUT_UNCERTAIN'})

    def test_payment_failure_closes_transport_without_repeating_generation(self):
        b=self.backend();rpc=Mock();error=RealWspScanError('WSP_PUBLIC_FIXTURE_HEIGHT_DENIED')
        with patch('wam_regtest.managed_wallet_session.check_session'), \
                patch('wam_regtest.wallet_session.WalletCoreCli',return_value=rpc), \
                patch('wam_regtest.q05_gui_scenario._public_fixture_payment',side_effect=error):
            with self.assertRaises(RealWspScanError) as caught:b.execute('network',(),{})
        self.assertIs(caught.exception,error)
        rpc._call.assert_called_once_with('generatetoaddress',['101',b.mining_address])
        rpc._transport.close.assert_called_once_with()
        self.assertEqual(b.funding_failure,{'stage':'payment','code':error.args[0]})

    def test_funding_without_disposable_mutation_grant_never_executes_cli(self):
        from wam_regtest import rpc_scope
        from wam_regtest.wallet_session import WalletCoreCli
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp).resolve();binary=directory/'fixture-cli';binary.write_bytes(b'fixture')
            context=SimpleNamespace(lock=threading.RLock(),faulted=False,authorized=False,ready=True,
                binding=SimpleNamespace(cli=binary))
            with patch.dict(rpc_scope._contexts,{str(directory):context}), \
                    patch('wam_regtest.network_policy.local_rpc_port',return_value=12345), \
                    patch('wam_regtest.rpc_scope.execute') as cli:
                rpc=WalletCoreCli(binary,directory)
                with self.assertRaises(RealWspScanError) as caught:
                    rpc._call('generatetoaddress',['101','wamrt1q'+'q'*40])
                cli.assert_not_called()
            self.assertTrue(context.faulted)
            self.assertEqual(_funding_failure('generation',caught.exception)['cli_code'],
                'CORE_RPC_MUTATION_CONSENT_REQUIRED')

    def test_normal_supervisor_stop_cannot_use_quarantined_wallet_scope(self):
        from wam_regtest import rpc_scope
        from wam_regtest.core_supervisor import CoreSupervisor,ManagedCoreError
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp).resolve()
            owner=object.__new__(CoreSupervisor);owner._faulted=False
            owner.directory=directory;owner.cli=directory/'fixture-cli'
            original=owner.process=Mock();owner.binding=Mock();owner.journal=Mock()
            owner._check_profile=Mock()
            context=SimpleNamespace(lock=threading.RLock(),faulted=True)
            with patch.dict(rpc_scope._contexts,{str(directory):context}), \
                    patch('wam_regtest.network_policy.local_rpc_port',return_value=12345), \
                    patch('wam_regtest.rpc_scope.execute') as cli:
                with self.assertRaisesRegex(ManagedCoreError,'^MANAGED_SHUTDOWN_UNCERTAIN$'):
                    owner.shutdown()
                cli.assert_not_called()
            self.assertTrue(owner._faulted);self.assertIs(owner.process,original)
            original.kill.assert_not_called();original.terminate.assert_not_called()

    def test_private_or_lookalike_errors_never_enter_receipts(self):
        class Lookalike(RealWspScanError):pass
        for error in (ValueError('rpcpassword=canary'),RealWspScanError('PRIVATE_CANARY'),
                      Lookalike('WSP_LIVE_RPC_DENIED'),RealWspScanError(['private']),
                      RealWspScanError('WSP_LIVE_RPC_DENIED','private')):
            with self.subTest(error_type=type(error).__name__):
                self.assertEqual(_funding_code(error),'Q05_FIXTURE_FUNDING_DENIED')
        from wam_regtest.core import CoreSmokeError
        for cause in (CoreSmokeError('rpcpassword=canary'),ValueError('CORE_RPC_TIMEOUT_UNCERTAIN')):
            error=RealWspScanError('WSP_LIVE_RPC_DENIED');error.__context__=cause
            self.assertEqual(_funding_failure('generation',error),
                {'stage':'generation','code':'WSP_LIVE_RPC_DENIED'})
