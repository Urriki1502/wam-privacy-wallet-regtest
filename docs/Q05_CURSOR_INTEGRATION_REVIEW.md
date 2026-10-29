# Combined integration update — 29 October 2026

The owner transferred integration/qualification to Codex in
[PR #138 comment 6488299410](https://github.com/Urriki1502/wam-privacy-wallet-regtest/pull/138#issuecomment-6488299410).
Latest reviewed Cursor head: `87721cda50682ee55feec32829ccf94a87459ade`;
last code-bearing source `952e8756e46345f798b5fa2dbef8ced418d6e718`.

| Source group | Combined disposition |
| --- | --- |
| history_pages, snapshot/read/window pagination, disclosure lookup | Selectively imported; complete transactional fingerprints, bounded display windows, exact SQL disclosure; no truncated-history claim. |
| reservation_fingerprint | Imported into managed checkpoint/session, retained irreversible reservations. |
| GUI/history/HiDPI helpers | Imported compatible pagination and DPR presentation; managed operations now use persistent serialized executor, not Cursor main-thread timers or temporary live-session QThreads. |
| open_owned/recovery/custody | Codex active_location/COMMIT/anchor-floor implementation retained. No import of Cursor hardcoded original-vault opener or weaker directory metadata checks. |
| platform adapters / Windows signed staging | Reviewed extraction into q05_platforms; Linux test witness explicit, not production authority; create-new staging, no repair. |
| native CI | Adapted existing platform workflows to new actual managed GUI executor probe; previous four Cursor green runs are historical scope only. |
| old q05_owned_lifecycle driver | Excluded: GUI bypasses lifetime owner-thread; interrupted-publication dummy file cannot prove genuine encrypted-publication failure. |

Native Cocoa proof on combined source 873f6ac is supplemental, with failure history
retained. All-OS native/frozen, real publication fault matrix and physical/independent
review remain open. This internal review is not independent G7 signoff.

---

# Engineer 1 selective integration review — 29 October 2026

Reviewed remote `cursor/q05-history-pagination-9c81` at
`9eea948ce06b87238fbf3705aa2c6f74fb1cef7c`, relative to common published
Codex source `9b0361c6211f500ef78d0ace171c1bb6a5a10329`.
Cursor branch/checkpoint was not modified. This is an internal review, not G7.

Imported into #138: `history_pages.py`, checkpoint history/chain snapshot helpers,
`test_q05_history_pagination.py`, and history helper tests. Preserve local
`_runtime(name)`, recovery-reference selection, anchor floor and create refusal.
Fingerprint every row under one SQLite transaction with reservations/balance;
require canonical order, declared row count, confirmations and bounded WSP
offsets. Empty and <=999 row fingerprints retain canonical JSON-array semantics.
Counts 1000/1001/2500 now complete instead of truncated/refused; offset overflow
still refuses. No wallet/signing/control authority is added.

The Cursor source-string test for session/read pagination was adapted to the
actually imported checkpoint-only scope. All behavior tests in the shared helper
and checkpoint suite are retained. Session/read/GUI pagination is not claimed.

Deferred file groups and integration prerequisites:

| Files | Review finding / next integration action |
| --- | --- |
| `wallet_session.py: open_owned` | Hardcodes original `wallet-vault`/runtime. Must select authenticated COMMIT container, enforce native anchor floor and reject pending/foreign target; no fallback to original folder. Create must reject recovery residue even if original reference is missing. |
| `wallet_session.py: owned session lifecycle` | Review anchor lease coverage across restore/sync/save and fresh original-Popen checks before each privileged operation; retain stale-session refusal and uncertainty before submission. Verify close never deletes unknown runtime/sidecars. |
| `desktop.py`, `operational_gui.py`, `fusion_pages.py`, `cli.py` | Depend on reviewed owned-session API. Do not introduce a second supervisor or wallet capabilities on control-only IPC. Prove close/lock/in-flight sign/broadcast behavior on genuine Core. |
| `q05_owned_lifecycle.py`, `probe_q05_owned_session.py` | Existing cross-platform harness is a reuse candidate; avoid duplicate CI. Verify candidate/checkout/executed source identity, native profile root repair, and failure cleanup. Current `stop_owned` suppresses stop/close errors: receipts must expose a surviving child and retain original Popen authority, never call that safe shutdown. |
| Four workflow files | Review provenance, exact source and sanitized artifacts before selective import; no assumption that legacy frozen jobs exercise Q05 owned GUI. Current Linux workflow is also immutable developer build provenance input. |
| History changes in session/read/GUI | Can follow after custody integration. Preserve complete fingerprints and explicit display-window metadata; targeted tests do not imply native packaged qualification. |

Actions API returned no workflow runs for exact remote 9eea948 during this review.
Owner-provided failure run 40788571264 used 85d5c5c; the later profile-root fix
is not independently native-qualified by that older FAIL receipt.

Recovery limitations: current local prototype requires an original live owned
Popen and exact anchor-authenticated checkpoint. It neither adopts a post-crash
foreign process nor completes a pending recovery reference. No promotion of an
orphan by filename/password alone, unknown runtime cleanup, vault/KDF migration,
or standalone antirollback claim. Native successes remain supplemental; all 37
canonical cases and physical/independent boundaries stay unresolved.
