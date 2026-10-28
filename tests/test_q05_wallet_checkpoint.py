"""Reference/custody refusals; genuine vault/scanner proof is a native probe."""
import json
import hmac
from pathlib import Path
import unittest
from unittest.mock import patch

import test_q05_core_supervisor as fixture
from wam_regtest import managed_wallet_checkpoint as module
from wam_regtest.supervisor_store import read_exact


class WalletCheckpointContracts(unittest.TestCase):
    setUp=fixture.SupervisorLifecycleUnit.setUp
    owner=fixture.SupervisorLifecycleUnit.owner

    def test_creation_needs_consent_before_any_owner_or_source_access(self):
        with patch.object(module,'_owned') as owned,patch.object(module,'_pinned_source') as source:
            with self.assertRaisesRegex(module.ManagedWalletError,'EXPLICIT_CONSENT'):
                module.checkpoint(object(),Path('/unused'),b'public-disposable-password')
            owned.assert_not_called();source.assert_not_called()

    def test_bad_password_scope_denied_before_source_keys_or_storage(self):
        for password in (b'short','public-password',b'x'*1025):
            with patch.object(module,'_owned') as owned:
                with self.assertRaisesRegex(module.ManagedWalletError,'INPUT_DENIED'):
                    module.checkpoint(object(),Path('/unused'),password,authorized=True)
                owned.assert_not_called()

    def test_observed_or_stopped_owner_never_grants_wallet_access(self):
        for owner in (object(),self.owner()):
            with self.assertRaisesRegex(module.ManagedWalletError,'ORIGINAL_OWNER_REQUIRED'):
                module._owned(owner)

    def test_reference_is_create_once_authenticated_and_profile_bound(self):
        owner=self.owner();wallet='a'*32
        module._publish_reference(owner,wallet)
        original=read_exact(self.root,'supervisor.wallet')
        self.assertEqual(module._read_reference(owner),wallet)
        with self.assertRaises(ValueError):module._publish_reference(owner,'b'*32)
        self.assertEqual(read_exact(self.root,'supervisor.wallet'),original)
        owner.profile=dict(owner.profile,config_sha256='c'*64)
        with self.assertRaisesRegex(module.ManagedWalletError,'REFERENCE_UNVERIFIED'):
            module._read_reference(owner)

    def test_wrong_wallet_id_or_mac_is_never_repaired(self):
        owner=self.owner();module._publish_reference(owner,'a'*32)
        path=self.root/'supervisor.wallet';original=path.read_bytes()
        for field,value in (('wallet_id','b'*32),('network','main'),('mac','0'*64)):
            row=json.loads(original);row[field]=value;raw=json.dumps(row).encode()
            path.write_bytes(raw)
            with self.assertRaisesRegex(module.ManagedWalletError,'REFERENCE_UNVERIFIED'):
                module._read_reference(owner)
            self.assertEqual(path.read_bytes(),raw)

    def test_partial_reference_and_wrong_token_refuse_without_replacement(self):
        owner=self.owner();module._publish_reference(owner,'a'*32)
        path=self.root/'supervisor.wallet';original=path.read_bytes()
        (self.root/'supervisor.token').write_bytes(b'z'*32)
        with self.assertRaises(module.ManagedWalletError):module._read_reference(owner)
        path.write_bytes(original[:-12])
        with self.assertRaises(module.ManagedWalletError):module._read_reference(owner)
        self.assertEqual(path.read_bytes(),original[:-12])

    def test_authenticated_integer_zero_is_not_false_network_authority(self):
        owner=self.owner();module._publish_reference(owner,'a'*32)
        path=self.root/'supervisor.wallet';row=json.loads(path.read_bytes())
        row.pop('mac');row['mainnet_allowed']=0
        secret=read_exact(self.root,'supervisor.token',length=32)
        row['mac']=hmac.digest(secret,module.SCHEMA.encode()+b'\n'+module._canonical(row),'sha256').hex()
        path.write_bytes(module._canonical(row))
        with self.assertRaisesRegex(module.ManagedWalletError,'REFERENCE_UNVERIFIED'):
            module._read_reference(owner)

    def test_existing_runtime_or_sidecars_are_preserved(self):
        owner=self.owner();runtime=owner.directory/'wallet-runtime.sqlite'
        for suffix in ('','-journal','-wal','-shm'):
            path=runtime.with_name(runtime.name+suffix);path.write_bytes(b'preserve')
            with self.assertRaisesRegex(module.ManagedWalletError,'EXISTING_RUNTIME_DENIED'):
                module._runtime(owner)
            self.assertEqual(path.read_bytes(),b'preserve');path.unlink()

    def test_control_protocol_does_not_gain_password_wallet_or_spending_ops(self):
        from wam_regtest.supervisor_protocol import CONTROL_COMMANDS,READ_COMMANDS
        self.assertFalse({'wallet-create','wallet-unlock','sign','broadcast','scan'} &
                         (CONTROL_COMMANDS|READ_COMMANDS))

    def test_scanner_client_never_expands_for_mempool_probe_introspection(self):
        from wam_regtest.wallet_session import WalletCoreCli
        from wam_regtest.wsp_live import RealWspScanError,REGTEST_GENESIS
        client=WalletCoreCli(Path('/unused/cli'),Path('/unused/profile'))
        client._genesis=REGTEST_GENESIS
        with patch.object(WalletCoreCli,'_call') as send:
            with self.assertRaisesRegex(RealWspScanError,'WSP_LIVE_METHOD_DENIED'):
                client.call('getrawmempool')
            send.assert_not_called()
