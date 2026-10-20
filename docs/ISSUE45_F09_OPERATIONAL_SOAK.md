# F-09 — Persistent operational acceptance (bounded native phase)

Issue #45 / Phase F / F-09 [P0]. One Draft PR stacked on #99 F-08.
REGTEST and pinned WAM Core v0.1.11 only. This is NOT a claim that the
wallet is ready for production, runs stably for days, or survives every
resource-pressure scenario.

## Versioned native smoke budget: F09_V1_64_CYCLES_180S

Runs on the already **authenticated, disposable, owned native Core**
after its genuine mining/UTXO/fee/transaction fixture reaches final
REGTEST height. There is no mock Core, external daemon, mainnet node,
external peer or imported wallet in this native proof.

| Measured assertion | Budget |
| --- | --- |
| Sequential observation rounds | exactly 64 |
| Authenticated read-only Core RPC calls | exactly 192 |
| RPC methods in each round | getblockchaininfo, getblockcount, getbestblockhash |
| Initial network identity | getblockhash(0), exact WAM REGTEST genesis |
| Stable Core tip | height & bestblockhash agree for every round |
| Per-round latency | no more than 12 wall-clock seconds |
| Total continuous read loop | no more than 180 wall-clock seconds |
| Write RPC / Core restart / wallet unlock during loop | 0 |
| New peer connection during fixture | 0 (reasserted at end) |
| Long-run qualification | false until separately evidenced |

The native probe records actual duration and maximum round latency in
milliseconds. A busy/faulted node, RPC timeout, non-regtest response,
height/tip drift, unavailable Core, or request exceeding the threshold
must **fail**; it cannot be silently called a good soak. No rerun,
wallet unlock, user key, synthetic balance or implicit node restart
is performed as error recovery.

The above read loop is a **bounded, short** stress/continuity gate
that every pinned Core platform must pass before claiming F-09 code
integration. Source-level unit tests exercise malformed responses,
wrong chain, changes in tip/height, 503/busy, late responses, invalid
timing/cycle-budget arguments and the exact read-method allowlist.
They are **not** an actual native Core endurance result.

## Full F-09 qualification matrix — still PENDING

The following failures and time windows require a **separate native
execution and saved, redacted measurement receipts**, not a new
boolean asserted in docs or unit tests:

- **Hours/days continuous source + frozen run**: real elapsed wall
  time, repeated Core/WSP reopen, baseline/final RSS/FD/handle counts
  and memory/CPU trend, no leaked resources or stolen Core lock.
- **Large confirmed WSP history and long rescans**: actual
  generated blocks/history at multiple scales, throughput and
  percentiles, persisted SQLite checkpoint integrity and
  correct wallet balance/credits/debits after restart/reorg.
- **Multiple independently operated peer nodes**: true peer
  connectivity, sync/fork/reconciliation, ownership of only the
  managed Core and no interruption to a separate miner.
- **Database schema upgrades**: tested upgrade and rollback refusal
  from each supported real previous version; no auto-migration
  of imported keys or older BDB.
- **Fault injection**: crash during sync, low disk and atomic
  write failure, CPU/RSS pressure, slow RPC, partitions, reorgs
  and daemon busy saturation; fail closed with correct custody
  checkpoints and no duplicate broadcast/reservation release.
- **Responsive GUI and frozen binaries**: empirically observed
  3-platform event-loop responsiveness, render timing on large
  histories, clean restart/close, stable process/resource budget
  over sustained runtime and physical HiDPI review.

All remain **PENDING_OPERATOR/DEV** until actual hours/days tests,
large histories, cross-node environments or fault-injection
workloads have completed. Short Core RPC stability is only an
initial acceptance increment, not global F-09 completion.

## Boundaries

No real wallet keys, mainnet, arbitrary miner/node shutdown,
external configuration edits, database migration, incoming network
peer creation, automatic signer authority, auto-broadcast or
reservations unlock. No original wallet data is modified.

Exact F-09 HEAD: require the native Linux x86_64, macOS ARM64,
Windows x64 Core workflows **and** BIP352 vectors green.
Keep this PR Draft; do not merge automatically.
