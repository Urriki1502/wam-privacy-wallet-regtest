# PR67 component qualification — REGTEST only

Tested code: `060183affb7a75c0af2f8b1d786b4d55c960e3e0`.
CI merge checkout: `2b66256120423d3ed9cf12fc948ad5771f82f2c6` (parents
`71a1e7b4336054bf0dabf3ca0ee6de174b462154` and the tested code SHA).
[Draft PR67](https://github.com/Urriki1502/wam-privacy-wallet-regtest/pull/67).
This report qualifies components, not full managed-wallet Q05 or Issue45 V1.
A later documentation commit must not be relabelled as these tested binaries.

## Platform matrix

| Evidence | macOS ARM64 | Windows x64 | Linux x86_64 |
|---|---|---|---|
| Core provenance | Official signed v0.1.11 | Official signed v0.1.11 | Reviewed pinned developer build; independent root witness |
| Genuine Core/WSP/SQLite native operational wallet | PASS: local and native runner | PASS: exact-head native runner receipt | PASS: native/headless runners |
| Final frozen operational wallet | PASS: local app/DMG, Cocoa and runner | PASS: final executable and125/150% DPI runners | PASS: desktop/headless runners |
| Actual downloaded frozen bytes/manifests | PASS: payload/RC hashes, original Core pair and ARM64 Mach-O | PASS:354 file hashes, PE AMD64, Core pair and source provenance | PASS:193/454 files;25 safe desktop links |
| Fresh-chain stale sign/broadcast denial | PASS: separate native Keychain vault directories, source/frozen/Cocoa | PASS: native/frozen Credential Manager case | PASS: headless root-witness case; distinct from GUI/cross-directory proof |
| Dedicated supervisor / native GUI close, kill and reconnect | PASS: actual Core and Qt processes | PASS: exact-head native T05 modal/Core receipt | PASS: native xcb/Core proof; source helper distinct from frozen managed entry |
| Full funded managed-wallet Q05 | PENDING | PENDING | PENDING |
| Physical owner/operator acceptance | PENDING_OPERATOR | PENDING_OPERATOR | PENDING_OPERATOR |

Mac local251 unit tests =217PASS/34platformSKIP, exit0. They supplement genuine
Core acceptance. No mock RPC/crypto result is counted as real-Core PASS. The
native signer and broadcast instrumentation delegates to actual implementations
or proves they were never entered. Only a proven never-signed fixture draft is
cancelable; signed/uncertain reservations remain irreversible.

## Changes and exact evidence

- `93083aaa5b15e5cf2de46599ccde1440eb0d54b5`: one monotonic deadline for control
  and scanner IPC. Real TCP trickle reproduced the old unbounded renewal;
  fixes and all10 exact-head CI jobs passed.
- `db71f42b7207608cfb5de9b8a72033906757d380`: exclude background/lifecycle
  workers and window destruction while native approval dialogs run their nested
  Qt event loop; recheck state after approval. Actual native dialog Cancel and
  Core/WSP/SQLite/GUI crash/reconnect passed. All10 exact-head CI passed; all
  three platforms' downloaded frozen packages were independently inspected.
- `060183a`: reuse Windows genuine-Core stale-payment acceptance on Mac with
  an explicit disposable Keychain matching the session anchor. No owner default
  Keychain fallback. Prove zero native signer calls on stale pre-sign rejection,
  a positive real signature after current recovery, then zero broadcast calls
  after a second vault advances the anchor. Final signed reservation remains
  irreversible. Mac source CI and final frozen entry now require these fields.

Current code CI: [Mac](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/39054287273),
[Windows](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/39054287394),
[Linux](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/39054287336),
[canonical vectors](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/39054287227).
All10 checks at the exact tested code SHA completed SUCCESS. The saved
[CI snapshot](evidence/issue45/PR67_060183A_ALL_CI.json) records each job URL,
conclusion and completion time. Later evidence/documentation commits have their
own CI and are not relabelled as this tested code or these packages.

## Reproduce the modal defect

On predecessor93083aa, authenticate a disposable managed Core and open Verify
locked wallet. Its native password dialog runs a nested event loop: the5s sync
timer could start a status QThread while the prompt was open. Accepting the
password could then overwrite its worker reference. The regression reproduced
worker creation during the modal loop; the overwrite/unsafe-lifetime consequence
also follows from the old unconditional assignment. It is distinct from the
historical hidden-widget native exit139 crash fixed at41c14bd.

The new actual-Core T05 test opens the real dialog, attempts background sync and
window close inside that loop, cancels, then checks no worker/session/wallet
adoption and the original live Core/tip. Separate negative fixtures cover stale
state and dialog errors; they are not mock-blockchain acceptance.

## Verified CI packages and SHA-256

| Artifact | Payload | SHA-256 |
|---|---|---|
| [Mac](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/39054287273/artifacts/12109301886) | .app.zip | `bbf69795fc1f74d305eaf9ce05fcbcda198c30ba4c2256e43568932c05e760f6` |
| Same Mac artifact | .dmg | `1dd5cfb321088861a288df3f43d74264146dc0e0291fa3272dd2737ab1e489af` |
| [Windows](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/39054287394/artifacts/12109626366) | operational x64 .zip | `42e6dc8c4675cec3555da6320aaa66478da86a6cbe4f5bd62d53adf144e64ce8` |
| [Linux desktop](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/39054287336/artifacts/12109470481) | .tar.gz | `662e9f0e6fcb8e414705dde37c01ad83cbc9f3462adf2ac7e6d8cf7a69d8ece2` |
| [Linux headless](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/39054287336/artifacts/12109326606) | .tar.gz | `b87b40dc991b4f9c138cce7dcae2f25206f3a3f89654a6b0c56a2989eaaf57f2` |

Actual outer artifact digests, all payload/RC manifests, platform machine code,
Core pair and source provenance were independently inspected after completed
downloads. Full receipts are in `docs/evidence/issue45/PR67_060183A_*`.
Mac CI and local builds have identical clean native source inventories but
separate OS/toolchain/dependency receipts and package hashes; byte-for-byte
reproducibility across differing toolchains is not asserted. Artifacts have the
existing14-day retention; local full archives and redacted screenshots remain
under `outputs/pr67-resume-20261017T144215` in the owner workspace.

Original Core pairs (node then CLI):

- Mac: `7298de701e467eb28b4806cbcbe35edb393861b4b97117017fee4c1b194e3068`; `81a031ebf9b3060b19061b29756d43bcd09b32ad778348b8c3d8321397076e82`.
- Windows: `31717319535c5b784b2bed3b4d3c9a727f5c062e9534b4d27c59d2ffd04e95a1`; `538a6d1b918b698ce76a949dda982fdda6776e33ba057efaac59b1af59e59d21`.
- Linux developer build: `ccc9f0f1d299a1e98a49ff83859aa03e994e83e6ea4b7cd60c327eb1e0e8e4d6`; `ada9dabd56d0859b9d64c0b20a05c33cb039b2573f75088443b45c35d5379652`.

## Reproduction

Use a clean native checkout at the tested SHA and the repository engineering
lease. Provision the independently verified v0.1.11 Core pair and pinned native
WSP source `ac55f13423620252bdbf848c7e8a280c3b84721e` using the existing platform
workflow. All wallet/Keychain/Credential/root-witness fixtures are disposable;
never use an owner wallet or existing default Keychain as a test fixture.

On Mac: `python scripts/run_native_unittest.py --pattern 'test*.py'`, then
`python scripts/issue45_t05_real_core.py --core-dir core --qt-e2e --output <new-public-receipt>`.
Run the existing full `wam_regtest.cli smoke` workflow flags and
`scripts/build_macos_bundle.sh` with empty package-output. Execute the final
binary with `QT_QPA_PLATFORM=cocoa` and `--ci-real-core-wallet-cocoa` separately.
The build records clean source before/after, original Core hashes, final
executable E2E, DMG verification and create-only manifests. Local sibling venv
requires explicit `PYTHONPATH=src` plus the recorded reference-deps path; do not
modify its old editable checkout or upstream WSP. Windows/Linux use their
existing native/frozen workflows, not a foreign executable on Mac.

## Remaining findings and disposition

Independent Drafts68/94a7649,69/d3aa1f3,70/a4a8257,71/75433cb were inspected read
only and left untouched. Their extra wallet-view password dialog in69 still
needs equivalent modal exclusion when independently integrated. PR70 funded
read-only GUI crash/reopen and PR71 crash-DURING-write proof are Mac-specific;
other platforms' operational regression green is not that direct funded proof.
Requalify their actual integration checkout after any base/runtime change.

Current packages still exercise the operational disposable wallet; their green
results do not establish a final frozen persistent original-wallet GUI entry
with Prepare/Review/Sign/Broadcast continuity. No read-only status/snapshot can
grant signing authority. Preserve unknown runtime/orphan refusal and native
anchors, original test keys and irreversible reservations. Never repair/delete
anchors, abandon signed/uncertain locks or replay uncertain broadcast to pass.

A direct Cua attempt to inspect/launch the qualified app was blocked by the
Mac lock screen (no successful app UI state observed). Normal launch/initial
Cancel remains PENDING_OPERATOR until the owner manually unlocks the Mac.
Programmatic Cocoa results remain separate. No lock-screen bypass was attempted.

Physical Finder/LaunchServices startup, focus/keyboard/retina/font/camera QR,
actual macOS preferences changing Auto appearance, sleep/wake and human usability
remain PENDING_OPERATOR. Automated Cocoa probes change only local Qt color-scheme
hints and verify native widget signals; they do not change system preferences.
No local Windows/Linux execution, physical operator approval or DEV review is
claimed. Memory erasure, unlocked SQLite, OS/profile rollback, power-loss/disk
failure, loader/dependency supply chain and release signing/notarization retain
the explicit limitations in platform receipts and existing security review.

**Disposition: REGTEST engineering preview only; full Q05/Issue45 V1 not qualified.**
Main/immutable RC1/upstream/owner data were preserved. v0.1.12 remains candidate
only; Core Update Manager is deferred P1. No merge, force-push or new PR.
