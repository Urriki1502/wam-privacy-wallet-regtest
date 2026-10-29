"""Refuse unqualified/fabricated probe evidence; actual Core runs separately."""
from hashlib import sha256
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import patch

from wam_regtest import q05_checkpoint_scenario as checkpoint
from wam_regtest import q05_security_scenario as security
from wam_regtest.q05_packaged import run

ROOT=Path(__file__).resolve().parents[1]


class QualificationContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name).resolve()
        self.root=self.directory/('wam-fusion-core-'+'a'*16)
        self.args=['--core-dir',str(self.directory),'--wsp-source',str(self.directory),
            '--root',str(self.root),'--receipt',str(self.directory/'receipt.json')]

    def test_checkpoint_requires_consent_before_source_core_or_custody(self):
        with patch.object(checkpoint,'verify_source') as source,patch.object(checkpoint,'verified_core_paths') as core:
            with self.assertRaises(SystemExit):checkpoint.main(self.args)
            source.assert_not_called();core.assert_not_called()
        self.assertEqual(list(self.directory.iterdir()),[])

    def test_checkpoint_incompatible_fault_modes_refuse_before_access(self):
        for flags in (['--reservation','uncertain'],['--complete-pending-recovery'],
                      ['--negative','corrupt','--fund-disposable-wallet']):
            with self.subTest(flags=flags),patch.object(checkpoint,'verify_source') as source:
                with self.assertRaises(SystemExit):
                    checkpoint.main([*self.args,'--confirm-disposable-regtest',*flags])
                source.assert_not_called()

    def test_security_contender_cannot_create_a_missing_profile(self):
        with patch.object(security,'verify_source') as source:
            with self.assertRaisesRegex(ValueError,'DISPOSABLE_SCOPE_DENIED'):
                security.main([*self.args,'--confirm-disposable-regtest','--lease-contender'])
            source.assert_not_called()
        self.assertFalse(self.root.exists())

    def test_security_parent_never_uses_an_existing_profile(self):
        self.root.mkdir();canary=self.root/'preserve';canary.write_bytes(b'public-fixture')
        with patch.object(security,'verify_source') as source:
            with self.assertRaisesRegex(ValueError,'DISPOSABLE_SCOPE_DENIED'):
                security.main([*self.args,'--confirm-disposable-regtest'])
            source.assert_not_called()
        self.assertEqual(canary.read_bytes(),b'public-fixture')

    def test_frozen_scenarios_pass_only_bundled_resources_and_explicit_flags(self):
        args=['--root',str(self.root),'--receipt',str(self.directory/'receipt.json'),
              '--confirm-disposable-regtest']
        for scenario,module in (('checkpoint',checkpoint),('security',security)):
            with patch.object(sys,'frozen',True,create=True),patch.object(sys,'platform','darwin'), \
                    patch.object(module,'main',return_value=0) as execute:
                self.assertEqual(run(self.directory,self.directory,[*args,'--scenario',scenario]),0)
                execute.assert_called_once_with(args,core=self.directory,source=self.directory,frozen=True)

    def test_frozen_supplement_rejects_missing_shutdown_or_altered_source_or_binary(self):
        require=runpy.run_path(str(ROOT/'scripts/qualify_q05_frozen.py'))['require_supplement']
        binary=self.directory/'bootloader';binary.write_bytes(b'public-test-bootloader')
        base={k:'public-fixture' for k in
              ('source_sha','checkout_sha','core_sha256','wsp_source_commit','platform','core_trust')}
        good={**base,'status':'PASS','owner_shutdown_verified':True,'frozen':True,
            'synthetic_rpc':False,'mainnet_allowed':False,
            'source_provenance':{'frozen_executable_sha256':sha256(binary.read_bytes()).hexdigest()},
            'observations':[{'cross_process_competing_owner_refused':True},
                {'credential_bytes_sent':0},{'explicit_original_backend_quit_verified':True}]}
        require(good,base,binary,'security',[])
        for changes in ({'owner_shutdown_verified':False},{'source_sha':'foreign'},
                        {'synthetic_rpc':True},{'source_provenance':{}},
                        {'observations':[]},{'frozen':False}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                require({**good,**changes},base,binary,'security',[])

    def test_frozen_uncertain_recovery_cannot_use_a_gui_or_signed_only_receipt(self):
        require=runpy.run_path(str(ROOT/'scripts/qualify_q05_frozen.py'))['require_supplement']
        binary=self.directory/'bootloader';binary.write_bytes(b'public-test-bootloader')
        base={k:'public-fixture' for k in
              ('source_sha','checkout_sha','core_sha256','wsp_source_commit','platform','core_trust')}
        good={**base,'status':'PASS','owner_shutdown_verified':True,'frozen':True,
            'synthetic_rpc':False,'mainnet_allowed':False,'recovery_completed':True,
            'qualification_scope':'EXPLICIT_PENDING_RECOVERY_COMPLETION',
            'automatic_wallet_transaction_replay':False,'wallet_broadcast_calls_total':1,
            'source_provenance':{'frozen_executable_sha256':sha256(binary.read_bytes()).hexdigest()},
            'observations':[{'explicit_pending_commit_completed':True},
                            {'reopened_same_wallet_live_resync':True}]}
        require(good,base,binary,'checkpoint',['uncertain'])
        for changes in ({'wallet_broadcast_calls_total':0},{'wallet_broadcast_calls_total':2},
                        {'recovery_completed':False},{'automatic_wallet_transaction_replay':True},
                        {'qualification_scope':'CLEAN_OWNER_REOPEN'}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                require({**good,**changes},base,binary,'checkpoint',['uncertain'])
