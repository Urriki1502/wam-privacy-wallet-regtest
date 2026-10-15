# Linux integration handoff — 15 October 2026

Only application repository: https://github.com/Urriki1502/wam-privacy-wallet-regtest

Worktree: `/Users/dinhdang/Documents/Codex/2026-10-14/wam-privacy-wallet-real-regtest-macos/work/linux-regtest-integration`
Current documentation branch: `docs/linux-qualification-checkpoint-20261015`.
Last implemented CODE: `be294c19dba02b5d8016cf76520b40975ee20c96` (Draft PR34).
Main remains `50e1ea94df61b8400cbab3bffe0fbdd285c6b419`.
No merges/release. Preserve all existing branches, worktrees and uncommitted work.

## Mandatory exclusive engineering protocol

Before edits inspect actual cwd/remotes/branch/history/status, open PRs/current
CI, and active Codex threads. Acquire
`python3 scripts/engineering_lease.py --hold` in a persistent TTY. Exit73 means
another cooperating engineering session holds the lease: refuse changes.
Keep the lease alive through engineering; release with newline when finished.
The OS flock is in the common Git directory and spans worktrees. Death releases
it. This is advisory/cooperating protection, not an arbiter over sessions which
ignore it. Refuse engineering if another active thread is observed.

Never modify the legacy wallet or upstream WAM source. REGTEST/test keys only;
no mainnet, real funds, personal keys, production claim, weakened security gate,
synthetic RPC/blockchain acceptance or automatic merge.

## Actual scheduled continuation

Heartbeat `linux-regtest-single-continuation` fired once at12:07:22 UTC /
19:07:22 Asia/Ho_Chi_Minh15October2026. Only the current thread was active;
lease54700 acquired. Initial clean HEAD was e16ecf28dfcd1a32bb2d1f9dbfc8e9e325bd249c.
Fetched official origin and refreshed live PR/check state before implementation.
All seven e16 checks PASS; prior milestone engineering was not repeated.

Separate resume log:
`/Users/dinhdang/Documents/Codex/2026-10-14/wam-privacy-wallet-real-regtest-macos/outputs/linux-resume-20261015T121033Z.log`.
Usage tool actually returned ordinaryUsageAllowed=true, primary2% at resume;
no assumed credit reset or reset credit used. No usage-limit failure encountered.
The one-shot automation was explicitly updated to **PAUSED** and its saved TOML
verified. No second scheduler, recurring retry, launchd job or paid reset.
The scheduler uses the local Codex app, not a CLI process installation.

## Stack and completed units

PR9 is merged. Existing PR17 documentation and PR18–28 Windows/Fusion stack
remain open; do not merge/rewrite them as cleanup. Integration base PR28 is
`a869a36a76ae3f3d9e0e39b4eea2135f01649c37`.

Linux stack (all Draft):

| PR | Branch | Head / delivered unit |
| --- | --- | --- |
|29|feature/linux-regtest-integration-20261015|576082d227ccd9eb139686ded431c69c07399237; corrected upstream developer Core build, ELF/library/hash gates, real101 blocks, lease|
|30|feature/linux-private-custody-20261015|240881bfe457c9e0fdafc5440cf3036c1d754196; owner/ACL/no-follow/private publication/OS lease contracts|
|31|feature/linux-root-anchor-witness-20261015|7335633e380ebaa4035b7897e425886b1a29384d; actual independent root UID witness, CAS/flock/crash/UID refusal|
|32|feature/linux-headless-wallet-20261015|a63c3716a453c9e26c2ace815ff37b7783d43366; shared WalletSession headless real E2E, startup --recover-backup|
|33|feature/linux-fusion-qt-20261015|9aa8607cc512c419c6800ccd2fd858ef7b31944f; existing Fusion Qt, real native xcb workers/approvals/recovery, attested xcb closure|
|34|feature/linux-frozen-wallets-20261015|be294c19dba02b5d8016cf76520b40975ee20c96; FINAL frozen no-Qt headless and native Qt executable gates/manifests/tarballs|

LINUX01 audit and LINUX02 Core are complete. Linux custody primitives/root
witness and shared source/frozen headless/Qt paths now have native runner
acceptance. This is scoped developer REGTEST acceptance, not production custody.
LINUX08 portable migration is design only, execution HOLD; do not remove native
v1/macOS, v2/Windows or v3/Linux authenticated platform/anchor fields.

## Native evidence and artifact provenance

Authoritative detailed matrix, artifact links/checksums and explicit limits:
[LINUX_QUALIFICATION.md](LINUX_QUALIFICATION.md).

PR32 a63c371 actual source recovery run38732813560 PASS. Its exact startup
selector reopens original keys/reservations on two fresh Core chains; headless
no Qt, genuine PSBTv2/native sign, actual mempool/change, reorg1/12/100,
lost actual broadcast reply, wrong password, stale-before-sign/broadcast PASS.
Downloaded report in project outputs/linux-headless-qualified-a63c371.

At PR34 be294c1 run38733851062 native-contracts, source headless, source xcb Qt,
frozen-wallet(headless), frozen-wallet(desktop) PASS. Source Qt proves six
Fusion screens, native Cancel/Sign/Broadcast boundaries and workers, real
recipient100000 atoms/change, backup/lock/wrong-password/recovery and original
keys/irreversible locks on a fresh real Core native window. No synthetic RPC or
crypto. Xvfb Qt Auto events were unavailable; qt_auto_events_verified=false.
Manual Light/Dark passed. Human GNOME/KDE/OS appearance signoff remains pending.
Repeated developer Core rebuild also PASS; all six jobs in38733851062 PASS.
Exact-head Windows final regression38734182038 also PASS. Linux six jobs,
macOS source/frozen, canonical vectors and Windows source/frozen/DPI are all
PASS for codebe294c1; this is not human/operator or production qualification.
Mac source and FINAL app/DMG38733851084 and vectors38733851085 PASS.
Windows exact code dispatch38734182038; source/Qt/vector/frozen/DPI PASS.
Do not substitute older green heads for any future pending head.

Artifacts after actual frozen acceptance:
headless11970254824, desktop11970854820, source Qt11971044723,
source headless11971498887, all under run38733851062 and named with fullbe294c1 SHA.
Linux manifest records PR headbe294c1 and actual PR merge checkout
b6824f9990d04db1553465ac32964ade8e0e22f5 separately.
Local host is macOS ARM64: downloaded ELF/member/hash inspection is distinct
from native Linux execution. See project outputs/linux-engineering-review-20261015
and outputs/linux-frozen-qualified-be294c1. Downloaded Linux tarballs independently match180/441 regular files,0/25 links,
all original Core/branding/WSP identities; exact checksums are in the matrix.
Current macOS and Windows artifacts were also downloaded/inspected in project
outputs/cross-platform-qualified-be294c1: Windows341 files/PE64/Core/PNG and33
pinned WSP files (exact reversible Git CRLF checkout); MacZIP/DMG/ARM64 Core,
originalPNG/ICNS,33 exact WSP files and111 safe links. Downloaded DMG verifies
VALID. The newly downloaded FINAL Mac app PASSed real-Core Cocoa E2E on this
actual ARM64 MacBook (exit0): payment/change, security/reorg/uncertainty, backup,
lock/recovery/fresh-Core reopen and Qt appearance events. Receipt/log/screens in
outputs/cross-platform-qualified-be294c1/macbook-cocoa. This is automated local
MacBook testing, NOT human Finder/OS-setting signoff.
No native Windows/Linux execution on this Mac was claimed.
Source Qt screenshots were actually
viewed for compact overview, send, light overview, Security, Settings and exact
native approval. Human visual acceptance is still PENDING_OPERATOR.
Local full128 tests PASS with33 platform skips and unchanged independent wallet
auditor PASS. Those Mac skips do not count as native Linux coverage.

Initial Qt run3de1c75 failed native xcb loading. Added full dependency closure
and ldd gate2240163; ldd identified missing libxcb-shape.so.0, fixed9aa8607.
No offscreen replacement or security gate removal. PR34 carries those fixes
via cherry-picks; PR33 remains its intended review base. Preserve lineage;
review overlapping build-workflow changes when eventually merging bottom-up. Superseded failed Linux
runs38733164940/38733578892/38733750568 were cancelled to avoid redundant builds;
current head's complete gates remain required.

## Immutable Core/WSP identities

Qualified developer Core run38697805476 at576082d, artifact11955725964.
Approved manifest SHA256:
`e77a5745263b8fdbcffdb282af22800b6f7805f033c09f00738e997150a0f806`.
wamd `ccc9f0f1d299a1e98a49ff83859aa03e994e83e6ea4b7cd60c327eb1e0e8e4d6`;
CLI `ada9dabd56d0859b9d64c0b20a05c33cb039b2573f75088443b45c35d5379652`.
WAM82a1487fd86f7021b1b9fc1524d267fca126f7d4 (GNU_STACK fix);
Bitcoin32efe850438ef22e2de39e562af557872a402c31;
RandomX102f8acf90a7649ada410de5499a7ec62e49e1da.
WSPac55f13423620252bdbf848c7e8a280c3b84721e. No upstream WAM edits.

Published Linux v0.1.11 executable-stack binary remains rejected. This is an
explicitly approved developer source build, NOT an official signed release.
System loader/libraries are exactly manifest-pinned and sanitized subprocess
environments remain required. No automatic trust for upgraded dependencies.
Artifact retention14days: if expired or host closure differs, stop/qualify a
fresh exact build and independently review it; never bypass the approved pin.

## Architecture / remaining work

Keep compact shared WalletSession/Vault/WSP/Core; no new signer or replacement
cipher. Linux runtime requires explicit manifest approval and actual root
peer before funding or wallet creation. Root witness is optional administrator
provisioning; app never installs/starts it or invokes sudo. Software-only local
file anchors remain forbidden for spending. Backups retain platform binding;
uncertain/signed reservations remain irreversible through lock/recovery/reorg.

The original root Core builder failed pristine RandomX's grep under set-e.
The fix pre-seeds only the exact official pinned GNU-stack NOTE block onto
pristine RandomX before the official fetch/patch/configure/make sequence.
No upstream WAM source changes; final ELF RW/RPATH/library checks stay required.
Do not use upstream install --build-only (it writes host services).

Next engineering (current scheduled continuation is complete):
1. Refresh all latest PR heads/CI/artifacts; finish any actual regression defect.
2. Review focused stack bottom-up while preserving Draft/no-merge disposition.
3. Operator Linux desktop/OS Auto testing, explicit reviewed root-witness
   provisioning/restart/anchor-loss handling; no automatic privileged installer.
4. Review PORTABLE_BACKUP_FOUNDATION.md freshness/transfer protocol before any
   cross-OS import. Design only is not migration acceptance. Do not claim Linux08
   complete without actual source/destination OS/native-anchor evidence.
5. Remaining production-hardening limits: unlocked plaintext SQLite, best-effort
   memory clearing,16 epochs,10000 witness generations, ambiguous anchor/snapshot
   publication availability, root/whole-store rollback, power-loss durability,
   executable-to-loader binding. No automatic reset or old-lock release.

Useful local verification runtime:
`PYTHONPATH="$PWD/src" ../wam-privacy-wallet-regtest/.venv/bin/python`.
Local Qt contracts need QT_QPA_PLATFORM=offscreen in the shell sandbox. Real
Linux acceptance uses Ubuntu24.04 x86_64/xcb; do not execute Linux ELF on this Mac.
The no-Qt package job must not install PySide/shiboken; desktop is a separate job.
Two original macOS/vector workflows and existing Windows/Linux workflows retain
platform gates; do not add a workflow per feature or collapse native acceptance.
