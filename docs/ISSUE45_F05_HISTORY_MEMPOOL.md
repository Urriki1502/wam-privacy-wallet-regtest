# F-05 — Core mempool, confirmed WSP history, reorg and RPC uncertainty

Issue #45 / Phase F / F-05 [P0]. Stacked Draft on PR #95. REGTEST only,
pinned WAM Core v0.1.11. A Core mempool entry is NOT a confirmed
WSP incoming silent payment or authority to spend.

## Independent data sources

The pinned native REGTEST wallet already creates one disposable signed
BIP352 transaction and one intentionally ambiguous RPC response after Core
really accepts its transaction. `classify_known_transaction` is a
read-only classifier for **known, authorized transaction IDs**, not a
mempool-wide discovery engine.

- Authenticated `getrawmempool` from the owned Core describes only
  node-local, current unconfirmed transaction presence.
- The independently scanned WSP SQLite `HistoryRow` describes
  confirmed transactions with a block height and depth. Every depth
  must equal `tip_height - block_height + 1`.
- Native encrypted reservation state (`draft`, `signed`,
  `broadcast`, `uncertain`) is persistent intent-custody evidence.
  It is **never** inferred from a mempool hit.
- A missing mempool transaction does not prove it was dropped,
  conflicted, replaced, or never submitted. No automatic release,
  rebroadcast, rewind, signer/broadcast permission or fund credit.

## Native Core + WSP scenario

| Genuine event | Core mempool | Verified WSP history | Accepted classification |
| --- | --- | --- | --- |
| Submitted signed disposable payment | Contains known txid | Not yet confirmed | `mempool_observed` |
| Mine one block | Txid absent from mempool | Height/depth exact | `confirmed`, depth 1 |
| Invalidate that real block | May return to mempool | Previously confirmed row rolled back | `reorged_mempool_observed` or `reorged_not_observed`, depth 0 |
| Reconsider original valid block | Txid absent from mempool | Confirmed WSP row restored | `confirmed`, depth 1 |
| Submit second test payment, lose RPC reply | Contains txid after actual Core acceptance | No confirmed WSP history | `uncertain_mempool_observed`, no auto-retry |
| Lock, managed reopen and restore | Core/SQLite reauthenticated | Irreversible reservation rows unchanged | Never auto-release or rebroadcast |

The native Qt scenario exists in `wallet_probe.py`; F-05 binds actual
Core and WSP observations to immutable status receipts and makes signed
macOS ARM64 and Windows x64 workflow assertions mandatory. Linux headless
has independent real-Core 1/12/100 reorg checks and runs this suite's
negative unit contracts; it does not automatically qualify the new
Qt-specific transaction-state probe.

## What is NOT yet accepted

A shallow one-block Qt reorg cannot prove WSP balances/history are safe
across 12- and 100-block reorgs. Deep receiver-plus-sender, sender
reservation availability, restoration after multi-day node outages,
mempool persistence across a Core restart, real dropped/conflicted/
replaced status where supported, and fully unconfirmed silent-payment
discovery remain **PENDING** until their own native executable proofs.

No detached/malicious Core, unknown external user wallet, mainnet key,
off-chain pool owed value, real TX resend, WSP signed/uncertain unlock,
automatic backup replay or consensus mutation is authorized.

Native CI must be checked at the **exact F-05 HEAD** before recording
an engineering green milestone. Do not merge automatically.
