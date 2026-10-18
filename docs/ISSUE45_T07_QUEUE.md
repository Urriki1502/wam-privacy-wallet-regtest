# Issue #45 — T-07 RPC queue contention and retry

T-07 is a **REGTEST-only backpressure change** to the existing direct HTTP RPC
and persistent Fusion Core supervisor, not a separate queue framework.

## Existing safety controls reused

- The authenticated, bounded `ManagedReadRpc` session already retries **at
  most 3 times** for a *positively rejected* HTTP 503 / `RPC_NODE_BUSY`
  idempotent read, with bounded exponential jitter (existing real-Core queue
  saturation proof in `rpc_contention_probe.py`).
- Authentication failures, malformed replies, changed config, uncertain
  connection failures and RPC writes are never silently retried.
- `sendrawtransaction` is an independently authorized WSP operation, with
  irreversible signed/uncertain reservations persisted before submitting.
  A lost reply **cannot** auto-rebroadcast or free the reserved UTXO.

## Missing operator-facing backpressure now implemented

A `CoreSupervisor.status()` call used to issue a new full Core attestation
on every subsequent GUI/status/scan request even after a genuine Core busy
response. This could pile up work against a saturated RPC worker queue.

After **only a confirmed `RPC_NODE_BUSY`**, the supervisor records a bounded
12-second *monotonic* cooling-off window. Within that interval it:

1. **Always checks native Core process/image ownership**. An exited or
   replaced process transitions to `recovery-needed`; it is never reported as
   an authenticated, owned Core merely because an earlier busy state existed.
2. Returns only `busy` and `core_process_owned=true` with **no height, tip,
   wallet balance, transaction or other stale blockchain observation**.
3. Performs **zero additional Core HTTP requests** until the interval expires.
   Existing scanner/spend methods refuse while Core is busy. No signer/
   broadcast retry or Core stop/restart follows from this cooldown.
4. Reattests against the real chain after the interval; successful attestation
   clears the busy state, and any non-503 error fails closed.

Fusion's managed GUI displays `NODE BUSY · RETRYING` and lengthens *periodic*
status refresh from five to fifteen seconds while busy, resetting it on
verified recovery. Its already existing single-worker guard coalesces
in-flight GUI status refresh. No wallet is unlocked or accepted on a busy
status.

## Explicit limits, acceptance and separate roles

The previous genuine Core 32-client queue saturation / idle-reconnect test
still proves that WAM Core v0.1.11 really rejects requests with 503 and the
shared read transport recovers. New T-07 unit and native Qt tests verify
supervisor/UI cooldown behavior, fail-closed wrong-process/exit handling and
absence of extra status reads while busy. Real-Core and frozen three-OS
regressions remain mandatory on the exact PR head; unit success by itself is
**not** a full P0 or physical acceptance.

The normal REGTEST `wam.conf` is not mutated. Upstream-provided operator
settings `rpcworkqueue=64` or `rpcthreads=4` may be discussed as manual
guidance on separately approved nodes; they are **not** automatically applied
here, and the managed Core's exact validated profile is unchanged. No
external/mainnet miner is attached or stopped, and no data is deleted to
resolve contention. Runtime limits under an indefinitely busy Core remain
pending real long-duration/operator acceptance.
