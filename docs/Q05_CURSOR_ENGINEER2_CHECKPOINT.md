# Engineer 2 checkpoint — reservation identity

Source HEAD: `724a2cf87cda10eb3a3f4f2e63b79506a68063e2`.
Parent proof: crash fingerprint `f16e7b7879685f800858cf54014bf89f8d5938a3`
checked out as `3e04e45b60a937e41bce1f29d8aa044312dc03d7`.
Branch `cursor/q05-history-pagination-9c81`. Codex Draft #138 stays independent
(`feature/issue45-q05-managed-core-stage-a-20261027` at `b3046f82`).
Canonical ledger: 37 Q05 cases PENDING, `accepted=false`. No merge.

## This change

Owned snapshots now fingerprint `reservations` with the same canonical
digest as the native checkpoint. Reattach, graceful restore, and empty or
funded same-owner crash recovery call `_require_same_reservation` and record
`reservation_identity_unchanged` only after the count, digest, and states
match. A missing fingerprint refuses. The quoted `gettxoutsetinfo` flush,
exact history height/tip/sha256 check, native history page, and reaped-handle
reopen stay in place. Schema stays `q05-owned-session-native/v6`.

Local `PYTHONPATH=src unittest discover -s tests -p 'test_q05*.py'`: 119 PASS.
`tests.test_gui_error_privacy` and `tests.test_linux_headless_contracts`: 8 PASS.
No genuine Core on this host. Not a native PASS.

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
Those receipts do not prove `f16e7b7` or `724a2cf`.

## Retained failures

`4d27f1b` Windows funded `CORE_RPC_DENIED` (bare tip, `use_index` false):
https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40810343337

`ca7bb85` Windows funded `MANAGED_RECOVERY_HEIGHT_REGRESSED`:
https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40809932361

`5770930` same height code:
https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40809138451

## Next

`724a2cf` CI is the reservation-identity proof. Read
`reservation_identity_unchanged` on reattach, crash recovery, and graceful
restore. A `Q05_RESERVATION_IDENTITY_DENIED` or
`WALLET_RESERVATION_INCONSISTENT` result is a real FAIL. Do not treat
`3e04e45` history receipts as proof of this check.

- Windows funded https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40812185764
- Windows smoke https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40812185782
- Linux https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40812185723
- macOS https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40812185737

`frozen_build` stays `NOT EXECUTED`. Q05 remains unaccepted.
