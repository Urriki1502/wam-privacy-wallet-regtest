# Linux integration handoff — 15 October 2026

Only application repository: https://github.com/Urriki1502/wam-privacy-wallet-regtest

Worktree: `/Users/dinhdang/Documents/Codex/2026-10-14/wam-privacy-wallet-real-regtest-macos/work/linux-regtest-integration`
Branch: `feature/linux-headless-wallet-20261015`
Integration base / last completed upstream commit: `a869a36a76ae3f3d9e0e39b4eea2135f01649c37` (PR28 Fusion 2.0).
Current PR: https://github.com/Urriki1502/wam-privacy-wallet-regtest/pull/32 (Draft, stacked on31/30/29/28).
Last completed CODE commit: f9c0eedbabe16951839f2dac563b5123b1beb623 (Linux shared headless wallet, strict Core directory guard).
Next unit: Linux Qt over the existing Fusion design, then frozen headless/desktop packages. No merge/release.
Main remains `50e1ea94df61b8400cbab3bffe0fbdd285c6b419`.
PR9 merged; PR18–28 remain stacked open Draft. Do not merge or rewrite them.

## Completed / actual evidence

LINUX-01 audit: platform seams are custody.py, core.py, WalletSession,
CheckpointVault and read models; WSP cryptography/scanner remains pinned
`ac55f13423620252bdbf848c7e8a280c3b84721e`. Qt is optional and imported lazily
by CLI, so headless can reuse WalletSession without importing PySide6.
Mac backups use v1/Keychain; Windows v2/Credential Manager. Neither permits
silent cross-platform migration. No Linux custody/anchor is qualified yet.
PR28 macOS source/frozen38659533440, vectors38659533447 and Windows
source/frozen38659533579 are PASS. That does not qualify Linux.

Core build target: `wamcoin-core-dev/wam-coin` commit
`82a1487fd86f7021b1b9fc1524d267fca126f7d4`, containing the GNU_STACK fix and
ELF guard correction. Bitcoin v28.1 commit32efe850438ef22e2de39e562af557872a402c31;
RandomX1.2.1 commit102f8acf90a7649ada410de5499a7ec62e49e1da.
Published Linux v0.1.11 remains unacceptable (RWE stack); never substitute it.
Developer source build is NOT an official signed release. No upstream source
changes in this application repo. Install --build-only still writes host service
units; use the reviewed upstream fetch/patch/configure/make steps on ephemeral CI.

## Exclusive engineering / scheduled continuation

Before changing files: inspect active Codex threads and acquire
`python3 scripts/engineering_lease.py --hold` in a persistent TTY. If it exits73,
another cooperating engineering session holds the lease: stop without changes.
Keep that TTY alive through engineering, release by newline when finished.
The common Git directory OS flock spans all worktrees; process death releases it.
This advisory lease cannot control a session which ignores the protocol. Refuse
work if another active thread is observed; the Codex thread scheduler serializes
this chat. Do not claim an all-process OS arbiter or CLI launchd installation.

Local Codex heartbeat `linux-regtest-single-continuation` was installed ACTIVE,
one future run at19:06:55 Asia/Ho_Chi_Minh, 15 October2026 (12:06:55 UTC), about
five hours after execution began07:06:55 UTC. Saved automation.toml verified;
CLI0.162.0-alpha.17.2 supports exec/resume and is authenticated via ChatGPT.
The installed continuation uses the local app scheduler, not launchd or an
embedded credential. App/host must be available. No guarantee of renewed credits.
An initial COUNT2 attempt was auto-review rejected; no such schedule installed.
One-shot COUNT1 schedule replaced it. Do not add a second scheduler.

At resume create `outputs/linux-resume-<UTC>.log`, inspect actual lease/threads,
fetch, check PR/CI and read this document. Run only the next incomplete unit.
Disable automation after successful continuation. If usage-limited, log the
actual error; zero automatic retry is the bounded policy (no recurring charges).

## Next / remaining milestones

LINUX-02 PASS: run38697805476 at576082d227ccd9eb139686ded431c69c07399237.
Artifact11955725964, name linux-developer-core-576082d227ccd9eb139686ded431c69c07399237.
Manifest SHA256 e77a5745263b8fdbcffdb282af22800b6f7805f033c09f00738e997150a0f806.
wamd ccc9f0f1d299a1e98a49ff83859aa03e994e83e6ea4b7cd60c327eb1e0e8e4d6;
CLI ada9dabd56d0859b9d64c0b20a05c33cb039b2573f75088443b45c35d5379652.
Both ELF64/stackRW;101 actual blocks/genesis/zero peers/process+datadir cleanup.
Artifact downloaded to project outputs/linux-core-qualified-576082d. Not signed release.
LINUX-03 primitives now implemented in linux_private_storage.py; native contracts
for ACLs, actual WSP encryption, create-only publication, processes and crashes
passed in native-contracts of38698476013. Its builder repeated all custody tests
without WSP installed and failed before build;240881b limits that builder to
Core parser tests after the mandatory full native contract job. Retry38698811352.
On macOS,6 foreign/ELF contracts PASS and10 native-only cases skip;
these are not Linux acceptance. Spending explicitly refuses until an independent
trusted anchor is qualified; see LINUX_CUSTODY_POLICY.md. Do not wire a plain
file anchor into WalletSession to make tests pass.
Root witness native-contracts PASS in38699751140 (actual root service, UID
refusal, CAS, stale writers, contention, killed client/server, restart). Root/OS
rollback and power-loss remain unqualified. Explicit runtime/anchor v3 now
connects the shared vault; no default Linux enablement, no root auto-install.
Headless source app and real acceptance added; CI pending. Local full contracts
128 PASS (33 platform skips), independent unchanged macOS security auditor PASS.
Next: inspect new PR headless-wallet job, fix actual native failures, then
qualify source before frozen/Qt work. Keep new Linux CLI startup-recovery option
as an explicit remaining improvement; backend fresh-chain recovery is in gate.
Then finish LINUX-03/04 real wallet and platform regression gates;
LINUX-04 shared headless session; LINUX-05 existing Fusion Qt;
LINUX-06 real payment/recovery/reorg/uncertainty gates;
LINUX-07 frozen native headless/desktop packages;
LINUX-08 authenticated portable-export design without weakening native anchors.

First native run38697520671 passed parser contracts, then failed inside pinned
upstream fetch-upstream.sh: unmatched grep under set-e aborts pristine RandomX
before its NOTE insertion. Build preparation now extracts ONLY that exact NOTE
block from the pinned official script and pre-applies it to pristine RandomX;
WAM source is unchanged and final ELF RW validation remains mandatory. No
Core startup/mining occurred in the failed run. Build retry pending.
Engineering lease contention tested on local Mac: second process exits73.

Linux Core and SOURCE HEADLESS wallet PASS; Qt/frozen/portable recovery remain pending. Current host is macOS ARM64. CI Linux must provide
actual ELF/process/scanner/SQLite/Qt evidence. Mock/negative units are supplementary.
No mainnet, personal secrets, real funds, production qualification or automatic merge.

## Latest verified checkpoint (authoritative, 15 October2026)

At code f9c0eed, Linux run38701530294 native-contracts and headless-wallet PASS.
Headless artifact11956317856: linux-headless-wallet-evidence-f9c0eedbabe16951839f2dac563b5123b1beb623.
Actual CLI subprocess, root witness, no PySide6, real PSBTv2 signing, mempool,
recipient100000 atoms, confirmed change, reorg1/12/100, lost actual broadcast
reply, original-key recovery on TWO fresh chains, irreversible reservations and
stale-before-sign/broadcast refusal PASS. No synthetic RPC/crypto. Reports under
project outputs/linux-headless-qualified-f9c0eed and linux-core-qualified-576082d.
Core binary and approved manifest hashes independently checked after download.

Exact code-head macOS source and28 canonical vector suites PASS. macOS frozen,
Windows regression/frozen and repeated developer Core build still running at
checkpoint; refresh actual state before any all-platform claim. PR29 all checks
PASS. PR30/31 native contracts passed; stacked review remains Draft, no merges.

Next actions, in order:
1. Refresh PR32 runs38701530294 (Linux),38701530304 (Mac),38701530301 (Windows),
38701530265 (vectors), and any documentation-head reruns. Diagnose failures;
never weaken gates. Code-qualified HEAD is f9c0eed; this final checkpoint commit
changes documentation only. Preserve the stack and uncommitted work.
2. Add startup --recover-backup selection to the interactive headless launcher;
backend same-key fresh-chain recovery already passes, but product startup still
initializes fresh sessions. Do not repeat cryptographic/reorg work unnecessarily.
3. LINUX-05: configure existing OperationalWalletWindow with approved Linux
runtime; correct platform labels/fonts/screenshot names, preserve six screens,
consent/clear/worker gates. Native Qt xcb/Xvfb actual-Core acceptance, independent
headless no-Qt gate. Do not claim human Linux desktop/OS theme signoff.
4. LINUX-07: separate native frozen CLI and desktop artifacts, bundled qualified
Core/WSP closure, preserved Core bytes/stackRW, manifests/checksums; execute the
FINAL binaries with actual wallet E2E before qualification. Root witness stays
optional administratively provisioned; app must not auto-install privileged code.
5. LINUX-08: versioned portable export/migration policy. v1 Mac/v2 Win/v3 Linux
remain platform-bound. No cross-platform recovery PASS without actual source and
destination OS tests. Root/whole-store rollback and power-loss remain unqualified.

Scheduler still installed ACTIVE: linux-regtest-single-continuation, one future
run19:06:55 Asia/Ho_Chi_Minh15Oct2026 /12:06:55 UTC. Local app scheduler, NOT
launchd/CLI process launch. App/Mac availability required; credits not guaranteed.
Existing prompt enters this worktree and reads this file. Acquire engineering
lease and inspect active threads before writes; write separate resume log,
then disable the one-shot after successful work. No automatic paid retries.
