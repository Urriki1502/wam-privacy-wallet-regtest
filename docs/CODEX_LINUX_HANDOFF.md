# Linux integration handoff — 15 October 2026

Only application repository: https://github.com/Urriki1502/wam-privacy-wallet-regtest

Worktree: `/Users/dinhdang/Documents/Codex/2026-10-14/wam-privacy-wallet-real-regtest-macos/work/linux-regtest-integration`
Branch: `feature/linux-root-anchor-witness-20261015`
Integration base / last completed upstream commit: `a869a36a76ae3f3d9e0e39b4eea2135f01649c37` (PR28 Fusion 2.0).
Current base PR: https://github.com/Urriki1502/wam-privacy-wallet-regtest/pull/30 (Draft, stacked on29).
Last completed engineering commit: 240881b (native custody and builder dependency fix).
Next Draft PR: optional independent Linux root witness; no wallet activation yet.
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

Next: inspect Linux run38697805476 for LINUX-02 native build/mining/cleanup.
LINUX-03 primitives now implemented in linux_private_storage.py; native contracts
for ACLs, actual WSP encryption, create-only publication, processes and crashes
passed in native-contracts of38698476013. Its builder repeated all custody tests
without WSP installed and failed before build;240881b limits that builder to
Core parser tests after the mandatory full native contract job. Retry38698811352.
On macOS,6 foreign/ELF contracts PASS and10 native-only cases skip;
these are not Linux acceptance. Spending explicitly refuses until an independent
trusted anchor is qualified; see LINUX_CUSTODY_POLICY.md. Do not wire a plain
file anchor into WalletSession to make tests pass.
Root witness implementation and opt-in real root-process CI tests now exist
but remain unqualified/unconnected. See LINUX_ROOT_WITNESS_POLICY.md; native
tests must pass before integrating exact LinuxRootWitnessAnchor into vault.
Then finish LINUX-03 trusted witness policy and regression gates;
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

No Linux real test PASS yet. Current host is macOS ARM64. CI Linux must provide
actual ELF/process/scanner/SQLite/Qt evidence. Mock/negative units are supplementary.
No mainnet, personal secrets, real funds, production qualification or automatic merge.
