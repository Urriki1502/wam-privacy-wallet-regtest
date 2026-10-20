# F-01 — WAM mining account, subsidy, fees and treasury integrity

**Issue:** #45 / Phase F / F-01 [P0]. This engineering change is stacked
on Draft K-10 PR #91 and remains **REGTEST only**. No mainnet key,
public-network RPC, external miner datadir, owned node mutation,
legacy wallet migration, imported signer or user-authorized broadcast.

## Source consensus reference — production parameters, not live mainnet

Independent unchanged v0.1.11 and v0.1.12 upstream source pins:
- `wam-params.h`: `d798155e1964adbdb3ccc48b44dd48fcde3b1602`
- `consensus/subsidy.cpp`: `5659e868f191f2c497950d690829f0369aa912d1`

The existing native-compiled `scripts/check_wam_subsidy_source.py`
uses a test-only C++ harness calling those *pinned source functions*,
not a compiled production network node. Observations are integer atoms:

| Production block height | Block subsidy (WAM) | Treasury from subsidy | Miner subsidy, before all fees |
| --- | ---: | ---: | ---: |
| 1–200000 | 50 | 2.5 | 47.5 |
| 200001–400000 | 25 | 1.25 | 23.75 |
| 400001–600000 | 12.5 | 0 | 12.5 |
| 600001–800000 | 6.25 | 0 | 6.25 |

Block zero is genesis premine, not a normal block reward. Starting
400001 the treasury percentage is zero independently of subsidy or
halving. Transaction fees belong entirely to miners. The complete
production-parameter lifetime subsidy treasury is 750000 WAM; this is
a **source-derived** calculation, not a confirmed native-chain history.

## Genuine Core runtime — separate REGTEST consensus parameters

REGTEST subsidy halves every **150** blocks in the pinned v0.1.11
runtime, not every 200000. The pre-existing native
`probe_core_mining()` verifies the actual Core-produced outputs,
`getdevfeeinfo` block audit, owned `getaddressinfo` script,
independent authenticated wallet balances and spent/locked UTXOs.
Core transaction fees are independently matched against exact
coinbase outputs. It checks the first 47.5/2.5, height 150/151,
300/301 and 450/451 (and depth 99/100/101 for the separately scoped F-02).

F-01 strengthens this with **full miner ownership**: matching total
coinbase subsidy and 5% treasury is insufficient. Every positive
non-treasury reward output must map to a Core-confirmed owned miner
script, and their aggregate must equal **subsidy − treasury + all
transaction fees**. Unknown script attribution fails closed.

An additional native runtime regression takes an ACTUAL coinbase RPC
response, mutates **only an in-memory copy** to point a miner output to
an unrelated public script, and verifies that `CoinbaseAudit` refuses
the result. This is a negative test grounded in a real Core response,
not a claim that Core itself was modified or attacked.

All native lanes must explicitly assert:
- `f01_real_core_unowned_miner_script_negative_denied == true`
- `f01_all_miner_fees_core_owned_and_treasury_separate == true`

No actual Core at REGTEST height 400001 can provide nonzero coinbase
subsidy under its 150-block halvings (already zero by height 4951).
Therefore **do not** claim that a positive-subsidy real-Core
400000/400001 transition has been verified by the short REGTEST
fixture. Pinned consensus-source vectors check the mathematical
cutoff; physical/exact-version Core runtime consensus beyond those
heights remains a separate qualification gate.

## Acceptance status

| Proof category | Required observation |
| --- | --- |
| SOURCE | Exact pinned native C++ subsidy vectors 1/200000/200001/400000/400001, independent treasury cutoff |
| UNIT | Tampered miner-owned script, fee diverted to stranger, treasury fee attribution, zero-value metadata, chain/owner refusal |
| REAL CORE | Genuine REGTEST block audits, Core-owned miner reward, fee and treasury segregation on tested heights, in-memory tampering refused |
| THREE OS | Linux developer Core / macOS signed Core / Windows signed Core native workflow at exact F-01 HEAD |
| PRODUCTION-HEIGHT CORE | Pending independent valid binary/chain fixture for live nonzero 400000/400001 comparison; not inferred from source |
| RELEASE | No mainnet, transferable signer, external-node tests or approval to merge |

F-02 maturity and spendable-UTXO correctness is the **next PR**, not
an implicit completion claim from F-01.
