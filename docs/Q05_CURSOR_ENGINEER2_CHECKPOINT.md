# Engineer 2 checkpoint — cross-platform real-Core owned-session CI

Branch `cursor/q05-history-pagination-9c81`. Codex Draft #138 remains independent.
Canonical ledger: 37 Q05 PENDING, `accepted=false`. No second PR, no merge.

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
