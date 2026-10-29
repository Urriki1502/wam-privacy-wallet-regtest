# Engineer 2 checkpoint — graceful stop and history identity

Source HEAD: `b05289783a06d47d8b259f4acecc99eadda8a560`.
Flush parent: `37a2bf18871e710c71d17e71e50a19f2cc8732fe`.
Branch `cursor/q05-history-pagination-9c81`. Codex Draft #138 stays independent
(`feature/issue45-q05-managed-core-stage-a-20261027` at `b3046f82`).
Canonical ledger: 37 Q05 cases PENDING, `accepted=false`. No merge.

## This change

After the owned wallet locks, the original Popen is stopped and that handle
must be reaped before a new supervisor starts on the same datadir. A reused
numeric PID is not a second daemon. Reopen must match the pre-shutdown
history fingerprint, counts, confirmed atoms, height and tip. The quoted
`gettxoutsetinfo none "<tip>" true` flush is unchanged. Schema stays
`q05-owned-session-native/v6`.

Local `unittest discover -s tests -p 'test_q05*.py'`: 118 PASS.
`test_q02_contracts`: 19 PASS, 1 skipped. No genuine Core on this host.
Not a native PASS.

## Retained flush proof

`37a2bf1` signed Windows funded PASS:
https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40810596391
`funded_same_owner_crash_recovery` PASS. Original pid 3288, recovered pid
4404. Windows smoke PASS:
https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40810596382
Empty fail-closed, crash recovery, wrong-core refusal, reattach and
concurrent-owner refusal PASS. `frozen_build` remains NOT EXECUTED.
Those receipts do not include `graceful_shutdown`.

macOS https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40810596567
and Linux https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40810596535
were still the open flush proof when this commit was cut.

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

## Next

Read this commit's receipts for `graceful_shutdown` and
`history_identity_unchanged` on Windows, macOS and Linux. A reaped-handle
miss or a history fingerprint mismatch is a real FAIL. Q05 remains
unaccepted.
