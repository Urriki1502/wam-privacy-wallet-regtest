"""Owned Core durability barriers; real crash qualification is separate."""
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import unittest
from unittest.mock import Mock,patch

from wam_regtest import managed_wallet_checkpoint as module,cli_rpc,rpc_scope
from wam_regtest.wallet_session import WalletSession,WalletSessionError


class CoreDurabilityContracts(unittest.TestCase):
    def test_flush_is_mutation_consented_and_has_one_fixed_parameter_shape(self):
        self.assertIn('gettxoutsetinfo',cli_rpc.WRITES)
        self.assertNotIn('gettxoutsetinfo',cli_rpc.READS)
        self.assertEqual(cli_rpc.validate(['gettxoutsetinfo','none']),('gettxoutsetinfo',['none']))
        for args in (['gettxoutsetinfo'],['gettxoutsetinfo','muhash'],
                     ['gettxoutsetinfo','none','1'],['gettxoutsetinfo','-rpcconnect=foreign']):
            with self.subTest(args=args),self.assertRaises(cli_rpc.CliRpcError):cli_rpc.validate(args)

    def test_flush_reply_requires_exact_typed_height_and_hash(self):
        good={'height':102,'bestblock':'a'*64}
        self.assertEqual(cli_rpc.decode(json.dumps(good).encode(),'gettxoutsetinfo',['none']),good)
        for value in ({'height':True,'bestblock':'a'*64},{'height':-1,'bestblock':'a'*64},
                      {'height':102,'bestblock':'private'},{'height':102},[],None):
            with self.subTest(value=value),self.assertRaises(cli_rpc.CliRpcError):
                cli_rpc.decode(json.dumps(value).encode(),'gettxoutsetinfo',['none'])

    def test_read_only_owned_scope_cannot_flush(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();binary=root/'cli';binary.write_bytes(b'public-fixture-only')
            context=SimpleNamespace(lock=threading.RLock(),faulted=False,authorized=False,ready=True,
                                    binding=SimpleNamespace(cli=binary))
            with patch.dict(rpc_scope._contexts,{str(root):context}),patch.object(rpc_scope,'execute') as execute:
                with self.assertRaisesRegex(cli_rpc.CliRpcError,'MUTATION_CONSENT_REQUIRED'):
                    rpc_scope.route(binary,root,['gettxoutsetinfo','none'])
                execute.assert_not_called()
            self.assertTrue(context.faulted)

    def owner(self):
        owner=SimpleNamespace(process=object(),cli=Path.cwd()/'cli',directory=Path.cwd(),read=Mock())
        owner.read.call.side_effect=lambda method:{'getblockcount':102,'getbestblockhash':'a'*64}[method]
        return owner

    def test_barrier_is_cached_only_for_same_popen_and_tip_after_fresh_owner_check(self):
        owner=self.owner()
        with patch.object(module,'_owned') as owned,patch('wam_regtest.core._read_cli',
                return_value={'height':102,'bestblock':'a'*64}) as flush:
            module.durable_core_checkpoint(owner,102,'a'*64)
            module.durable_core_checkpoint(owner,102,'a'*64)
            self.assertEqual(flush.call_count,1);self.assertEqual(owned.call_count,3)
            owner.process=object()
            module.durable_core_checkpoint(owner,102,'a'*64)
            self.assertEqual(flush.call_count,2)
            owned.side_effect=module.ManagedWalletError('ORIGINAL_OWNER_REQUIRED')
            with self.assertRaises(module.ManagedWalletError):module.durable_core_checkpoint(owner,102,'a'*64)
            self.assertEqual(flush.call_count,2)

    def test_wrong_tip_or_postflush_movement_never_caches_a_barrier(self):
        for reply in ({'height':101,'bestblock':'a'*64},{'height':102,'bestblock':'b'*64}):
            owner=self.owner()
            with patch.object(module,'_owned'),patch('wam_regtest.core._read_cli',return_value=reply):
                with self.assertRaises(module.ManagedWalletError):module.durable_core_checkpoint(owner,102,'a'*64)
            self.assertFalse(hasattr(owner,'_durable_core_checkpoint'))
        owner=self.owner();owner.read.call.side_effect=None;owner.read.call.return_value=103
        with patch.object(module,'_owned'),patch('wam_regtest.core._read_cli',
                return_value={'height':102,'bestblock':'a'*64}):
            with self.assertRaises(module.ManagedWalletError):module.durable_core_checkpoint(owner,102,'a'*64)
        self.assertFalse(hasattr(owner,'_durable_core_checkpoint'))

    def test_failed_flush_cannot_publish_wallet_anchor_or_release_state(self):
        session=object.__new__(WalletSession);session._managed_owner=self.owner()
        session.scanner=Mock();session.scanner.store.tip.return_value=(102,'a'*64)
        session.vault=Mock();session.ring=Mock();session._password=b'public-fixture-password'
        session.faulted=False;original=session._managed_owner.process
        with patch('wam_regtest.managed_wallet_session.check_session'), \
                patch.object(module,'durable_core_checkpoint',side_effect=ValueError('flush-denied')):
            with self.assertRaisesRegex(WalletSessionError,'ANCHORED_SAVE_FAILED'):session._save()
        session.vault.save.assert_not_called();self.assertTrue(session.faulted)
        self.assertIs(session._managed_owner.process,original)
        session.scanner.close.assert_not_called();session.ring.close.assert_not_called()
