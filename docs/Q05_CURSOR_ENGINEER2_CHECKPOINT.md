# Engineer 2 isolated checkpoint — history completeness (not Q-GATE)

Branch `cursor/q05-history-pagination-9c81`. Codex Draft #138 remains
`9b0361c6211f500ef78d0ace171c1bb6a5a10329`. This file is a Cursor work
log only. Canonical ledger `tests/acceptance/issue45.json` is unchanged
(37 Q05 PENDING, accepted=false). No second PR, no merge, no mainnet.

## Completed on this branch

1. Managed checkpoint history paging under one `BEGIN IMMEDIATE` snapshot.
2. Exact WSP ceiling: 1_001_000 records complete; 1_001_001 incomplete.
   Last full page at offset 1_000_000 no longer raises after success.
3. Shared `wam_regtest.history_pages` used by checkpoint fingerprint,
   WalletSession snapshot (collect newest-first for GUI), macOS
   `wallet_read` and Windows `windows_wallet_read` SQL paging.
4. Disclosure looks up `history.txid` instead of scanning a truncated
   `Wallet.history()` page.
5. GUI public categories for `WALLET_HISTORY_INCONSISTENT` /
   `WALLET_HISTORY_INCOMPLETE`. Reservations, vault/KDF/AEAD, native
   anchor, journal and broadcast policy were not changed.

## Tests actually run (this environment)

- `unittest discover -s tests -p 'test_q05*.py'`: 105 PASS / 0 FAIL / 0 SKIP
- `tests.test_history_pages` + `tests.test_gui_error_privacy` +
  `tests.test_q02_contracts`: PASS (1 skip in Q02, unrelated)
- Genuine signed WAM Core / macOS / Windows / frozen / physical:
  **NOT EXECUTED**

## Codex overlap

PR #138 remaining work is interrupted native-anchor publication and
cross-process dirty-owner recovery. Engineer 2 did not copy that path.

## Next engineering action

GUI/supervisor managed-Core onboarding needs a genuine Core host.
This Linux cloud agent has no `wamd`/`wam-cli`. Continue isolated unit
contracts that do not require Core, or stop that native action as
NOT EXECUTED and keep recovery architecture for Codex review.

Do not promote Q05 cases to canonical PASS from this checkpoint.
