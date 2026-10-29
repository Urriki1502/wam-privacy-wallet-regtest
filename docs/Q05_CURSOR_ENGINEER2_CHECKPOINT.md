# Engineer 2 checkpoint — owned history paging

Parent tip: `724a2cf87cda10eb3a3f4f2e63b79506a68063e2` (reservation identity).
Crash fingerprint `f16e7b7879685f800858cf54014bf89f8d5938a3` checked out as
`3e04e45b60a937e41bce1f29d8aa044312dc03d7`. Native page
`64278ed8b4dccf17750d8bd5ce762c97cac1eb26`.
Branch `cursor/q05-history-pagination-9c81`. Codex Draft #138 stays independent
(`feature/issue45-q05-managed-core-stage-a-20261027` at `b3046f82`).
Canonical ledger: 37 Q05 cases PENDING, `accepted=false`. No merge.

## This change

When the owned history page is incomplete, Older and Newer read the same
session at the next `GUI_HISTORY_LIMIT` offset and return to the original
txids. A complete page leaves both controls disabled and does not call
`snapshot` again. No broadcast, mine, wallet lock, datadir deletion or
second supervisor. `724a2cf` reservation identity checks stay in place.
Funded Core jobs still have a complete two-row page, so `gui_history_paged`
stays false there. Schema stays `q05-owned-session-native/v6`.

Local offscreen: `test_fusion_v2_widgets` 10 PASS, `test_q05_owned_session`
11 PASS, `test_q05_history_pagination` 18 PASS. No genuine Core on this
host. Not a native PASS.

## Reservation identity on `724a2cf`

Owned snapshots fingerprint `reservations` with the same canonical digest
as the native checkpoint. Reattach, graceful restore, and empty or funded
same-owner crash recovery call `_require_same_reservation`. A missing
fingerprint refuses. Local `test_q05*.py` on that parent was recorded as
119 PASS. Its CI is still the reservation proof:

- Windows funded https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40812185764
- Windows smoke https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40812185782
- Linux https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40812185723
- macOS https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40812185737

## `3e04e45` crash-fingerprint receipts

These Q05 owned-session jobs include `f16e7b7`. `history_identity_unchanged`
is on the crash observation at the pre-crash height and tip.
`native_gui_history_matches` is true where the GUI ran. `frozen_build` is
`NOT EXECUTED`. Whole workflows still had unrelated Q04 or frozen jobs open.

- Windows funded PASS
  https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40811682152
  Official signed Core. Crash pid 2696, recovered pid 3140, reopened pid 4916.
  Height 103. History sha256
  `237070a804b692012af8a4e6f87bffa0ea5e4d97571051569844cad3768c6426`.
  Txid `14c486700d63468b18311b40b6352bf7ab4736a6b2658a6b144006cc75fd8f30`.
- Windows smoke Q05 job PASS
  https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40811682138
  Empty crash pid 1756, recovered pid 1956, height 0. Graceful stop pid
  4248 reaped, reopened pid 2516. Offscreen GUI PASS.
- Linux Q05 job PASS
  https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40811682229
  Reviewed developer Core, `official_signed_release` false. Funded crash
  pid 4833, recovered pid 5220, height 103, txid
  `9b561dd0a86cc1a249aff10d7b658811ac17ae4c479a120db2f0896fe600b764`.
  Empty crash pid 4438, recovered pid 4591, height 0.
- macOS Q05 job PASS
  https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40811682294
  Official signed Core. Funded crash pid 3582, recovered pid 4229, height
  103, txid `27ad7760023f81b60e3f5174ad384607fd26df0baf20358d35f1fa4cd4edcebe`.
  Empty crash pid 3385, recovered pid 3418, height 0.

## Retained `b052897` graceful-stop receipts

Windows funded
https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40811222194
crash pid 5676, recovered pid 4072, reopened pid 7196.
Windows smoke
https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40811222061
Linux
https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40811222487
macOS Q05 job inside
https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40811222044
Those receipts do not prove `f16e7b7`, `724a2cf`, or history paging.

## Retained failures

`4d27f1b` Windows funded `CORE_RPC_DENIED` (bare tip, `use_index` false):
https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40810343337

`ca7bb85` Windows funded `MANAGED_RECOVERY_HEIGHT_REGRESSED`:
https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40809932361

`5770930` same height code:
https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40809138451

## Next

Read `724a2cf` for `reservation_identity_unchanged` on reattach, crash
recovery, and graceful restore. `Q05_RESERVATION_IDENTITY_DENIED` or
`WALLET_RESERVATION_INCONSISTENT` is a real FAIL. `3e04e45` history
receipts do not prove that check. This paging commit needs its own CI.
`gui_history_paged` is false on the current two-row funded page.
`frozen_build` stays `NOT EXECUTED`. Q05 remains unaccepted.
