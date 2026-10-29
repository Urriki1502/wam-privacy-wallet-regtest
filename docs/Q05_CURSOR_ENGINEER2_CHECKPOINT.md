# Engineer 2 checkpoint — funded crash height reload

Branch `cursor/q05-history-pagination-9c81`. Codex Draft #138 stays independent
(`feature/issue45-q05-managed-core-stage-a-20261027` at `b3046f82`).
Canonical ledger: 37 Q05 cases PENDING, `accepted=false`. No merge.

## Failure being repaired

`5770930` Windows funded owned-session failed
`MANAGED_RECOVERY_HEIGHT_REGRESSED` at `FUNDED_SAME_OWNER_CRASH_RECOVERY`.
Sign/broadcast had passed. Run
https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40809138451
artifact `q05-owned-session-funded-windows-x64-5770930f7d34dbde1b99c9022f3d2cf4bbe6b2bf`.

The same-owner restart treated the first short `getblockchaininfo` as a final
shorter chain. Recovery boot now stays on that Popen until the attested tip
loads or the start deadline expires. A chain that remains below the floor
still raises `MANAGED_RECOVERY_HEIGHT_REGRESSED`. Before the kill, one
miner-address block is generated and the floor stays at the confirmed spend
height. No second supervisor, PID adoption, datadir deletion or spend replay.

Parent `cbb5361` refuses a missing Core directory and an untrusted mainnet
receipt before `start`. Its Windows empty job `40809458244` then failed
`FileNotFoundError` in `FAIL_CLOSED` because the tampered-core parent
directory was never created. The harness now creates that private profile
before the refusal. The qualified receipt is still not mutated.

## Retained parent evidence

`9e1766e` empty crash recovery succeeded on macOS `40808378718`, Linux
`40808378513` and Windows smoke `40808378464`. `792701e` Windows smoke
`40808542596` and Windows funded `40808542569` succeeded with
`concurrent_owner_refused`. `a7c3f81` added same-owner reattach.
`5b5e4c1` Linux `40807061493` and macOS `40807061511` completed SUCCESS.
None of those receipts prove this funded-crash repair.

## Next

Read this commit's funded receipt for `funded_same_owner_crash_recovery` on
Windows, then macOS and Linux. Q05 remains unaccepted.
