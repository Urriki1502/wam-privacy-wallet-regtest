# Engineer 2 checkpoint — funded same-owner crash recovery

Branch `cursor/q05-history-pagination-9c81`. Codex Draft #138 stays independent
(`feature/issue45-q05-managed-core-stage-a-20261027` at `b3046f82`).
Canonical ledger: 37 Q05 cases PENDING, `accepted=false`. No merge.

## This change

Parent `a7c3f81ce5891cd123e7aab0c121cf70e9d24f4a` reattaches the wallet on the
same live Core after the lease refusal. This commit, on that parent, kills the
original Popen only on the funded path after a confirmed spend and calls
`recover_dead(authorized=True)` on that owner. The restored snapshot must keep
one copy of the broadcast txid, history, receive count, confirmed atoms and
height. The reference, `wam.conf` and datadir stay. The spend is not broadcast
again. Lease refusal and same-owner reattach then run on the recovered Core.
Empty crash recovery is unchanged. Receipt schema is `q05-owned-session-native/v5`.

Local `test_q05*.py`: 116 PASS. `test_q02_contracts.py`: 19 PASS, 1 skipped.
This host has no genuine Core binary. This commit is not a native PASS.

## Parents already observed

`9e1766e` empty `same_owner_crash_recovery` succeeded in the owned-session jobs
of macOS `40808378718`, Linux `40808378513` and Windows smoke `40808378464`.
Windows funded `40808378632` succeeded without that scenario.

`792701e` Windows smoke `40808542596` and Windows funded `40808542569` succeeded
with `concurrent_owner_refused`. macOS `40808542544` was queued and Linux
`40808542678` was in progress. Those runs do not include this funded crash.

`a7c3f81` same-owner reattach is the parent of this commit. Do not treat a
`792701e` receipt as proof of reattach or of funded crash recovery.

`5b5e4c1` Linux `40807061493` and macOS `40807061511` completed SUCCESS.

## Next

Read this commit's funded receipts for `funded_same_owner_crash_recovery` on
macOS, Linux and Windows, together with `same_owner_reattach`. A datadir lock
or `MANAGED_RECOVERY_HEIGHT_REGRESSED` must be fixed without deleting chain
data, adopting a PID, or replaying the spend. Q05 remains unaccepted.
