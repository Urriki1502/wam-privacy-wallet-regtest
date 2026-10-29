# Engineer 2 checkpoint — untrusted Core directory refusal

Branch `cursor/q05-history-pagination-9c81`. Codex Draft #138 stays independent
(`feature/issue45-q05-managed-core-stage-a-20261027` at `b3046f82`).
Canonical ledger: 37 Q05 cases PENDING, `accepted=false`. No merge.

## This change

Parent `5770930f7d34dbde1b99c9022f3d2cf4bbe6b2bf` recovers funded history after
an explicit kill of the original Popen. This commit keeps that path and
strengthens `wrong_core_refused`: a missing directory and a separate directory
whose receipt sets `mainnet_allowed` true, with non-Core bytes named `wamd` /
`wam-cli` / `wamd.exe` / `wam-cli.exe`, must fail in `CoreSupervisor` before
`start`. The qualified Core `receipt.json` is not modified. No PID adoption.
Receipt schema is `q05-owned-session-native/v6`.

Local `unittest discover -s tests -p 'test_q05*.py'`: 117 PASS. This host has
no genuine Core binary. Do not mark `Q05-WRONG-CORE-REFUSAL` PASS from the
unit test.

## Parent evidence, not this commit

`5770930` funded crash recovery CI was queued or in progress when this change
started. `a7c3f81` Windows funded reattach workflow succeeded:
https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40808964946
macOS `40808964924`, Windows smoke `40808964943` and Linux `40808964955` were
still running. Those receipts are schema v4/v5, not v6.

`792701e` Windows smoke `40808542596` and Windows funded `40808542569`
succeeded with `concurrent_owner_refused`. macOS `40808542544` and Linux
`40808542678` still had non-owned-session jobs open after their Q05
owned-session jobs had passed.

## Next

Read this commit's empty owned-session receipts for `wrong_core_refused` with
`untrusted_core_directory_refused`, `process_started` false and
`real_core_receipt_unchanged` on macOS, Windows smoke and Linux. Read
`5770930` funded receipts for `funded_same_owner_crash_recovery` before
changing that path. Q05 remains unaccepted.
