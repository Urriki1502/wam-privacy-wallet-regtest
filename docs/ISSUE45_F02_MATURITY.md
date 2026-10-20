# F-02 — Genuine Core coinbase maturity 99 / 100 / 101

Issue #45, Phase F, F-02 [P0]; stacked Draft PR on F-01.

**Scope:** original freshly generated, isolated disposable WAM Core REGTEST
miner-only account and its first height-1 coinbase. This is NOT general
wallet spend authorization, mainnet mining, WSP-reservation reconciliation,
imported-wallet spendability or a key export.

## Core-backed test protocol

The existing signed macOS ARM64 / signed Windows x64 / qualified Linux
developer-Core acceptance fixture mines first block to a new owned wallet
address, with miner subsidy of **47.5 WAM** and treasury **2.5 WAM**.
It then mines exactly 98 blocks to an unrelated public test address.
All observations below use real isolated Core, not synthetic balances:

| Coinbase depth | Source height | Core UTXO coinbase | Wallet immature | Wallet trusted | Wallet available | Core wallet send |
| --- | --- | --- | ---: | ---: | ---: | --- |
| 99 | 99 | true, confirmations 99 | 47.5 WAM | 0 | 0 | Must fail without changing mempool or wallet |
| 100 | 100 | true, confirmations 100 | 47.5 WAM | 0 | 0 | Must fail without changing mempool or wallet |
| 101 | 101 | true, confirmations 101 | 0 | 47.5 WAM | 47.5 WAM | First disposable payment accepted in mempool |

The core's `WAM_COINBASE_MATURITY=100` setting must not be
incorrectly read as wallet spendable at *100* confirmations: test the
actual Core result at **depth 101**.

## New explicit maturity witness

`src/wam_regtest/f02_maturity.py` matches all of these simultaneously:

- Chain identity and exact WAM REGTEST genesis from source-verified Core.
- Actual height vs coinbase origin block and exact integer confirmations.
- `gettxout` coinbase flag, script matching the Core-owned miner address
  and exact 47.5 WAM miner (not treasury) output.
- `getbalances`, owned `listunspent` and independent `gettxout`
  reconciled in the existing read model.
- Zero early trusted / available / eligible UTXO counts, and appropriate
  `immature` atoms at depth 99/100.
- Exactly one eligible first miner output at depth 101; no premature RPC
  spend, balance drift, or mempool changes.

The native source test exercises fake Core-shaped public observations
to prove rejection of malformed depth, pre-mature spending claims,
untrusted wallet state, changed scripts/amounts, wrong chain or
impossible coinbase references. It is **UNIT only**, never Core E2E.

Native workflows require the actual Core receipt:
`f02_real_core_immature_99_100_and_mature_101_verified` and
`f02_no_early_send_or_mempool_mutation`, plus the three complete
per-depth `f02_core_maturity_witness` records.

### Important limits

- A failed `sendtoaddress` CLI alone does not prove maturity. The
  independent Core UTXO, wallet trust/balance, chain-height and
  unchanged mempool checks all must pass.
- A positive depth-101 witness only states a **disposable Core test
  account** has reached normal coinbase spend eligibility. It creates
  no WSP signer session, authorization to broadcast real payments,
  cross-OS recovery privilege or real miner-wallet accounting.
- Core source/binary pin, OS provenance and frozen acceptance remain
  independent. No claim that a different version is automatically
  equivalent.
- Phase K physical cross-OS recovery and signed/uncertain WSP
  reservations remain PENDING. F-03 starts only after F-02 exact-HEAD
  CI reaches green and its evidence is reviewed.

**Status:** native execution results must be checked at the exact
F-02 HEAD before marking F-02 engineering complete.
