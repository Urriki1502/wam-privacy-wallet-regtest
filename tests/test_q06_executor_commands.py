"""Q06 owner-executor command admission regression; no Core/signing involved.

The executor must accept Q06's explicit activation and bounded CI command,
but arbitrary RPC/seed actions must remain refused. Backend authorization is
a separate fail-closed gate and this test does not grant spending.
"""
import unittest
from wam_regtest.wallet_executor import WalletExecutor, WalletExecutorError, COMMANDS


class FakeBoundedQ06Backend:
    def __init__(self):
        self.calls = []

    def execute(self, action, args, kwargs):
        self.calls.append((action, args, kwargs))
        if action == "activate":
            if args or kwargs:
                raise ValueError("Q06_GUI_ACTIVATE_ARGUMENTS_DENIED")
            return {"activated": False, "mainnet_allowed": False}
        if action == "ci_confirm":
            if args or kwargs:
                raise ValueError("Q06_GUI_CONFIRM_CI_ARGUMENTS_DENIED")
            return {"ci_only": True}
        if action == "quit":
            return None
        raise ValueError("Q06_GUI_SPENDING_NOT_IMPLEMENTED")

    def public_state(self):
        return {"locked": True, "faulted": False, "core_alive": False}


class Q06ExecutorCommandAdmission(unittest.TestCase):
    def test_activation_and_ci_confirmation_reach_only_bound_backend(self):
        self.assertTrue({"activate", "ci_confirm"}.issubset(COMMANDS))
        self.assertNotIn("sendrawtransaction", COMMANDS)
        self.assertNotIn("sign_raw", COMMANDS)
        backend = FakeBoundedQ06Backend()
        executor = WalletExecutor(lambda: backend)
        try:
            self.assertEqual(executor.request("activate")["activated"], False)
            self.assertFalse(executor.request("activate")["mainnet_allowed"])
            self.assertEqual(executor.request("ci_confirm")["ci_only"], True)
            self.assertEqual([call[0] for call in backend.calls],
                             ["activate", "activate", "ci_confirm"])
            with self.assertRaises(WalletExecutorError):
                executor.request("sendrawtransaction", "deadbeef")
            self.assertEqual(len(backend.calls), 3)
        finally:
            executor.request("quit")
            self.assertTrue(executor.join(5))
            self.assertTrue(executor.closed)

    def test_generic_backend_refuses_unsafe_q06_parameters(self):
        backend = FakeBoundedQ06Backend()
        executor = WalletExecutor(lambda: backend)
        try:
            with self.assertRaises(WalletExecutorError):
                executor.request("activate", True)
            with self.assertRaises(WalletExecutorError):
                executor.request("ci_confirm", "mainnet")
            self.assertEqual([call[0] for call in backend.calls],
                             ["activate", "ci_confirm"])
        finally:
            executor.request("quit")
            self.assertTrue(executor.join(5))


if __name__ == "__main__":
    unittest.main()
