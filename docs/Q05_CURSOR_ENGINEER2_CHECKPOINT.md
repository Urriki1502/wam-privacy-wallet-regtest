# Engineer 2 checkpoint — flush the confirmed tip before kill

Parent `ca7bb859b19e5b70f6cba64a2c93bf86d1e5b689`.
Branch `cursor/q05-history-pagination-9c81`. Codex Draft #138 stays independent
(`feature/issue45-q05-managed-core-stage-a-20261027` at `b3046f82`).
Canonical ledger: 37 Q05 cases PENDING, `accepted=false`. No merge.

## Failure being repaired

`ca7bb85` Windows funded owned-session still failed
`MANAGED_RECOVERY_HEIGHT_REGRESSED` at `FUNDED_SAME_OWNER_CRASH_RECOVERY`
after the sacrificial miner block and the same-Popen height wait.
Sign/broadcast had passed. Run
https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40809932361
Receipt: `failure_code=MANAGED_RECOVERY_HEIGHT_REGRESSED`.

The earlier `5770930` receipt is
https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40809138451
with the same code. One extra `generatetoaddress` did not leave the confirmed
tip on disk. `4d27f1b` calls `gettxoutsetinfo none <bare tip> false`. Core v28
rejects that pair (`use_index` false with a named block) and its CLI
JSON-parses `hash_or_height`, so a bare hash never reaches RPC. This commit
passes a quoted tip and `use_index` true. `ForceFlushStateToDisk` still runs
before the tip read. The recovery floor stays at that height. The same-Popen
wait from `f3dc3c0` remains. No second supervisor, PID adoption, datadir
deletion or spend replay.

Local `unittest discover -s tests -p 'test_q05*.py'`: 118 PASS.
`test_q02_contracts.py`: 19 PASS, 1 skipped. This host has no genuine Core
binary. Canonical cases stay PENDING.

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

Read this commit's Windows funded receipt for
`funded_same_owner_crash_recovery`. If the flush RPC is rejected, keep the
height floor and fix the call. Do not delete chain data. Q05 remains
unaccepted.
