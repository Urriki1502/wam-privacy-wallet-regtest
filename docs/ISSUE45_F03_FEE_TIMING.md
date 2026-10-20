# F-03 — WAM block timing, relay fees and actual Core fee policy

Issue #45 / Phase F / F-03 [P0]. One Draft PR stacked directly on
F-02 PR #93. No signing, release, mainnet connection, real user mining
wallet or external-node mutation authorized by this document.

## Target block interval

The reviewed v0.1.11 upstream `src/wam/wam-params.h` Git blob
`d798155e1964adbdb3ccc48b44dd48fcde3b1602` defines
`WAM_POW_TARGET_SPACING = 120` seconds. The matching
`src/wam/chainparams.cpp` Git blob
`6e7eebfec5483f99ed13849a9b22cd502781364f` applies it
to consensus `nPowTargetSpacing` on main/test/regtest. The existing
native-compiled pinned C++ source contract explicitly checks 120.
It is a TARGET, not a guaranteed confirmation schedule or an
observed network ETA. No Bitcoin 600-second interval is inherited
by UI or test calculations.

## Core-observed fee evidence

The unchanged authorized isolated REGTEST miner fixture creates a
mature owned UTXO, spends **0.001 WAM** to a public test address,
and independently obtains the wallet transaction's **exact fee atoms**
before generating the confirmation block.

While the transaction is genuinely in the Core mempool, the new
`CoreFeeWitness` reads:

- `getnetworkinfo.relayfee` (WAM per kilobyte)
- `getmempoolinfo.mempoolminfee` (WAM per kilobyte)
- `getmempoolentry(txid).vsize` (integer virtual bytes)
- `getmempoolentry(txid).fees.base` (WAM from actual accepted TX)
- Owned wallet `gettransaction(txid).fee`, converted to integer atoms

Check the *same* fee from Core wallet and mempool, compare against the
maximum relay/mempool floor as `ceil(rate_atoms_per_kvB * vsize / 1000)`,
bound the fee to the existing maximum **0.01 WAM** (1,000,000 atoms),
and retain all values in exact integer atoms. The per-kvB rate is NOT
a per-transaction absolute fee, and `vsize` is not a Bitcoin 10-minute
confirmation estimate.

The actual REGTEST Core also attempts a deliberately subdust
**one-atom** send at coinbase maturity depth 101. Core must reject it
with no mempool or wallet-balance mutation before the separately
verified valid payment succeeds. This proves that test node's very
small output rejection; it does **not** certify the exact dust
threshold for every script type, mempool condition or Core release.

`estimatesmartfee(2)` may lack historical samples on an isolated
REGTEST node. When unavailable, the receipt explicitly marks
`f03_estimate_available=false` and does NOT substitute configured
`fallbackfee` as a genuine observed estimate. When Core returns a
fee rate, it is parsed into exact integer atoms per kvB. Neither
case promises a 2-block/4-minute confirmation deadline.

## WSP intent/amount/change boundaries

The test WalletSession coordinator now independently rejects
non-integer amounts/fees, amounts below its supported minimum,
fees outside 1..1,000,000 atoms and combinations above the WAM
maximum supply before preparing a transaction. After selecting
actual WSP coins but *before native signing*, it checks exact
`sum(inputs) >= amount + fee`, deriving change by subtraction
with no floats. A positive change output still requires actual
Core policy checking in the existing send/mempool pipeline; a
minimum integer-amount bound alone is NOT proof of a standard
change script or safe output policy.

## Acceptance status

- Unit: rate/size/floor, exact arithmetic, estimator absence,
  impossible amount+fee and WAM timing tests.
- Native Core E2E: genuine isolated wallet payment fee must match
  genuine mempool vsize/base fee; one-atom subdust send refused
  without state mutation; three platform workflows assert both.
- Source proof: pinned 120-second WAM consensus source constant.
- Not claimed: future fee estimation reliability, all script dust
  shapes, mainnet network conditions, arbitrary user wallet
  transactions, guaranteed confirmations or production release.
- Frozen physical WSP portability/reservation and unrelated
  F-04 money classification remain independent P0 gates.

Only record F-03 CI as green after all workflows finish
successfully on the exact final F-03 branch HEAD.
