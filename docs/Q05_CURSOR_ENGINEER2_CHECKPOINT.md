# Engineer 2 checkpoint — same-owner wallet reattach

Branch `cursor/q05-history-pagination-9c81`. Codex Draft #138 stays independent
(`feature/issue45-q05-managed-core-stage-a-20261027` at `b3046f82`).
Canonical ledger: 37 Q05 cases PENDING, `accepted=false`. No merge.

## Proof source

`a7c3f81ce5891cd123e7aab0c121cf70e9d24f4a`. This note is docs-only and is not
that proof SHA. After the live lease refusal, the harness opens the same
wallet on the original Popen before shutdown. History fingerprint, balance
and pid must match. No second daemon. Receipt schema `q05-owned-session-native/v4`.
Local `test_q05*.py`: 116 PASS. This host has no genuine Core binary.

Queued, not yet proof:

- macOS https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40808964924
- Linux https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40808964955
- Windows smoke https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40808964943
- Windows funded https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40808964946

## Already recorded, other SHAs

`5b5e4c1` macOS `40807061511` PASS, including the Q02 E2E that failed on
`f6672a7`. Linux `40807061493` PASS, including developer-core.
https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40807061493

`9e1766e` same-owner crash recovery. Empty owned-session jobs SUCCESS:
macOS `40808378718` (E2E job also SUCCESS; bundled app and Q04 were still
running), Linux `40808378513` (owned-session, native, Qt, headless, Q04
SUCCESS; developer-core and frozen still running), Windows smoke
`40808378464` full SUCCESS.
https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40808378464

`792701e` concurrent-owner lease refusal. Windows funded `40808542569` full
SUCCESS, including `concurrent_owner_refused`. macOS `40808542544` and Linux
`40808542678` and Windows smoke `40808542596` were still running. That SHA
does not include reattach.
https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40808542569

## Next

Read `same_owner_reattach` on the four `a7c3f81` owned-session jobs, including
funded Windows. A history or anchor mismatch must be fixed without a second
daemon, file deletion, or PID adoption. Do not treat `792701e` or `9e1766e`
as this SHA. Q05 remains unaccepted.
