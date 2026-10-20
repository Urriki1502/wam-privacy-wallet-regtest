# F-10 — Solo-miner coexistence: bounded owned-Core qualification

Issue #45 / Phase F / F-10 [P0]. One Draft PR stacked on F-09 #100.

**Do not confuse this short Core mining fixture with a native end-to-end
external `wam-miner` process on the same node.** F-10 retains that
independent P0 acceptance as PENDING until the miner executable itself
participates in the test and reports matching real blocks.

## Initial native proof now implemented

Run only after the signed/developer v0.1.11 WAM Core REGTEST
`mining_probe` has confirmed a freshly owned isolated node,
its wallet, original genesis, source identity and acceptance
config. The new proof runs inside the SAME disposable, separately
authenticated node with no external peers or mainnet wallet.

- Start a real authenticated `waitfornewblock` request in a
  bounded worker for each of four successive new REGTEST blocks.
- Run actual Core `generatetoaddress` against the node's existing
  PUBLIC, non-user fixture address; each accepted block must match
  the long-poll response's exact hash and height.
- In parallel with owned-Core mining activity, the existing
  authenticated, persistent, read-only wallet transport checks
  `getblockchaininfo`, `getblockcount`, and `getbestblockhash`
  after each block (12 independent verified reads).
- Recheck the disposable Core wallet's identity and descriptor
  format without creating, unlocking, transferring or importing
  money. No external node restart, process kill, `wam.conf` edit,
  external peers, mining interruption or ordinary-user Send RPC.
- Hash the original private **disposable fixture** `wam.conf`;
  check the checksum after every round and at completion. Owner
  RPC settings are never edited or inspected.
- Refuse wrong hashes, heights, source network, tip drift, wallet
  substitution, config modifications, missing miner response
  and runner deadlines. All checks use real Core RPC in native E2E.
- Four Core mining events and at least four long-poll witnesses
  with verified tip are required, budget 100 seconds. The
  source contract's synthetic response tests NEVER count as
  miner/Core E2E acceptance.

## Node RPC queue and source/operator limits

The existing T-07 native Core workload independently saturated
the default 16-slot queue using 32 concurrent public
`waitfornewblock` clients and observed actual HTTP 503, bounded
read retry and recovery **without restarting Core**. F-10 does not
modify that previous result or silently raise the limit.

The optional `rpcworkqueue=64` tuning is **operator-controlled**
and needs a separately consented fresh test node/config plus 64+
simultaneous requests and observed wallet/miner fairness. This
PR does not alter `wam.conf`, Core `rpcthreads`, miner settings,
HTTP transport, wallet fallback or an external node. Therefore:
`f10_operator_rpcworkqueue_64_qualified=false`.

Likewise, Core's own `generatetoaddress` is a real REGTEST
block producer but is **not a native compiled `wam-miner` binary**
using `getblocktemplate` and `submitblock`. The executable
miner/GUI cross-process coexistence gate, real submitted share or
block and queue fairness remain **PENDING**:
`f10_native_external_solo_miner_qualified=false`.

## Treasury sunset hypothesis — upstream source, NOT a proven defect

Read-only published v0.1.11 upstream pins:

- `src/wam/wam-params.h` Git blob
  `d798155e1964adbdb3ccc48b44dd48fcde3b1602`: treasury last
  height 400000 inclusive.
- `src/wam/chainparams.cpp` Git blob
  `6e7eebfec5483f99ed13849a9b22cd502781364f`: consensus
  uses that cutoff for main/test/REGTEST.
- `miner/src/solo_template.h` Git blob
  `192fd389f2c0588ca93022a6f5402a35b15d9f5f`:
  its `BuildSoloTemplate()` reconstructs `expected =
  (subsidy * 5) / 100` when transaction fees are known, without
  a height-based treasury sunset branch in that local check.

This is a **source-level compatibility risk**, not runtime proof
of an invalid miner block. Actual expected behavior near
400000/400001 must account for WAM regtest's 150-block halving,
where block subsidy has already reached zero at height 4951.
An artificial positive-subsidy Core/mempool fixture or authorized
deterministic appropriate binary environment is needed for
meaningful miner-vs-Core acceptance at the mainnet cutoff.
Do not generate 400001 blocks on CI, patch upstream consensus,
announce a confirmed upstream bug, or use real user mining keys.

`f10_sunset_400001_miner_binary_qualified=false`.

## Completion conditions

Exact PR HEAD four workflows must PASS (Linux, signed macOS,
signed Windows, canonical BIP352), including genuine per-platform
Core mining and authenticated wallet read receipts.
Nevertheless complete F-10 P0 remains PENDING until all external
miner, queue64 operator and sunset acceptance tests above obtain
their own reproducible observations and DEV review.

Keep Draft, no force-push, no merge, no extra branch for F-10.
