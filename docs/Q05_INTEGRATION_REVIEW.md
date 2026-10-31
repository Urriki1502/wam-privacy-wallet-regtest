# Q05 — Integration source review (current reconciliation)

**31 October 2026:** Draft PR #138; runtime source `4f7d4ed42e5fdeb5ea91712dea70ea4653bce0f5`; 32 technical PASS / 4 external BLOCKED / 1 owner PENDING; full `accepted=false`. This is an internal technical record, **not** an independent G7 review. See [current checkpoint](Q05_STAGE_A_CHECKPOINT.md).

## Incorporated source and scope

Reviewed input source revisions `9b0361c6211f500ef78d0ace171c1bb6a5a10329`, `952e8756e46345f798b5fa2dbef8ced418d6e718`, `87721cda50682ee55feec32829ccf94a87459ade`; exact source SHAs and Git ancestry remain the provenance, not contributor labels.

| Technical area | Integrated result |
| --- | --- |
| History/page/disclosure | Complete transactional fingerprint, bounded windows and exact SQL disclosure; no history truncation |
| Reservations | Irreversible signed/uncertain reservation identity across recover/reopen |
| GUI and HiDPI | Compatible display helpers, persistent serialized owner-thread executor |
| Custody and recovery | Authenticated COMMIT selection, active location, native lease/anchor floor and original-Core authority |
| Platform | Protected Windows SQLite create, explicit Linux test witness, pinned WSP and Core |
| CI | Genuine managed wallet native/final frozen scenarios qualified across three operating systems |

## Deliberately excluded

Do not import temporary UI-thread Core ownership, weaker directory checks, hard-coded original vault recovery, PID-only adoption, generic signing/RPC IPC, dummy publication faults or historical Q04 PASS as Q05 proof. No automatic replacement/stop of external Core or miner. Preserve FAIL receipts and never silently retry uncertain writes.

## Historical scope

The 29 October source review had 37 PENDING and unfinished combined frozen qualification. These are superseded by the 30 October source-bound CI and 31 October ledger reconciliation. Human clean-device, independent security review, owner merge authorization and exact-main postmerge verification remain open. Evidence under `docs/evidence/q05/` is retained unchanged.
