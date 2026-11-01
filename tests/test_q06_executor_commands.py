"""Q06 owner-executor command admission regression; no Core/signing involved.

The executor must admit only named Q06 commands; exact transaction authority
and mnemonic read-only verification remain enforced by the bound Q06 backend.
A generic backend cannot silently acquire these operations.
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
        if action == "confirm":
            if args != ("a"*64,) or kwargs:
                raise ValueError("Q06_CONFIRM_EXACT_PENDING_TX_REQUIRED")
            return {"status": "Q06_REGTEST_EXACT_SEND_CONFIRMED", "mainnet_allowed": False}
        if action == "recovery_verify":
            if args != ("disposable test words only",) or kwargs:
                raise ValueError("Q06_GUI_RECOVERY_PROOF_ARGS_DENIED")
            return {"status": "Q06_SAME_CHAIN_BIP39_HISTORY_RESCAN_PASS",
                    "signer_allowed": False}
        if action == "quit":
            return None
        raise ValueError("Q06_GUI_SPENDING_NOT_IMPLEMENTED")

    def public_state(self):
        return {"locked": True, "faulted": False, "core_alive": False}


class Q06ExecutorCommandAdmission(unittest.TestCase):
    def test_q06_bounded_commands_reach_only_bound_backend(self):
        self.assertTrue({"activate", "ci_confirm", "confirm",
                         "recovery_verify"}.issubset(COMMANDS))
        self.assertNotIn("sendrawtransaction", COMMANDS)
        self.assertNotIn("sign_raw", COMMANDS)
        backend = FakeBoundedQ06Backend()
        executor = WalletExecutor(lambda: backend)
        try:
            self.assertEqual(executor.request("activate")["activated"], False)
            self.assertFalse(executor.request("activate")["mainnet_allowed"])
            self.assertEqual(executor.request("ci_confirm")["ci_only"], True)
            self.assertEqual(executor.request("confirm", "a"*64)["status"],
                             "Q06_REGTEST_EXACT_SEND_CONFIRMED")
            recovery=executor.request("recovery_verify", "disposable test words only")
            self.assertEqual(recovery["status"], "Q06_SAME_CHAIN_BIP39_HISTORY_RESCAN_PASS")
            self.assertIs(recovery["signer_allowed"], False)
            self.assertEqual([call[0] for call in backend.calls],
                             ["activate", "activate", "ci_confirm",
                              "confirm", "recovery_verify"])
            with self.assertRaises(WalletExecutorError):
                executor.request("sendrawtransaction", "deadbeef")
            self.assertEqual(len(backend.calls), 5)
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
            with self.assertRaises(WalletExecutorError):
                executor.request("confirm", "b"*64)
            with self.assertRaises(WalletExecutorError):
                executor.request("recovery_verify", "unknown phrase")
            self.assertEqual([call[0] for call in backend.calls],
                             ["activate", "ci_confirm", "confirm", "recovery_verify"])
        finally:
            executor.request("quit")
            self.assertTrue(executor.join(5))


if __name__ == "__main__":
    unittest.main()
