# DEV WAM finding — REGTEST treasury comment contradicts the assigned address

Component: WAM Core v0.1.13, `src/wam/chainparams.cpp`
Upstream tag commit: `b3fb899ddb1ceab7e9b3b12ccd034ad1b4be8186`
File verified: Git blob `6081d8259d16513b1857ac893d21651a1400608e`,
sha256 `7189dd77bb3a9a2e04b35512861b5dc946b83ee951336af060df7224c47833d3`
Severity: documentation/clarity (no consensus or custody impact on any network)
Reporter: WAM Fusion engineering, disposable REGTEST evidence only, 2026-11-07

## Statement

In the REGTEST chain parameters (around lines 725–737), the comment says:

> "The testnet burn address (hash160 = 20 zero bytes) is used so regtest
> exercises the identical code path as a live network while the coins it pays
> are provably unspendable."

The assigned value is `consensus.devFeeAddress = WAM_TREASURY_ADDRESS_TESTNET;`.
That constant (around lines 123–126) is documented in the same file as:

> "Testnet treasury, generated 2026-08-19 on the seed node. Deliberately a
> different key from the testnet founder address …"
> `WAM_TREASURY_ADDRESS_TESTNET = "TQkMCz4r2oWuFjAu8mAeGYDMuz4BNkmofz"`

## Verification

1. Independent base58check decode of the literal (stdlib only): version byte
   `65` (the REGTEST/testnet `PUBKEY_ADDRESS` prefix in the same file), valid
   double-SHA256 checksum, hash160 `a21b54367f4bd15b9b33e6e9e8b87c5b2fab5c16`.
   This is **not** 20 zero bytes.
2. Genuine signed WAM Core v0.1.13 (macOS ARM64 `wamd` sha256
   `fe04a61f17eb8047f1d2a537ebcb61b45cbde14c491bc332d2a2ab7ee18237ba`) on a new
   disposable REGTEST chain paid the treasury output to
   `76a914a21b54367f4bd15b9b33e6e9e8b87c5b2fab5c1688ac` (P2PKH of that hash160):
   250000000 atoms at heights 1 and 150, and 125000000 atoms at height 151
   (5% of a 5000000000 / 2500000000 atom subsidy; REGTEST halving interval 150).

## Impact

- REGTEST treasury coins are paid to a real P2PKH key hash, not a burn. The
  claim "provably unspendable" is incorrect as written.
- No private key exposure is claimed or implied. The hash160 identifies a key
  documented as generated on the seed node; whether that key is retained is
  unknown to the reporter.
- Consensus, mainnet treasury, testnet treasury and chain identity are
  unaffected. REGTEST chains are local and disposable.

## Suggested resolution (for DEV WAM to choose)

Either correct the comment to state that REGTEST reuses the testnet treasury
key, or, if a burn was intended, assign a dedicated REGTEST constant whose
hash160 is provably unspendable. Fusion has made no change to Core, its
consensus, treasury addresses or chain identity, and describes REGTEST
treasury coins only as "paid to the testnet treasury key hash".
