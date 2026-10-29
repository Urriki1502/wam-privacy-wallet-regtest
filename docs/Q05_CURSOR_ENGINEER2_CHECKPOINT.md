# Engineer 2 checkpoint — crash history fingerprint

Source HEAD: `f16e7b7879685f800858cf54014bf89f8d5938a3`.
Parents: native page `64278ed8b4dccf17750d8bd5ce762c97cac1eb26`, graceful
reopen `b05289783a06d47d8b259f4acecc99eadda8a560`, flush
`37a2bf18871e710c71d17e71e50a19f2cc8732fe`.
Branch `cursor/q05-history-pagination-9c81`. Codex Draft #138 stays independent
(`feature/issue45-q05-managed-core-stage-a-20261027` at `b3046f82`).
Canonical ledger: 37 Q05 cases PENDING, `accepted=false`. No merge.

## This change

Empty and funded same-owner crash recovery must restore the pre-crash
history sha256, tip and exact height. Confirmations are inside the
fingerprint, so a flushed tip taller than the wallet snapshot is refused
before `process.kill()`. The quoted `gettxoutsetinfo none "<tip>" true`
flush, the reaped-handle reopen, and the native history page render stay
in place. Schema stays `q05-owned-session-native/v6`.

Local `PYTHONPATH=src unittest discover -s tests -p 'test_q05*.py'`: 118 PASS.
No genuine Core on this host. Not a native PASS.

## Retained flush proof

`37a2bf1` signed Windows funded PASS:
https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40810596391
`funded_same_owner_crash_recovery` PASS. Original pid 3288, recovered pid
4404. Windows smoke PASS:
https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40810596382
Empty fail-closed, crash recovery, wrong-core refusal, reattach and
concurrent-owner refusal PASS. `frozen_build` remains NOT EXECUTED.
Those receipts do not include `graceful_shutdown`.

`37a2bf1` Q05 owned-session jobs, not the whole workflows:

- macOS https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40810596567
  job `Q05 owned-session genuine signed Core START→RESTORE` SUCCESS.
  Funded receipt PASS. Original pid 4810, recovered pid 5349, txid
  `dd6689e5027bb637f8cee2b6634fec37407a01ae7413a1ff360aa32075610d35`.
  Empty receipt PASS, including crash recovery and offscreen GUI.
- Linux https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40810596535
  job `Q05 owned-session qualified Linux developer Core START→RESTORE` SUCCESS.
  Funded receipt PASS. Original pid 4701, recovered pid 5089, txid
  `385bdb071dd42e3a172b485d489f147a493d1e7839304376b2e43238f25d8260`.
  Empty receipt PASS. `official_signed_release` is false on that developer Core.

Those receipts do not prove `b052897`. The macOS and Linux workflows still
had unrelated frozen and Q04 jobs open when the Q05 jobs finished.

## Retained failures

`4d27f1b` Windows funded `CORE_RPC_DENIED` (bare tip, `use_index` false):
https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40810343337

`ca7bb85` Windows funded `MANAGED_RECOVERY_HEIGHT_REGRESSED`:
https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40809932361

`5770930` same height code:
https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40809138451

## Trigger SHA `792701e`

All four live-lease workflows completed success. They prove
`concurrent_owner_refused` on that SHA, not this reopen check.

- macOS https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40808542544
- Linux https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40808542678
- Windows smoke https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40808542596
- Windows funded https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40808542569

## `b052897` owned-session receipts

These are the Q05 owned-session jobs, not whole-workflow acceptance.
`graceful_shutdown` PASS and `history_identity_unchanged` on the funded
reopen. `frozen_build` remains NOT EXECUTED. macOS has not finished.

- Windows funded PASS
  https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40811222194
  Original crash pid 5676, recovered pid 4072, reopened pid 7196.
  Txid `eeed0f04b703a00cec6c8268f81f72bf25684ffea10564edcb05ed4b38ad1bf9`.
  Restored height 103. History sha256
  `8a228641cd5ad8fed6b0d5c681b7d70d3eae3a5a7e7ad7d8ea2bce7e153d2452`.
- Windows smoke PASS
  https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40811222061
  Empty fail-closed, crash recovery, wrong-core refusal, reattach,
  graceful shutdown and offscreen GUI PASS.
- Linux Q05 job PASS
  https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40811222487
  Empty and funded receipts PASS on reviewed developer Core
  (`official_signed_release` false). Other Linux jobs were still open.
- macOS https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40811222044
  was still queued when this note was written.

## Next

`f16e7b7` CI is the crash-fingerprint proof. It also carries the unproven
`64278ed` native history page (`native_gui_history_matches`). Read
`history_identity_unchanged` on both empty and funded crash observations,
and `native_gui_history_matches` where the GUI runs. A fingerprint, tip or
height mismatch is a real FAIL. Do not treat `37a2bf1` or `b052897` receipts
as proof of this check.

macOS `b052897` run 40811222044 was still in progress for
`graceful_shutdown`. Windows and Linux `b052897` receipts do not stand in
for that macOS job. `frozen_build` stays `NOT EXECUTED`. Q05 remains
unaccepted.
