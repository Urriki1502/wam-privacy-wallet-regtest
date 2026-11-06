"""Q06 source-only onboarding/owner regression (not physical macOS UI E2E).

No fake Core success is reported as source-native or owned-Core acceptance.
"""
import importlib.util
from contextlib import contextmanager
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from mnemonic import Mnemonic
from wam_regtest.bip39_owner_backend import Bip39ReadOnlyBackend,Q06ReadOnlyError
from wam_regtest.bip39_12 import Bip39Regtest12Keys

SOURCE=Path(importlib.util.find_spec("wam_sp").origin).resolve().parents[2]
PASSWORD=b"Q06 standalone trial password"
PHRASE=Mnemonic("english").to_mnemonic(bytes(16))


class Q06OwnerBackendContracts(unittest.TestCase):
    @contextmanager
    def _backup_verifier(self):
        self.backend._secret = bytearray(PASSWORD)
        self.backend._seed_folder = self.root / ('bip39-12-' + 'a' * 32)
        with (patch('wam_regtest.bip39_seed_vault.read_seed_phrase', return_value=PHRASE),
              patch('wam_regtest.bip39_seed_vault._owner_binding', return_value='0' * 64),
              patch('wam_regtest.bip39_seed_vault.open_owned_seed_container') as opened,
              patch.object(self.backend, '_q06_write_ack') as write):
            opened.return_value.__enter__.return_value = self._fake_opened_keys()
            yield write

    def _backup_request(self):
        challenge = self.backend.execute('backup_challenge', (), {})
        answers = [PHRASE.split()[p - 1] for p in challenge['positions']]
        return challenge, answers

    def test_backup_challenge_exact_three_one_use_and_no_secret_output(self):
        with self._backup_verifier() as write:
            challenge, answers = self._backup_request()
            self.assertEqual(len(set(challenge['positions'])), 3)
            self.assertTrue(all(1 <= p <= 12 for p in challenge['positions']))
            self.assertEqual(challenge['expires_in_seconds'], 120)
            self.assertNotIn(PHRASE, repr(challenge))
            self.assertNotIn(PASSWORD.decode(), repr(challenge))
            self.assertTrue(self.backend.execute('backup_verify', (challenge['challenge_id'], answers), {}))
            with self.assertRaises(Q06ReadOnlyError):
                self.backend.execute('backup_verify', (challenge['challenge_id'], answers), {})
            write.assert_called_once()

    def test_backup_challenge_denies_one_two_extra_and_caller_positions(self):
        with self._backup_verifier() as write:
            for count in (1, 2, 4):
                with self.subTest(count=count):
                    challenge, answers = self._backup_request()
                    with self.assertRaises(Q06ReadOnlyError):
                        self.backend.execute('backup_verify', (challenge['challenge_id'], (answers * 2)[:count]), {})
                    with self.assertRaises(Q06ReadOnlyError):
                        self.backend.execute('backup_verify', (challenge['challenge_id'], answers), {})
            challenge, answers = self._backup_request()
            with self.assertRaises(Q06ReadOnlyError):
                self.backend.execute('backup_verify', ([1, 2, 3], answers), {})
            write.assert_not_called()

    def test_backup_wrong_answer_consumes_challenge(self):
        with self._backup_verifier() as write:
            challenge, answers = self._backup_request()
            self.assertFalse(self.backend.execute('backup_verify', (challenge['challenge_id'], ['wrong'] * 3), {}))
            with self.assertRaises(Q06ReadOnlyError):
                self.backend.execute('backup_verify', (challenge['challenge_id'], answers), {})
            write.assert_not_called()
            fresh, answers = self._backup_request()
            self.assertNotEqual(fresh['challenge_id'], challenge['challenge_id'])
            self.assertTrue(self.backend.execute('backup_verify', (fresh['challenge_id'], answers), {}))

    def test_backup_expired_challenge_and_expiry_during_native_auth_refuse(self):
        with self._backup_verifier() as write, patch('wam_regtest.bip39_owner_backend.time.monotonic') as clock:
            clock.return_value = 1000
            challenge, answers = self._backup_request()
            clock.return_value = 1120
            with self.assertRaises(Q06ReadOnlyError):
                self.backend.execute('backup_verify', (challenge['challenge_id'], answers), {})
            clock.return_value = 2000
            challenge, answers = self._backup_request()
            def decrypt(*args, **kwargs):
                clock.return_value = 2120
                return PHRASE
            with patch('wam_regtest.bip39_seed_vault.read_seed_phrase', side_effect=decrypt):
                with self.assertRaises(Q06ReadOnlyError):
                    self.backend.execute('backup_verify', (challenge['challenge_id'], answers), {})
            write.assert_not_called()

    def test_backup_profile_epoch_cancel_and_replaced_id_refuse(self):
        with self._backup_verifier() as write:
            for change in ('profile', 'epoch', 'cancel', 'replace'):
                with self.subTest(change=change):
                    challenge, answers = self._backup_request()
                    original = self.backend._seed_folder
                    if change == 'profile':
                        self.backend._seed_folder = self.root / ('bip39-12-' + 'b' * 32)
                    elif change == 'epoch':
                        self.backend._backup_epoch += 1
                    elif change == 'cancel':
                        self.backend.execute('backup_challenge_cancel', (), {})
                    else:
                        self._backup_request()
                    with self.assertRaises(Q06ReadOnlyError):
                        self.backend.execute('backup_verify', (challenge['challenge_id'], answers), {})
                    self.backend._seed_folder = original
            write.assert_not_called()

    def test_backup_lock_and_restarted_backend_cannot_reuse_id(self):
        with self._backup_verifier() as write:
            challenge, answers = self._backup_request()
            folder = self.backend._seed_folder
            self.backend._lock_q06()
            self.backend._secret, self.backend._seed_folder = bytearray(PASSWORD), folder
            with self.assertRaises(Q06ReadOnlyError):
                self.backend.execute('backup_verify', (challenge['challenge_id'], answers), {})
            restarted = Bip39ReadOnlyBackend(self.root, Path('/synthetic-core'), SOURCE)
            restarted._secret, restarted._seed_folder = bytearray(PASSWORD), folder
            with self.assertRaises(Q06ReadOnlyError):
                restarted.execute('backup_verify', (challenge['challenge_id'], answers), {})
            restarted._lock_q06()
            write.assert_not_called()

    def test_backup_ack_write_failure_cannot_retry_same_challenge(self):
        with self._backup_verifier() as write:
            challenge, answers = self._backup_request()
            write.side_effect = OSError('public test storage failure')
            with self.assertRaises(Q06ReadOnlyError):
                self.backend.execute('backup_verify', (challenge['challenge_id'], answers), {})
            with self.assertRaises(Q06ReadOnlyError):
                self.backend.execute('backup_verify', (challenge['challenge_id'], answers), {})
            write.assert_called_once()

    def test_backup_simultaneous_executor_submissions_only_one_ack(self):
        from wam_regtest.wallet_executor import WalletExecutor, WalletExecutorError
        with self._backup_verifier() as write:
            facade = SimpleNamespace(
                execute=lambda action, args, kwargs: None if action == 'quit' else self.backend.execute(action, args, kwargs),
                public_state=self.backend.public_state)
            executor = WalletExecutor(lambda: facade)
            try:
                challenge = executor.request('backup_challenge')
                answers = [PHRASE.split()[p - 1] for p in challenge['positions']]
                futures = [executor.submit('backup_verify', challenge['challenge_id'], answers) for _ in range(2)]
                successes = 0
                for future in futures:
                    try:
                        successes += future.result(timeout=5) is True
                    except (WalletExecutorError, Q06ReadOnlyError):
                        pass
                self.assertEqual(successes, 1)
                write.assert_called_once()
            finally:
                executor.request('quit')
                self.assertTrue(executor.join(5))

    def test_backup_submission_requires_backend_owned_challenge(self):
        self.backend._secret = bytearray(PASSWORD)
        self.backend._seed_folder = self.root / ('bip39-12-' + 'a' * 32)
        with (patch('wam_regtest.bip39_seed_vault.read_seed_phrase', return_value=PHRASE),
              patch('wam_regtest.bip39_seed_vault._owner_binding', return_value='0' * 64),
              patch('wam_regtest.bip39_seed_vault.open_owned_seed_container') as opened,
              patch.object(self.backend, '_q06_write_ack') as write):
            opened.return_value.__enter__.return_value = self._fake_opened_keys()
            with self.assertRaises(Q06ReadOnlyError):
                self.backend.execute('backup_verify', ([1], [PHRASE.split()[0]]), {})
            write.assert_not_called()

    def test_lock_failure_erases_backend_password_without_discarding_session(self):
        from unittest.mock import Mock
        self.backend._secret = bytearray(PASSWORD)
        secret = self.backend._secret
        session = Mock()
        session.lock.side_effect = ValueError('PUBLIC_TEST_CLOSE_FAILURE')
        self.backend._spend_session = session
        with self.assertRaises(ValueError):
            self.backend._lock_q06()
        self.assertIsNone(self.backend._secret)
        self.assertEqual(secret, bytes(len(PASSWORD)))
        self.assertIs(self.backend._spend_session, session)
        self.assertFalse(self.backend._resume_spend)

    def test_unlock_resumes_previously_authorized_spend_only_after_reconciliation(self):
        self.backend._resume_spend = True
        opened = dict(backup_status='verified', receive_code='wamrtsp1public')
        verified = dict(signer_allowed=True, broadcast_allowed=True)
        with (patch.object(self.backend, '_reopen_q06', return_value=opened),
              patch.object(self.backend, '_activate_q06', return_value=verified) as activate):
            result = self.backend.execute('unlock', (PASSWORD, False), {})
        activate.assert_called_once_with()
        self.assertTrue(result['signer_allowed'])

    def test_unlock_without_prior_spend_consent_does_not_activate(self):
        with (patch.object(self.backend, '_reopen_q06', return_value={'backup_status':'verified'}),
              patch.object(self.backend, '_activate_q06') as activate):
            self.backend.execute('unlock', (PASSWORD, False), {})
        activate.assert_not_called()

    def setUp(self):
        import tempfile
        self.tmp=tempfile.TemporaryDirectory(prefix="q06-owner-unit-")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.owner=SimpleNamespace(directory=self.root,root=self.root)
        self.backend=Bip39ReadOnlyBackend(self.root,Path("/synthetic-core"),SOURCE)
        self.backend._core=lambda:self.owner

    def test_disposable_native_anchor_created_only_after_core_supervisor(self):
        # Regression for the macOS frozen failure: the old Q06 runner
        # precreated a .keychain-db under a fresh CoreSupervisor root, whose
        # empty-namespace protection correctly rejected the new profile.
        order=[]
        anchor=self.root/"q06-disposable.keychain-db"
        def init_owner():
            order.append("core_supervisor")
            return self.owner
        def create_anchor(root):
            self.assertEqual(root,self.root)
            order.append("native_keychain")
            return anchor
        self.backend=Bip39ReadOnlyBackend(
            self.root,Path("/synthetic-core"),SOURCE,
            _anchor_factory=create_anchor)
        self.backend._core=init_owner
        def create_seed(owner,source,password,phrase,*,authorized,keychain):
            self.assertTrue(authorized)
            self.assertEqual(keychain,anchor)
            order.append("sealed_seed")
            return (self.root/("bip39-12-"+("a"*32)),
                    {"profile":"q06","account_id":"test-account",
                     "receive_code":"wamrtsp1public"})
        with patch("wam_regtest.bip39_seed_vault.create_owned_seed_container",
                   side_effect=create_seed):
            result=self.backend.execute("open",(PASSWORD,"restore",PHRASE),{})
        self.assertEqual(order,["core_supervisor","native_keychain","sealed_seed"])
        self.assertEqual(result["status"],"Q06_REGTEST_READ_ONLY_OWNER_OPENED")
        self.assertTrue(self.backend._anchor_ready)
        self.backend.execute("lock",(),{})

    def test_funding_postcheck_uses_owned_read_after_fixture_closes_cli(self):
        from unittest.mock import Mock, call
        self.backend._secret=bytearray(PASSWORD)
        self.backend._public={"receive_code":"wamrtsp1public"}
        self.backend._seed_folder=self.root/("bip39-12-"+"a"*32)
        self.owner.cli=self.root/"wam-cli"  # mocked CLI entry, no binary executed
        self.owner.read=Mock()
        self.owner.read.call.return_value=102
        cli=Mock()
        cli.call.return_value=0  # fresh-chain precondition, BEFORE mining
        cli._transport=Mock()
        def funding(rpc, payment_code, address, record):
            self.assertIs(rpc,cli)
            self.assertEqual(payment_code,"wamrtsp1public")
            rpc._transport.close()  # the real shared fixture closes its transport
            return "a"*64, 150000, 102
        with (patch("wam_regtest.managed_wallet_checkpoint._owned") as ownership,
              patch("wam_regtest.wallet_session.WalletCoreCli",return_value=cli),
              patch("wam_regtest.wsp_live.public_regtest_mining_address",return_value="wamrt1public"),
              patch("wam_regtest.q05_checkpoint_scenario.fund_checkpoint_fixture",
                    side_effect=funding)):
            receipt=self.backend.execute("mine",(),{})
        self.assertEqual(receipt["status"],"Q06_REGTEST_PUBLIC_BIP39_RECEIVE_FUNDED")
        self.assertEqual(receipt["height"],102)
        self.assertEqual(cli.call.call_args_list,[call("getblockcount")])
        self.owner.read.call.assert_called_once_with("getblockcount")
        self.assertEqual(ownership.call_count,2)

    def test_gui_create_receipt_shows_exact_twelve_words_only_once(self):
        with (patch("wam_regtest.bip39_12.generate_phrase",return_value=PHRASE),
              patch("wam_regtest.bip39_seed_vault.create_owned_seed_container",
                    return_value=(self.root/("bip39-12-"+("0"*32)),{"profile":"q06",
                        "account_id":"public-identity","receive_code":"wamrtsp1public"}))):
            result=self.backend.execute("open",(PASSWORD,"create",""),{})
        self.assertEqual(result["mnemonic_once"],PHRASE)
        self.assertEqual(len(result["mnemonic_once"].split()),12)
        self.assertEqual(result["receive_code"],"wamrtsp1public")
        self.assertFalse(result["signer_allowed"])
        self.assertFalse(result["broadcast_allowed"])
        self.assertFalse(result["mainnet_allowed"])
        self.assertFalse(self.backend.public_state()["locked"])
        with self.assertRaises(Q06ReadOnlyError):
            self.backend.execute("sign",(),{})
        with self.assertRaises(Q06ReadOnlyError):
            self.backend.execute("broadcast",(),{})
        self.backend.execute("lock",(),{})
        self.assertTrue(self.backend.public_state()["locked"])
        self.assertIsNone(self.backend._secret)

    def test_import_existing_mnemonic_requires_explicit_new_profile(self):
        with patch("wam_regtest.bip39_seed_vault.create_owned_seed_container",
                   return_value=(self.root/("bip39-12-"+("f"*32)),{
                       "profile":"q06","account_id":"new-profile-account",
                       "receive_code":"wamrtsp1newprofile"})) as create:
            result=self.backend.execute("open",(PASSWORD,"restore",PHRASE),{})
        create.assert_called_once()
        self.assertEqual(create.call_args.args[3],PHRASE)
        self.assertEqual(result["mnemonic_once"],"")
        self.assertTrue(result["receive_code"].startswith("wamrtsp1"))
        self.backend.execute("lock",(),{})

    def test_existing_bip39_open_does_not_import_or_rewrite_seed(self):
        folder=self.root/("bip39-12-"+("a"*32))
        folder.mkdir()
        # Actual pinned WSP key derivation; native seed file read is test-patched.
        with patch("wam_regtest.bip39_seed_vault.open_owned_seed_container",
                   side_effect=lambda *a,**kw:Bip39Regtest12Keys(
                       PHRASE,source=SOURCE,authorized_disposable=True)):
            result=self.backend.execute("open",(PASSWORD,"reopen",""),{})
        self.assertEqual(result["mnemonic_once"],"")
        self.assertEqual(result["receive_code"],self.backend._public["receive_code"])
        self.assertEqual(self.backend._seed_folder,folder)
        self.backend.execute("lock",(),{})

    def test_native_spend_fault_reaches_executor_public_state(self):
        from types import SimpleNamespace
        self.backend._secret=bytearray(PASSWORD)
        self.backend._spend_session=SimpleNamespace(
            faulted=False, _q06_uncertain=False, locked=False,
            _core_reauthentication_required=False)
        self.assertEqual(self.backend.public_state()["faulted"],False)
        self.assertEqual(self.backend.public_state()["locked"],False)
        self.backend._spend_session._q06_uncertain=True
        self.assertEqual(self.backend.public_state()["faulted"],True)
        self.backend._spend_session._q06_uncertain=False
        self.backend._spend_session.faulted=True
        self.assertEqual(self.backend.public_state()["faulted"],True)
        self.backend._spend_session.faulted=False
        self.backend._spend_session.locked=True
        self.assertEqual(self.backend.public_state()["locked"],True)
        self.backend._spend_session._core_reauthentication_required=True
        self.assertEqual(self.backend.public_state()["reauthentication_required"],True)

    def test_read_only_post_reopen_txid_observation_never_mutates(self):
        from unittest.mock import Mock
        txid="a"*64
        history=(SimpleNamespace(txid=txid,confirmations=1),)
        session=Mock()
        session.faulted=False
        session._q06_uncertain=False
        session.locked=False
        session.snapshot.return_value=SimpleNamespace(history=history,height=108)
        session.inspect_confirmed.side_effect=lambda t:{
            "status":("Q06_CONFIRMED_IN_VERIFIED_HISTORY" if t==txid
                      else "Q06_TX_NOT_IN_CONFIRMED_HISTORY"),
            "txid":t, "write_attempted":False, "signer_allowed":False,
            "broadcast_allowed":False, "complete_anchored_history":True}
        self.backend._spend_session=session
        self.backend._secret=bytearray(PASSWORD)
        seen=self.backend.execute("inspect_confirmed",(txid,),{})
        self.assertEqual(seen["status"],"Q06_CONFIRMED_IN_VERIFIED_HISTORY")
        self.assertFalse(seen["write_attempted"])
        self.assertFalse(seen["signer_allowed"])
        self.assertFalse(seen["broadcast_allowed"])
        unknown=self.backend.execute("inspect_confirmed",("b"*64,),{})
        self.assertEqual(unknown["status"],"Q06_TX_NOT_IN_CONFIRMED_HISTORY")
        with self.assertRaises(Q06ReadOnlyError):
            self.backend.execute("inspect_confirmed",("mainnet",),{})
        session.faulted=True
        with self.assertRaises(Q06ReadOnlyError):
            self.backend.execute("inspect_confirmed",(txid,),{})
        self.assertEqual(session.inspect_confirmed.call_count,2)
        session.snapshot.assert_not_called()
        session.broadcast.assert_not_called()
        session.confirm_pending.assert_not_called()

    def test_guard_refuses_q05_profile_ambiguous_seeds_and_wrong_modes(self):
        with self.assertRaises(Q06ReadOnlyError):
            self.backend.execute("open",(PASSWORD,"mainnet",""),{})
        with self.assertRaises(Q06ReadOnlyError):
            self.backend.execute("open",(b"short","create",""),{})
        with self.assertRaises(Q06ReadOnlyError):
            self.backend.execute("open",(PASSWORD,"reopen",""),{})
        (self.root/"wallet-vault").mkdir()
        (self.root/("bip39-12-"+("b"*32))).mkdir()
        with self.assertRaises(Q06ReadOnlyError):
            self.backend.execute("open",(PASSWORD,"reopen",""),{})
        self.assertIsNone(self.backend._seed_folder)

    def _fake_opened_keys(self, generation=2):
        keys = Bip39Regtest12Keys(
            PHRASE, source=SOURCE, authorized_disposable=True)
        keys._q06_generation = generation
        return keys

    def test_create_marks_backup_status_required_and_can_verify_and_reopen(self):
        folder = self.root / ("bip39-12-" + ("0" * 32))
        with (patch("wam_regtest.bip39_12.generate_phrase", return_value=PHRASE),
              patch("wam_regtest.bip39_seed_vault.create_owned_seed_container",
                    return_value=(folder, {"profile": "q06",
                        "account_id": "public-identity",
                        "receive_code": "wamrtsp1public"}))):
            result = self.backend.execute("open", (PASSWORD, "create", ""), {})
        self.assertEqual(result["mnemonic_once"], PHRASE)
        self.assertEqual(result["seed_folder"], str(folder))
        self.assertEqual(result["backup_status"], "required")
        self.assertFalse(result["signer_allowed"])
        self.assertFalse(result["broadcast_allowed"])
        ack_path = self.root / "q06-gui-state" / "ack" / (folder.name + ".json")
        self.assertTrue(ack_path.exists())
        ack_data = json.loads(ack_path.read_text())
        self.assertFalse(ack_data["acknowledged"])
        self.assertTrue(ack_data["deferred"])

        words = PHRASE.split()
        challenge = self.backend.execute('backup_challenge', (), {})
        answers = [words[p - 1] for p in challenge['positions']]
        with (patch("wam_regtest.bip39_seed_vault.read_seed_phrase",
                    return_value=PHRASE),
              patch("wam_regtest.bip39_seed_vault._owner_binding",
                    return_value="0" * 64),
              patch("wam_regtest.bip39_seed_vault.open_owned_seed_container")
              as open_container):
            open_container.return_value.__enter__ = lambda *a, **kw: self._fake_opened_keys()
            open_container.return_value.__exit__ = lambda *a, **kw: None
            ok = self.backend.execute("backup_verify", (challenge['challenge_id'], answers), {})
        self.assertTrue(ok)
        self.assertTrue(ack_path.exists())
        self.assertTrue(json.loads(ack_path.read_text())["acknowledged"])
        self.assertTrue(json.loads(ack_path.read_text()).get("mac"))
        self.backend.execute("lock", (), {})
        self.assertTrue(self.backend.public_state()["locked"])

        folder.mkdir(parents=True)
        with patch("wam_regtest.bip39_seed_vault.open_owned_seed_container") as open_container:
            open_container.return_value.__enter__ = lambda *a, **kw: self._fake_opened_keys()
            open_container.return_value.__exit__ = lambda *a, **kw: None
            reopened = self.backend.execute("open", (PASSWORD, "reopen", ""), {})
        self.assertEqual(reopened["backup_status"], "verified")
        self.assertEqual(reopened["mnemonic_once"], "")
        self.assertTrue(reopened["receive_code"].startswith("wamrtsp1"))
        self.backend.execute("lock", (), {})

    def test_create_pending_marker_is_deferred_and_allows_reopen_verify(self):
        folder = self.root / ("bip39-12-" + ("0" * 32))
        with (patch("wam_regtest.bip39_12.generate_phrase", return_value=PHRASE),
              patch("wam_regtest.bip39_seed_vault.create_owned_seed_container",
                    return_value=(folder, {"profile": "q06",
                        "account_id": "public-identity",
                        "receive_code": "wamrtsp1public"}))):
            self.backend.execute("open", (PASSWORD, "create", ""), {})
        self.backend.execute("acknowledge_create_pending", (str(folder),), {})
        ack_path = self.root / "q06-gui-state" / "ack" / (folder.name + ".json")
        self.assertTrue(ack_path.exists())
        data = json.loads(ack_path.read_text())
        self.assertFalse(data["acknowledged"])
        self.assertTrue(data["deferred"])

        self.backend.execute("backup_defer", (), {})
        self.assertTrue(self.backend.public_state()["locked"])

        folder.mkdir(parents=True)
        with patch("wam_regtest.bip39_seed_vault.open_owned_seed_container") as open_container:
            open_container.return_value.__enter__ = lambda *a, **kw: self._fake_opened_keys()
            open_container.return_value.__exit__ = lambda *a, **kw: None
            reopened = self.backend.execute("open", (PASSWORD, "reopen", ""), {})
        self.assertEqual(reopened["backup_status"], "deferred")

        words = PHRASE.split()
        with (patch("wam_regtest.bip39_seed_vault.read_seed_phrase",
                    return_value=PHRASE),
              patch("wam_regtest.bip39_seed_vault._owner_binding",
                    return_value="0" * 64),
              patch("wam_regtest.bip39_seed_vault.open_owned_seed_container")
              as open_container):
            open_container.return_value.__enter__ = lambda *a, **kw: self._fake_opened_keys()
            open_container.return_value.__exit__ = lambda *a, **kw: None
            challenge = self.backend.execute('backup_challenge', (), {})
            self.assertFalse(self.backend.execute(
                "backup_verify", (challenge['challenge_id'], ["wrong"] * 3), {}))
            challenge = self.backend.execute('backup_challenge', (), {})
            self.assertTrue(self.backend.execute(
                "backup_verify", (challenge['challenge_id'],
                                  [words[p - 1] for p in challenge['positions']]), {}))
        self.assertTrue(json.loads(ack_path.read_text())["acknowledged"])

    def test_backup_verify_rejects_bad_inputs_and_locked_state(self):
        folder = self.root / ("bip39-12-" + ("0" * 32))
        with (patch("wam_regtest.bip39_12.generate_phrase", return_value=PHRASE),
              patch("wam_regtest.bip39_seed_vault.create_owned_seed_container",
                    return_value=(folder, {"profile": "q06",
                        "account_id": "public-identity",
                        "receive_code": "wamrtsp1public"}))):
            self.backend.execute("open", (PASSWORD, "create", ""), {})
        with self.assertRaises(Q06ReadOnlyError):
            self.backend.execute("backup_verify", ([0, 1], ["a", "b"]), {})
        with self.assertRaises(Q06ReadOnlyError):
            self.backend.execute("backup_verify", ([1, 1], ["a", "b"]), {})
        self.backend.execute("lock", (), {})
        with self.assertRaises(Q06ReadOnlyError):
            self.backend.execute("backup_verify", ([1, 2, 3], ["a", "b", "c"]), {})

    def _reopen_backend(self):
        """Simulate application restart with a fresh backend instance."""
        backend = Bip39ReadOnlyBackend(self.root, Path("/synthetic-core"), SOURCE)
        backend._core = lambda: self.owner
        return backend

    def test_generation2_missing_sidecar_fails_closed_after_restart(self):
        folder = self.root / ("bip39-12-" + ("0" * 32))
        folder.mkdir(parents=True)
        with patch("wam_regtest.bip39_seed_vault.open_owned_seed_container") as open_container:
            open_container.return_value.__enter__ = lambda *a, **kw: self._fake_opened_keys(2)
            open_container.return_value.__exit__ = lambda *a, **kw: None
            with self.assertRaises(Q06ReadOnlyError) as ctx:
                self.backend.execute("open", (PASSWORD, "reopen", ""), {})
        self.assertIn("BACKUP_ACK_REQUIRED", str(ctx.exception))
        self.assertTrue(self.backend.public_state()["locked"])

    def test_generation2_deleted_sidecar_fails_closed_after_restart(self):
        folder = self.root / ("bip39-12-" + ("0" * 32))
        folder.mkdir(parents=True)
        ack_path = self.root / "q06-gui-state" / "ack" / (folder.name + ".json")
        ack_path.parent.mkdir(parents=True, exist_ok=True)
        ack_path.write_text(json.dumps({"version": 1, "acknowledged": False,
                                        "deferred": True, "seed_id": folder.name}))
        ack_path.unlink()
        backend = self._reopen_backend()
        with patch("wam_regtest.bip39_seed_vault.open_owned_seed_container") as open_container:
            open_container.return_value.__enter__ = lambda *a, **kw: self._fake_opened_keys(2)
            open_container.return_value.__exit__ = lambda *a, **kw: None
            with self.assertRaises(Q06ReadOnlyError) as ctx:
                backend.execute("open", (PASSWORD, "reopen", ""), {})
        self.assertIn("BACKUP_ACK_REQUIRED", str(ctx.exception))

    def test_generation2_malformed_sidecar_fails_closed_after_restart(self):
        folder = self.root / ("bip39-12-" + ("0" * 32))
        folder.mkdir(parents=True)
        ack_path = self.root / "q06-gui-state" / "ack" / (folder.name + ".json")
        ack_path.parent.mkdir(parents=True, exist_ok=True)
        ack_path.write_text("not valid json")
        backend = self._reopen_backend()
        with patch("wam_regtest.bip39_seed_vault.open_owned_seed_container") as open_container:
            open_container.return_value.__enter__ = lambda *a, **kw: self._fake_opened_keys(2)
            open_container.return_value.__exit__ = lambda *a, **kw: None
            with self.assertRaises(Q06ReadOnlyError) as ctx:
                backend.execute("open", (PASSWORD, "reopen", ""), {})
        self.assertIn("BACKUP_ACK_TAMPERED", str(ctx.exception))

    def test_generation2_tampered_ack_mac_fails_closed_after_restart(self):
        folder = self.root / ("bip39-12-" + ("0" * 32))
        folder.mkdir(parents=True)
        ack_path = self.root / "q06-gui-state" / "ack" / (folder.name + ".json")
        ack_path.parent.mkdir(parents=True, exist_ok=True)
        ack_path.write_text(json.dumps({"version": 1, "acknowledged": True,
                                        "deferred": False, "seed_id": folder.name,
                                        "mac": "0" * 64}))
        backend = self._reopen_backend()
        with patch("wam_regtest.bip39_seed_vault.open_owned_seed_container") as open_container:
            open_container.return_value.__enter__ = lambda *a, **kw: self._fake_opened_keys(2)
            open_container.return_value.__exit__ = lambda *a, **kw: None
            with self.assertRaises(Q06ReadOnlyError) as ctx:
                backend.execute("open", (PASSWORD, "reopen", ""), {})
        self.assertIn("BACKUP_ACK_TAMPERED", str(ctx.exception))

    def test_generation2_replaced_sidecar_for_wrong_seed_fails_closed(self):
        folder = self.root / ("bip39-12-" + ("0" * 32))
        folder.mkdir(parents=True)
        other_folder = self.root / ("bip39-12-" + ("f" * 32))
        ack_path = self.root / "q06-gui-state" / "ack" / (folder.name + ".json")
        ack_path.parent.mkdir(parents=True, exist_ok=True)
        # Sidecar claims acknowledgement but names a different seed_id.
        ack_path.write_text(json.dumps({"version": 1, "acknowledged": True,
                                        "deferred": False, "seed_id": other_folder.name,
                                        "mac": "0" * 64}))
        backend = self._reopen_backend()
        with patch("wam_regtest.bip39_seed_vault.open_owned_seed_container") as open_container:
            open_container.return_value.__enter__ = lambda *a, **kw: self._fake_opened_keys(2)
            open_container.return_value.__exit__ = lambda *a, **kw: None
            with self.assertRaises(Q06ReadOnlyError) as ctx:
                backend.execute("open", (PASSWORD, "reopen", ""), {})
        self.assertIn("BACKUP_ACK_TAMPERED", str(ctx.exception))

    def test_generation1_missing_sidecar_remains_grandfathered(self):
        folder = self.root / ("bip39-12-" + ("0" * 32))
        folder.mkdir(parents=True)
        with patch("wam_regtest.bip39_seed_vault.open_owned_seed_container") as open_container:
            open_container.return_value.__enter__ = lambda *a, **kw: self._fake_opened_keys(1)
            open_container.return_value.__exit__ = lambda *a, **kw: None
            result = self.backend.execute("open", (PASSWORD, "reopen", ""), {})
        self.assertEqual(result["backup_status"], "verified")
        self.assertTrue(result["receive_code"].startswith("wamrtsp1"))
        self.backend.execute("lock", (), {})


if __name__ == "__main__":
    unittest.main()
