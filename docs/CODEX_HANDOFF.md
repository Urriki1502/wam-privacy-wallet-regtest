# Autonomous REGTEST checkpoint — 14 October 2026

Repository: Urriki1502/wam-privacy-wallet-regtest. Main remains
`50e1ea94df61b8400cbab3bffe0fbdd285c6b419`; no Windows stack was merged.
Read WINDOWS_V1_1_CODEX_FINALIZATION_HANDOFF_20261014.md for ancestor context.
Refresh GitHub on resumption. No Final or production release declaration.

## Current engineering units

- PR23 `feature/windows-secure-custody-v1`, qualified head
  `65c56e0523f6a0d78d80e67401a0eb6d4b0f887d`: protected owner-only NTFS
  DACL/owner checks, no-reparse ancestor handles without write/delete sharing,
  hardlink denial, flushed ciphertext and native same-directory non-replacing
  rename, owned-handle failure cleanup, terminated writers, protected global
  mutex and abandonment denial. Native run38561250796 PASS; Mac source/frozen
  run38561250768 PASS; vectors38561250795 PASS. This backend is qualified on
  Windows Server2022, not a claim about power-loss durability or compromised OS.
- PR24 `feature/windows-anchored-vault-v1`, qualified head
  `b021eada48a31729fd3326adbd346581e463ef41`: shared CheckpointVault dispatch,
  unchanged Mac v1 envelopes; Windows v2 custody-platform-bound envelopes,
  Credential Manager CAS, backup/recovery, stale writer, uncertain irreversible
  reservations, orphan publication, failed-restore cleanup, lost/replaced
  credentials and actual reorg1/12/100. Native run38562289194 PASS.
  Windows signedCore38562288823, receive38562289166, Qt38562288973 and
  native vectors/scanner + signed ZIP38562288920 PASS. Mac source/frozen
  38562288887 and vectors38562290466 PASS. All9 checks on this head PASS.
- PR25 `feature/windows-operational-wallet-v1`, latest source head
  `6116fe5` (resolve full SHA via GitHub): private native Core/CLI/config/receipt
  transport; native SystemWindowsDirectory environment; strict shared local
  REGTEST config parser; existing WalletSession/Qt approval, native signing,
  anchored reservations, actual broadcast/change, lock/unlock and recovery.
  Earlier Windows run38564349192 reached genuine sign/broadcast/confirmed
  change105, lost actual broadcast reply, backup/lock/unlock/recovery. Full job
  FAILED at additional fresh-Core stale-payment test. Diagnosis on bc1245d:
  recovery itself succeeded; test tried Prepare AFTER Qt window close, which
  correctly locks its session. Commit6116fe5 moves that test before close.
  Latest exact-head native/source/frozen checks MUST be refreshed, not assumed.
  No incomplete operational check was merged or marked qualified.
- New frozen-build branch `feature/windows-frozen-operational-wallet-v1`
  is stacked on PR25. Prepared native windowed PyInstaller entry and build
  recipe reuse packaging tactics only from legacy PR170/206. Original supplied
  PNG becomes ICO; no substitute artwork. Bundle contains pinned WSP source,
  native crypto and exact Core bytes; runtime stages Core with protected ACLs.
  Workflow builds ONLY after native source gate, then runs actual frozen wallet
  E2E and publishes ZIP/manifests only after success. Native execution not yet
  verified at checkpoint authoring. Do not call this operational artifact PASS.

## Artifact provenance and qualification matrix

| Feature | macOS ARM64 | Windows x64 |
|---|---|---|
| Signed official Core / native WSP / BIP352 / SQLite | PASS source + frozen | PASS native milestone/source |
| Receive / Balance / History | PASS source + frozen | PASS real Core Qt |
| Encrypted custody / anchor / backup / reorg1/12/100 | PASS Keychain | PASS native Credential Manager PR24 |
| Prepare / Sign / Broadcast / confirmed change / uncertainty | PASS source + frozen | Observed genuine PASS stages; full PR25 acceptance pending |
| Fresh-Core recovery / stale before sign and broadcast | PASS existing Mac gate | Latest fixed PR25 rerun pending |
| Qualified operational distributable | .app/.dmg CI PASS | Frozen operational .exe/ZIP pending |
| Human Finder/Gatekeeper or Windows10/11 operator | PENDING | PENDING |
| Production / mainnet / real funds | NOT AUTHORIZED | NOT AUTHORIZED |

Qualified PR24 Mac artifact:
https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38562288887/artifacts/11893252364
Upload archive digest:
`7f88a167ed96e2a4cbcd84cb4e14c9bf3a33bd9173c240415ec0dd06afaeaec9`.
Its name uses tested merge checkout `70a5375a5d8217cf7ddf8b119b0147c54b4f82ab`,
while source head is b021eada48a31729fd3326adbd346581e463ef41.
This upload-archive digest is NOT the inner .dmg digest. Download and inspect
SHA256SUMS/package manifest before reporting inner artifact digests.
Local download was started into outputs/qualified-pr24-macos; completion and
local packaged execution were not yet verified. Do not imply hands-on testing.

Fresh independent GPG verification of official Windows v0.1.11 on this Mac:
- ZIP: `ece622fa7ec3072c4e8b0d32e2c3749397d66260f2b0cf22b3636346873d15c5`
- wamd.exe: `31717319535c5b784b2bed3b4d3c9a727f5c062e9534b4d27c59d2ffd04e95a1`
- wam-cli.exe: `538a6d1b918b698ce76a949dda982fdda6776e33ba057efaac59b1af59e59d21`
Both executable pins and signed ZIP are independently checked, not learned from
an untrusted runtime receipt. Mac pins remain unchanged. WSP stays ac55f13423620252bdbf848c7e8a280c3b84721e.

## Exact next actions

1. Refresh PR25/26 exact heads/checks and redacted WIN_REOPEN_STAGE /
   WIN_STALE_STAGE diagnostics. Fix any genuine failures, retaining source
   and frozen gates. Native qwindows source testing is distinct from operator QA.
2. Qualify the prepared frozen entry/build on Windows. Inspect actual exported
   ZIP, PE64 exe, every file digest, Core pins, source closure and receipt; then
   download the artifact and check its manifest. No GUI-only preview acceptance.
3. Rerun all native Windows WSP vectors, locks, scanner, real receive/Qt,
   custody/recovery and packaged operational flow on final exact head. Retain
   Mac native source, frozen Core/Qt/Cocoa and independent security gates.
4. Review18->19->20->21->22->23->24->25->26 bottom-up only once complete.
   PR17 is a separate historical Mac documentation PR; update stale release
   statements before merging it. Never clear the stack by merging unqualified
   drafts. Main currently keeps its original two workflows; feature stack has
   additional technically necessary native Windows gates, no Linux build.
5. Publish final two-platform matrix and exact inner artifacts/checksums;
   human operator signoff is still outstanding on both platforms.

## Remaining limitations

File data flush + atomic NTFS rename and orphan/CAS failure tests are not a
hardware-power-loss qualification. SQLite remains plaintext while unlocked;
Python immutable secret buffers have no guaranteed zeroization. Same-user
malware/admin control, Credential Manager profile rollback/replacement and
cross-PC recovery are not qualified. Signing interruptions retain irreversible
locks; some conservative reservations require recovery rather than automatic
reuse. The native keyring 16-epoch rotation limit remains. Windows package
Authenticode and production process/DLL binding are not qualified. Linux HOLD;
BIP352 x PayJoin execution V2. No upstream Core or WSP code was changed.

## Workspace preservation / reproduction

Working checkout: work/windows-v1-finalization under this project. Original
work/wam-privacy-wallet-regtest at3299940 was preserved, including its untracked
preview. The new checkout also has an acceptance-generated public security
preview; not a key/credential artifact. No personal keys or secrets committed.

Portable tests on Mac: `PYTHONPATH="$PWD/src" ../wam-privacy-wallet-regtest/.venv/bin/python -m unittest discover -s tests -v`
Latest90 contracts PASS,17 nativeWindows-only skips (NOT native Windows PASS).
Changed shared vault/session passed genuine local Mac source Core/Qt/Keychain
E2E with reorgs and fresh-Core recovery. Latest packaged acceptance is CI,
not human Finder. Source/frozen Windows acceptance uses the existing native
credential workflow; do not run Windows executables on the Mac or replace RPC.
