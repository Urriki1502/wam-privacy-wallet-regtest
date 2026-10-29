# Engineer 2 checkpoint — cross-platform real-Core owned-session CI

Branch `cursor/q05-history-pagination-9c81`. Codex Draft #138 remains independent
(`feature/issue45-q05-managed-core-stage-a-20261027`). Canonical ledger: 37 Q05
PENDING, `accepted=false`. No second PR, no merge.

## Evidence at `f6672a7d9219f4432f272f324ed2fd9ced0b89fb`

Push workflows:

- Windows receive `40805865221` SUCCESS, including funded owned-session.
- Windows smoke `40805865225` SUCCESS, including owned-session.
- macOS `40805865241` owned-session SUCCESS. Job `real-wamd` FAIL:
  Q02 case `UNAVAILABLE`, `CORE_LOCAL_NETWORK_POLICY_DENIED` then
  `CORE_RPC_SCOPE_FAULTED`, then `Q02_NODE_START_TIMEOUT`. The start loop
  treated a pre-ready quarantine as warmup and never re-attested the same Popen.
- Linux `40805865248` owned-session, native Qt, headless and Q04 SUCCESS.
  developer-core and frozen were still running at inspection.

Fix on top of that SHA: `recover_unready_owned_scope` re-attests the same
Popen only while that owned scope has never completed a verified RPC. A ready,
exited, or foreign process stays faulted. Profile failure still quarantines
ordinary `_read_cli` calls; restoring the file does not clear the scope.

## This milestone

Shared harness `src/wam_regtest/q05_owned_lifecycle.py` plus CLI
`scripts/probe_q05_owned_session.py`.

Adapters: macOS Keychain, Windows Credential Manager, Linux approved manifest
`e77a5745263b8fdbcffdb282af22800b6f7805f033c09f00738e997150a0f806` + NativeRootWitness.

Jobs:

- macOS `real-core-regtest.yml` / `q05-owned-session`
- Windows `windows-x64-real-core-regtest.yml` / `q05-owned-session`
- Windows `windows-x64-wsp-real-receive.yml` / `q05-owned-session-funded`
- Linux `linux-experimental-regtest.yml` / `q05-owned-session`

`q05-linux-supervisor-contracts.yml` stays contracts-only.

## Dispatch (owner-local gh if cloud 403)

```bash
gh workflow run real-core-regtest.yml --repo Urriki1502/wam-privacy-wallet-regtest --ref cursor/q05-history-pagination-9c81
gh workflow run windows-x64-real-core-regtest.yml --repo Urriki1502/wam-privacy-wallet-regtest --ref cursor/q05-history-pagination-9c81
gh workflow run windows-x64-wsp-real-receive.yml --repo Urriki1502/wam-privacy-wallet-regtest --ref cursor/q05-history-pagination-9c81
gh workflow run linux-experimental-regtest.yml --repo Urriki1502/wam-privacy-wallet-regtest --ref cursor/q05-history-pagination-9c81
```

Inspect `head_sha` against the pushed commit. Do not reuse old receipts.

Owner macOS dispatch `40788571264` ran `85d5c5c` (not this SHA). Job
`q05-owned-session` FAIL: `SupervisorStorageError` at stage KEYCHAIN because
`--root ${RUNNER_TEMP}/q05-owned-empty` is not `wam-fusion-core-[0-9a-f]{16}`
and GitHub macOS temp carries inherited ACLs. Harness now allocates
`private_temporary_directory` + a correctly named profile. Re-dispatch this
HEAD.
