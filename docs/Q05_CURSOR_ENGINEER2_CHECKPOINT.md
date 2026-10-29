# Engineer 2 checkpoint — funded crash recovery on signed Windows

Source HEAD: `37a2bf18871e710c71d17e71e50a19f2cc8732fe`.
Branch `cursor/q05-history-pagination-9c81`. Codex Draft #138 stays independent
(`feature/issue45-q05-managed-core-stage-a-20261027` at `b3046f82`).
Canonical ledger: 37 Q05 cases PENDING, `accepted=false`. No merge.

## This SHA, Windows funded

`gettxoutsetinfo none "<tip>" true` runs before `process.kill()`. Core v28
`ForceFlushStateToDisk` runs before the tip read. `use_index` false with a
named block is rejected, so the quoted tip uses `use_index` true. The recovery
floor stays at that flushed height. No second supervisor, PID adoption,
datadir deletion or spend replay.

Signed Windows Core funded receipt PASS:
https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40810596391
`funded_same_owner_crash_recovery`, `sign_broadcast`, `concurrent_owner_refused`,
`same_owner_reattach` and `wallet_restore` are PASS. Original pid 3288,
recovered pid 4404, `automatic_wallet_transaction_replay` false,
`pid_adoption` false, `core_trust` official-signed-v0.1.11. This is one OS
receipt, not canonical Q05 acceptance.

## Retained failures

`4d27f1b` Windows funded failed `CORE_RPC_DENIED` at
`FUNDED_SAME_OWNER_CRASH_RECOVERY` (bare tip, `use_index` false):
https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40810343337

`ca7bb85` Windows funded failed `MANAGED_RECOVERY_HEIGHT_REGRESSED` after one
extra miner block and the same-Popen wait:
https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40809932361

`5770930` failed the same height code:
https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40809138451

## Trigger SHA `a7c3f81` reattach

All four workflows for same-owner reattach completed success. They do not
prove the later flush.

- macOS https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40808964924
- Linux https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40808964955
- Windows smoke https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40808964943
- Windows funded https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40808964946

`ca7bb85` Windows smoke `40809932341` succeeded for the empty owned session
(`crash_fail_closed`, `same_owner_crash_recovery`, `concurrent_owner_refused`,
`same_owner_reattach`). That job does not assert `wrong_core_refused`.

## Still open on this SHA

macOS https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40810596567
Linux https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40810596535
Windows smoke https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40810596382

## Next

Read macOS and Linux funded receipts for `funded_same_owner_crash_recovery`
on `37a2bf1`. A flush RPC rejection or a tip that stays below the floor is a
real FAIL. Do not push another flush variant while those runs are the proof.
Q05 remains unaccepted.
