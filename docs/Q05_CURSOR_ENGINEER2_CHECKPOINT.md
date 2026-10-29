# Engineer 2 checkpoint — live concurrent-owner refusal

Branch `cursor/q05-history-pagination-9c81`. Codex Draft #138 stays independent
(`feature/issue45-q05-managed-core-stage-a-20261027` at `b3046f82`).
Canonical ledger: 37 Q05 cases PENDING, `accepted=false`. No merge.

## This change

Parent code `9e1766e14145d00f998615a07a7b9722bb814033` recovers the same owned
Core with `recover_dead(authorized=True)` after an explicit kill. This commit
adds the live-lease refusal: after wallet lock and before reopen, a second
`CoreSupervisor` on that root must raise `SUPERVISOR_STORAGE_LEASE_BUSY` and
is not `start()`ed. The original pid and datadir stay in place.
`crash_fail_closed` still denies a replacement start. No PID adoption, file
deletion or transaction replay.

Source contract: `test_live_owner_lease_blocks_second_supervisor_without_new_process`.
Local discover of `test_q05_core_supervisor`, `test_q05_owned_session`,
`test_q05_supervisor_store` and `test_q02_contracts` PASS. That is not native
Core proof. Do not mark `Q05-CONCURRENT-OWNER-*` PASS from the unit test.

## Crash-recovery CI already queued on `9e1766e`

Not this commit's proof. Empty jobs include `same_owner_crash_recovery`.
Windows funded receive skips fail-closed and does not run that recovery.

- macOS https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40808378718
- Linux https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40808378513
- Windows smoke https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40808378464
- Windows funded https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40808378632

## Retained startup evidence

`f6672a7` macOS `40805865241` failed Q02 `UNAVAILABLE`. Windows smoke
`40805865225` and Windows WSP `40805865221` PASS. Linux `40805865248` PASS.
`18774a7` macOS `40806549784` PASS. Linux `40806549962` PASS.
`5b5e4c1` macOS `40807061511` PASS:
https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40807061511
Linux `40807061493` developer-core was still open when `9e1766e` was queued:
https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40807061493

## Next

Read this commit's owned-session receipts for `concurrent_owner_refused` on
macOS, Windows smoke, Windows funded and Linux, and `same_owner_crash_recovery`
on the empty jobs. If `40807061493` or the `9e1766e` empty jobs fail, repair
that before another scenario. Q05 remains unaccepted.
