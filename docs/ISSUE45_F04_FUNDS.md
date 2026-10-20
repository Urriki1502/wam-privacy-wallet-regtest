# F-04 — Core mining-account funds classification (REGTEST only)

**Issue #45 / F-04 [P0].** This Draft PR is stacked on F-03.
The objective is **no phantom balances**: do not treat confirmed,
trusted, available, immature, Core-locked, WSP-reserved and off-chain
pool-owed value as interchangeable categories.

## Existing Core read model

An existing, separately attested owned REGTEST miner wallet already
supplies independent Core wallet `getbalances.mine` fields:
`trusted`, `untrusted_pending`, `immature`. The read-only UTXO
layer uses authenticated `listunspent`, verified wallet address
ownership and Core `gettxout`; it counts as *available* only Core
safe/spendable/solvable eligible outputs, including the first coinbase
only after depth 101.

`trusted` is **not** an assertion of final chain confirmation and
may include trusted unconfirmed change. Confirmed WSP scanner amounts
are a *different account*, never added to this miner wallet.

## New explicit Core lock accounting

`src/wam_regtest/f04_funds.py` evaluates actual read-only
`listlockunspent` outpoints against `gettxout` values and a
Core-confirmed wallet-owned script:

- Check each outpoint's txid/vout, unique membership, no overlap
  with Core `listunspent` outputs, exact decimal atoms and maturity.
- Exclude treasury or unrelated scripts. A Core lock is neither an
  irreversible signed WSP reservation nor off-chain pool credit.
- Compute `available`, `locked_core`, `immature`, `untrusted_pending`,
  `trusted`, and `unattributed_trusted` **separately**. Any
  positive trusted amount not attributed by explicit Core UTXOs stays
  *unknown* — never implicitly called reserved/locked/spendable.
- Strictly refuse negative or inflated accounting, malformed
  outpoints, duplicate locks, foreign outputs or coinbase below maturity.

## Genuine native Core proof

The existing immutable disposable WAM Core v0.1.11 REGTEST fixture
generates coins, matures the first coinbase, sends a legitimate
fee-paying transaction to a public test address, then confirms it.
It already performs a local `lockunspent(false,...)` and
`lockunspent(true,...)` cycle on an independently owned Core change
output. F-04 adds explicit `listlockunspent` and `gettxout`
verification after the lock:

- Before locking, Core explicitly lists **no** coin locks, and
  Core `available` contains the eligible change amount.
- After lock, the exact outpoint appears in `listlockunspent`.
  `available = 0` while the amount is identified in
  `locked_core`; `trusted` must not change.
- After unlocking **only the disposable fixture output**, Core's
  coin-lock list is empty and the original eligible balance returns.
- Native Linux, macOS and Windows workflow receipts must assert this
  sequence. Mocked Core RPC values are UNIT only, never real E2E.

## Boundaries not accepted by this PR

Core listlockunspent can prove an explicit Core coin lock, but **not**
a WSP signer reservation, an RPC-uncertain broadcast, or an
external miner/pool amount owed off chain. Never derive those from
`trusted − available`. These remain separate, unresolved P0
integration and physical-host release gates unless an independent
real-Core/WSP acceptance proves them.

No external/core wallet access, owner seed, mainnet network, real
signing authority, ledger reconciliation release, auto-unlock or
physical cross-OS restore is authorized. No merge without owner
approval. Exact-HEAD native CI must be complete before the engineering
gate may be marked PASS.
