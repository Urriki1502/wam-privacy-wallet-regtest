"""CDX-AUD-002: base (legacy/headless) WalletSession.lock must not stop early.

Each resource close is attempted independently; signing/password references
are dropped even when one close fails; the session latches faulted, keeps
the runtime for review and refuses unlock/signing. Python cannot zeroize
every copy of a secret: this only removes this session's references.
Public dummy password, no Core, no seed, no wallet profile.
"""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

PASSWORD = b"PUBLIC_TEST_PASSWORD_CDX002"


class _Closable:
    def __init__(self, log, name, fail=False):
        self.log, self.name, self.fail = log, name, fail

    def close(self):
        self.log.append(self.name)
        if self.fail:
            raise OSError("PUBLIC_" + self.name.upper() + "_CLOSE_FAULT")


class LegacyLockCleanup(unittest.TestCase):
    def _session(self, fail=None):
        from wam_regtest.wallet_session import WalletSession
        temp = tempfile.TemporaryDirectory(prefix="cdx002-")
        self.addCleanup(temp.cleanup)
        base = Path(temp.name)
        self.runtime = base / "wallet-runtime.sqlite"
        self.runtime.write_bytes(b"public runtime placeholder")
        self.log = []
        scanner = _Closable(self.log, "scanner", fail == "scanner")
        scanner.store = SimpleNamespace(path=self.runtime)
        ring = _Closable(self.log, "ring", fail == "ring")
        from contextlib import nullcontext
        vault = SimpleNamespace(anchor=SimpleNamespace(lease=lambda: nullcontext()))
        session = WalletSession(base, base, base, ring, scanner, vault, PASSWORD, None)
        transport = _Closable(self.log, "rpc", fail == "rpc")
        session._rpc_client = SimpleNamespace(_transport=transport)
        session._disclosure_gate = _Closable(self.log, "disclosure", fail == "disclosure")
        session._prepared = session._signed = session._review = session._tip = object()
        return session

    def _assert_invalidated(self, session):
        self.assertIsNone(session.ring)
        self.assertIsNone(session.scanner)
        self.assertIsNone(session._password)
        self.assertIsNone(session._signed)
        self.assertIsNone(session._prepared)
        self.assertIsNone(session._review)
        self.assertIsNone(session._disclosure_gate)
        self.assertIsNone(session._rpc_client)
        self.assertTrue(session.locked)

    def test_each_single_close_fault_still_invalidates_and_latches(self):
        from wam_regtest.wallet_session import WalletSessionError
        for fail in ("scanner", "ring", "disclosure", "rpc"):
            with self.subTest(fault=fail):
                session = self._session(fail)
                with self.assertRaises(WalletSessionError) as caught:
                    session.lock()
                self.assertEqual(caught.exception.args, ("WALLET_LOCK_CLEANUP_UNCERTAIN",))
                self.assertEqual(sorted(self.log), ["disclosure", "ring", "rpc", "scanner"])
                self._assert_invalidated(session)
                self.assertTrue(session.faulted)
                self.assertTrue(self.runtime.exists())  # preserved, never unlinked
                with self.assertRaisesRegex(WalletSessionError, "WALLET_LOCKED_OR_FAULTED"):
                    session._rpc()
                with self.assertRaisesRegex(WalletSessionError, "WALLET_LOCK_CLEANUP_UNCERTAIN"):
                    session.unlock(PASSWORD)
                with self.assertRaises(WalletSessionError):
                    session.sign("0" * 64)
                session.lock()  # idempotent; no second cleanup attempt
                self.assertEqual(len(self.log), 4)

    def test_normal_lock_unchanged(self):
        session = self._session()
        session.lock()
        self.assertEqual(sorted(self.log), ["disclosure", "ring", "rpc", "scanner"])
        self._assert_invalidated(session)
        self.assertFalse(session.faulted)
        self.assertFalse(self.runtime.exists())
        session.lock()
        self.assertEqual(len(self.log), 4)

    def test_error_text_is_fixed_and_contains_no_exception_payload(self):
        from wam_regtest.gui_errors import error_text, operation_error
        from wam_regtest.wallet_session import WalletSessionError
        session = self._session("scanner")
        try:
            session.lock()
        except WalletSessionError as error:
            self.assertIsNone(error.__cause__)
            self.assertTrue(error.__suppress_context__)
            code = operation_error("lock", error)
        self.assertEqual(code, "WALLET_LOCK_CLEANUP_UNCERTAIN")
        self.assertNotIn("PUBLIC_", error_text(code))


if __name__ == "__main__":
    unittest.main()
