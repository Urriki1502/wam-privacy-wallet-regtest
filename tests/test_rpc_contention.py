"""Unit tests for Q04 RPC contention handling."""
import time
import unittest

from wam_regtest.rpc_contention import (
    BackoffPolicy, ReadCoalescer, ContentionAwareRpc, RpcContentionError)


class RpcContentionContracts(unittest.TestCase):
    def test_backoff_bounds(self):
        policy = BackoffPolicy(base_seconds=0.1, max_seconds=1.0, max_retries=3)
        delays = [policy.delay(i) for i in range(3)]
        self.assertLess(delays[0], delays[1])
        self.assertLessEqual(delays[1], delays[2])
        self.assertLessEqual(delays[2], 1.0)

    def test_backoff_exhausted(self):
        policy = BackoffPolicy(max_retries=1)
        policy.delay(0)
        with self.assertRaises(RpcContentionError):
            policy.delay(1)

    def test_coalescer_marks_busy(self):
        c = ReadCoalescer(cooldown_seconds=1.0)
        c.mark_busy()
        self.assertTrue(c.is_busy())
        time.sleep(1.1)
        self.assertFalse(c.is_busy())

    def test_contention_aware_rpc_retries_then_busy(self):
        call_count = [0]

        def failing_read(method, params):
            call_count[0] += 1
            raise RuntimeError('RPC_CORE_WARMUP')

        rpc = ContentionAwareRpc(failing_read, policy=BackoffPolicy(
            base_seconds=0.01, max_seconds=0.1, max_retries=2, jitter=0.1))
        with self.assertRaises(RpcContentionError) as ctx:
            rpc.read('getblockcount')
        self.assertEqual(ctx.exception.args[0], 'RPC_NODE_BUSY')
        self.assertGreaterEqual(call_count[0], 3)

    def test_contention_aware_rpc_no_retry_on_non_busy(self):
        call_count = [0]

        def failing_read(method, params):
            call_count[0] += 1
            raise RuntimeError('SOME_OTHER_ERROR')

        rpc = ContentionAwareRpc(failing_read, policy=BackoffPolicy(
            base_seconds=0.01, max_seconds=0.1, max_retries=2))
        with self.assertRaises(RuntimeError):
            rpc.read('getblockcount')
        self.assertEqual(call_count[0], 1)


if __name__ == '__main__':
    unittest.main()
