# Engineer 2 checkpoint — Q02 owned-startup datadir reads

Branch `cursor/q05-history-pagination-9c81`. Codex Draft #138 stays independent
(`feature/issue45-q05-managed-core-stage-a-20261027` at `b3046f82`).
Canonical ledger: 37 Q05 cases PENDING, `accepted=false`. No merge.

## Evidence on `f6672a7d9219f4432f272f324ed2fd9ced0b89fb`

- macOS `40805865241` FAILURE. `q05-owned-session` PASS. E2E failed in Q02
  `UNAVAILABLE`: `CORE_LOCAL_NETWORK_POLICY_DENIED`, latched
  `CORE_RPC_SCOPE_FAULTED`, `Q02_NODE_START_TIMEOUT`. Same E2E job PASS on
  `fd8376a` (`40802778826`).
- Windows smoke `40805865225` SUCCESS, including owned-session.
- Windows WSP `40805865221` SUCCESS, including funded owned-session.
- Linux `40805865248`: Q05 owned-session, native contracts, Qt, headless, Q04,
  and both frozen wallet jobs SUCCESS. `developer-core` was still running when
  `18774a7` was pushed.

## Two startup fixes

`18774a757dc871863c8c69da8c01842f55b1d69a` re-attests the same Popen only before
the first verified RPC. A ready, exited, or foreign process stays faulted.
Ordinary profile failure still quarantines `_read_cli`.

This commit stops macOS and Linux directory checks from treating child creation
(link count and timestamps) as directory replacement. Inode, owner and mode
still refuse. File envelope identity still includes mtime and size. Continuous
datadir updates during startup no longer fail every bootstrap read that the
re-attest path has to retry.

## Next

Read macOS `real-core-regtest` on this commit for Q02 `UNAVAILABLE`, and Linux
`developer-core` on `f6672a7` / `18774a7` if that job fails. Q05 remains unaccepted.
