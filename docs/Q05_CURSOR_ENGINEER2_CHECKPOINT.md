# Engineer 2 checkpoint — Q02 startup reads on signed macOS Core

Branch `cursor/q05-history-pagination-9c81`. Startup code fix
`5b5e4c160ee21cfef2e75c52b5262c77d889ce1b`. This note is docs-only and is not
that proof SHA.
Codex Draft #138 stays independent
(`feature/issue45-q05-managed-core-stage-a-20261027` at `b3046f82`).
Canonical ledger: 37 Q05 cases PENDING, `accepted=false`. No merge.

## Startup failure and fixes

`f6672a7` macOS `40805865241` failed Q02 `UNAVAILABLE` with
`CORE_LOCAL_NETWORK_POLICY_DENIED`, latched `CORE_RPC_SCOPE_FAULTED`, and
`Q02_NODE_START_TIMEOUT`. Q05 owned-session on that run PASS. Windows smoke
`40805865225` and Windows WSP `40805865221` PASS. Linux `40805865248` later
PASS, including developer-core.

`18774a757dc871863c8c69da8c01842f55b1d69a` re-attests the same Popen only before
the first verified RPC. macOS `40806549784` PASS (E2E, owned-session, Q04, bundled app).

`5b5e4c160ee21cfef2e75c52b5262c77d889ce1b` keeps inode, owner and mode as
directory stability. Child link-count and timestamp updates are not replacement.
File identity and pre-transport quarantine are unchanged. macOS `40807061511`
PASS: https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40807061511

Linux `40807061493` still had developer-core building when this note was written.
Q05 owned-session, native contracts, Qt, headless, Q04 and both frozen wallet
jobs on that run were already SUCCESS.
https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40807061493

## Next

If Linux `40807061493` developer-core fails, fix that before new Q05 behavior.
Otherwise continue the next source-level Q05 gap that is not already covered by
the owned-session harness. Q05 remains unaccepted.
