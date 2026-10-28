# Q04 regression investigation on Q05 PR #138 — 28 October 2026

Failed run 40539812345, PR head `d52187832250a4852a8387297440038e6f192611`,
actual checkout `c3e56966c6656638ff6a892947edcdfc4aa4a4eb` (GitHub merge ref).
Full logs were read and retained outside the checkout for jobs:

- [q04-miner-coexistence 122315978220](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40539812345/job/122315978220): genuine `Q04_BUSY_NOT_OBSERVED` at the attachment busy assertion.
- [frozen desktop 122315978170](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40539812345/job/122315978170): build and Q02/Q03/native wallet completed, then frozen `q04-external-miner` exited 2 with `LINUX_FROZEN_UNCLASSIFIED`. The original log cannot identify the inner exception; it is not proof of a loader/build failure.

Both used Ubuntu 24.04.5 runner image 20261012.334.1 and the immutable Core
artifact 11955725964, producer run 38697805476, ZIP SHA-256
`3076f3ea9cc9f94457c5b1984fcfcaadb91c001ac74b8ef175b681b599225b5c`.
The log confirms the downloaded digest. No trust downgrade or new Core build.

Q04 runner/busy-probe/fixture/external transport and Linux frozen entry/workflow
are byte-identical to qualified main snapshot `c316671ac0e483640736e1b3c599a8b2541a839a`.
Main exact-head run 40490308482 passed these scopes. Prior PR head d624abc3 also
passed both jobs in run 40534359675. These passes do not erase d521878 failures
or qualify the new fix. There is no evidence to label these infrastructure-only.

Confirmed fixture defect: busy induction submitted six 3-second long polls,
then used `sleep(.5)` as its sole readiness criterion. It did not prove dispatch
or queue saturation before requiring four busy replies through native attachment
attestation/retries. Scheduling and completed long polls can therefore leave
that requirement unexercised. The d521 native failure is missing busy evidence;
its exact runner timing cannot be recovered from the old log. Different results
with identical Q04 source support a timing-sensitive fixture, not a demonstrated
Q05 transport change. Product behavior is not declared PASS from this analysis.

Confirmed reporting defect: the frozen exception allowlist omitted
`RpcContentionError`; Q04 fixed contention codes were hidden as UNCLASSIFIED.
The original desktop inner failure remains unclassified until new executable
evidence, rather than being asserted to equal the native busy failure.

Narrow repair: require all six requests transmitted AND an actual Core 503 on
the load channel before attachment probing, bounded by five seconds. Long polls
hold ten seconds (45-second client/drain budget) to span attestation/backoff.
The actual Fusion assertions are unchanged: exactly four attachment busy replies,
backoff intervals, zero extra coalesced calls, GUI behavior, recovery and denied
write/no retry. No synthetic busy injection, assertion relaxation or PASS fallback.
Receipt adds readiness and real load-rejection counts. Failure to saturate is a
distinct FAIL. Frozen reporting adds only the known error class and still checks
the strict code regex and fails with exit 2; arbitrary exception text stays hidden.

Supplemental Q04 tests (16) PASS before push: delayed dispatch, incomplete/no-503
readiness refusal and redacted frozen errors. Targeted native/frozen Linux jobs
must pass on the repair source before Q05 journal engineering resumes. No full
workflow manually redispatched; automatic PR CI is retained. Any new FAIL remains
unresolved and suspends broader Q05 work.

## Repair recheck completed

Exact repair source a89848b, Linux run 40615131718: native Q04 job 122576258488,
contention 122576258508 and frozen desktop 122576343826 / headless 122576343783
all SUCCESS. Native evidence archive 12784418762 was downloaded and SHA-256
verified as b1213564e6441ef8adb7f24c1f63b5e76ff1e41dc41a8b7bb0cdac75f79010ea.
It records 3 real load 503s, 4 attachment 503s, bounded backoff, coalescing and
write-no-retry. Both final-executable logs independently contain Q04 receipts
with 4 attachment 503s and real Core hashes; desktop GUI coalescing PASS. See
`docs/evidence/q05/q04-repair-a89848b.json`. No full frozen archive re-audit or
Q05 integrated-package claim is made. These results resolve the CI recheck on
repair source; they cannot reconstruct the old frozen inner error.

Q05 journal work remains STOPPED because the single owner-authorized macOS
native retest failed at authenticated start and left the original supervisor /
Core live in recovery-needed state. No further native attempt or cleanup followed.
