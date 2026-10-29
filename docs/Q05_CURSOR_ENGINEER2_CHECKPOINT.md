# Engineer 2 checkpoint — reservation receipts on 724a2cf

Code under test for paging: `952e8756e46345f798b5fa2dbef8ced418d6e718`.
Reservation identity: `724a2cf87cda10eb3a3f4f2e63b79506a68063e2`.
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
same-owner crash recovery call `_require_same_reservation`. These are the
Q05 owned-session jobs, not whole-workflow acceptance. Every listed crash,
reattach, and restore observation has `reservation_identity_unchanged`
true. Empty wallets have reservation count 0 and sha256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` on all
three OS. Funded wallets have count 1. `frozen_build` stays `NOT EXECUTED`.
`3e04e45` history receipts do not prove this check. `952e875` paging CI
does not prove it either.

- Windows funded PASS
  https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40812185764
  Signed Core. Crash pid 5708, recovered pid 2724, reopened pid 2040.
  Height 103. Txid `38860c311dae443fb418f6466cfd88fad2b1c0c4218b0c622f2a5ce5bd22f0bf`.
  History sha256 `debf7a7f46040694afdb799adbb980985dd1206539d55cd6ea0ab65dedab2273`.
  Reservation sha256 `b8f05fd523d4f00c13a0f9bc631938041e5a7e42372d176af7c51f473e7073fc`.
- Windows empty PASS
  https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40812185782
  Signed Core. Crash pid 7848, recovered pid 6164, height 0.
  The smoke workflow still had Q04 jobs open.
- Linux Q05 job PASS
  https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40812185723
  Reviewed developer Core, `official_signed_release` false.
  Funded crash pid 4854, recovered pid 5243, height 103.
  Txid `ddd97cc8bb0e260d4d8e7a4151b154ed74463bb8919f1f13c7731de59d37ea85`.
  History sha256 `10b679a90e227a4f5005532d68f3c872a91371f957552e2486cd34125994f471`.
  Reservation sha256 `d49b956a63d165c89577f2e2d693b69141503070b718bf13d4ee12eab54ee4ce`.
  Empty crash pid 4460, recovered pid 4612, height 0.
  developer-core, Q04, and frozen-wallet jobs were still open. Those frozen
  jobs are not Q05 `frozen_build`.
- macOS Q05 job PASS
  https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40812185737
  Signed Core. Funded crash pid 2174, recovered pid 2623, height 103.
  Txid `d3cfe4672cb26e90668d1fa3d846f6ccc4eae2c7d40bb30f273ff8bb407fc071`.
  History sha256 `eb2004e347dff91f67e0742c7bc20d07a09c471c7796a14186c329d3fdb09fd1`.
  Reservation sha256 `0b2a370a73eb2f84cc4fe95cf96e8ea5eaa920ab933f6282629174270ebe65f3`.
  Empty crash pid 2072, recovered pid 2111, height 0.
  The receive/balance job was still open.

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

`724a2cf` Q05 jobs passed reservation identity on Windows, Linux, and
macOS. Do not treat the still-open Q04, frozen-package, or receive jobs
on those workflows as this proof. `952e875` CI is the paging proof and
was still running when this note was written. Funded Core pages are
complete at two rows, so `gui_history_paged` stays false there. A paging
FAIL is real. `frozen_build` stays `NOT EXECUTED`. The frozen executable
still has `q04-external-miner` and no owned-session mode. Q05 remains
unaccepted. No merge.
