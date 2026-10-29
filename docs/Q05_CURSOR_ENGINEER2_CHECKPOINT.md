# Engineer 2 checkpoint — same-owner crash recovery

Branch `cursor/q05-history-pagination-9c81`. Codex Draft #138 stays independent
(`feature/issue45-q05-managed-core-stage-a-20261027` at `b3046f82`).
Canonical ledger: 37 Q05 cases PENDING, `accepted=false`. No merge.

## Startup proof already recorded

`f6672a7` macOS `40805865241` failed Q02 `UNAVAILABLE`. Windows smoke
`40805865225` and Windows WSP `40805865221` PASS. Linux `40805865248` PASS,
including developer-core.

`18774a757dc871863c8c69da8c01842f55b1d69a` re-attests the same Popen only before
the first verified RPC. macOS `40806549784` PASS. Linux `40806549962` PASS,
including developer-core.

`5b5e4c160ee21cfef2e75c52b5262c77d889ce1b` ignores datadir child link-count and
timestamp churn. macOS `40807061511` PASS:
https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40807061511
Linux `40807061493` owned-session, native, Qt, headless, Q04 and both frozen
jobs PASS. `developer-core` was still building when this note was written:
https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40807061493

## This change

Empty fail-closed owned-session kills the original Popen and calls
`recover_dead(authorized=True)` on that same owner. The wallet reference,
`wam.conf` and datadir stay in place. The restored session keeps the payment
code and empty history. `crash_fail_closed` still denies a replacement
supervisor `start`. No PID adoption, file deletion or transaction replay.

Local: 115 `test_q05*.py` PASS. This host has no genuine Core binary.

## Next

Read this HEAD's empty owned-session jobs on macOS, Linux and Windows. A
datadir-lock failure must be fixed without deleting chain data or allowing a
foreign start. Canonical cases stay PENDING.
