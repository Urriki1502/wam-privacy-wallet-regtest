# PR67 frozen-owned Core crash/restart qualification

Tested runtime: `c21bbd1b06f5db9bd40375e8dc43ba19ed7ca150`.
CI merge checkout: `518a7b48e74f7161edce0ab59b1299b3415fa40c`, independently
verified Git parents66/71a1e7b and67/c21bbd1. The earlier
[e960dff component report](PR67_FROZEN_MANAGED_ACCEPTANCE.md) remains historical.
Full funded managed-wallet Q05 and Issue45 V1 remain PENDING; no merge/new PR.

## Added acceptance boundary

The FINAL packaged supervisor now injects a real fault into its own Core Popen.
The application runtime supervisor_cli and Core implementation are unchanged.
The CI-only path requires BOTH disposable-REGTEST consent and separate explicit
owned-Core-crash consent. Ordinary Python cannot invoke the helper or label a
receipt frozen; GUI/scan roles reject fault consent. Six actual bootloader
refusals must leave the fresh supervisor root empty and exit 2 without a modal.

Before kill: require READY, real RPC reads and immediate native image/metadata
verification of the actual owned Popen. Require exact fault exit(-9POSIX,
1Windows), recovery-needed, retained protected datadir, new owned Core process
and same height 101/tip. Publish only a bounded/create-only native-private report.
The source operator independently checks actual Core status/tip before two
pinned WSP processes resume SQLite0→3→8 and three genuine Qt processes prove
clean-close/kill-after-authenticated-ready/reopen. Finally verify Core shutdown
and supervisor exit 0. No external PID adoption, key/anchor operation, reservation
release, wallet authority or uncertain signing/broadcast retry is introduced.

This is a quiescent isolated REGTEST chain. It does not prove crash-during-Core
block writing, power-loss durability, funded original-wallet continuity or
resistance to a compromised same-UID/privileged host. The harness's initial
source/native daemon crash and modal/ancillary cases remain separately scoped;
only the newly labelled final-executable owner/scan/GUI cases are FROZEN.

## Platform matrix

| Component | macOS ARM64 | Windows x64 | Linux x86_64 |
|---|---|---|---|
| Core provenance | Official signed v0.1.11 | Official signed v0.1.11 | Reviewed pinned developer build + independent root witness |
| Native genuine operational wallet | PASS local/runner | PASS inspected native receipt | PASS headless/xcb runners |
| Final executable operational security/recovery | PASS local app/DMG, Cocoa, runner | PASS inspected final executable,125/150% DPI | PASS headless/desktop runners |
| Actual FROZEN-owned Core kill/restart/same tip | PASS offscreen+Cocoa, local/runner | PASS inspected qwindows receipt,exit 1 | PASS inspected desktop xcb receipt; headless N/A |
| Six frozen consent/resource/scope refusals | PASS | PASS | PASS desktop |
| Downloaded final payload/Core/source manifests | PASS | PASS: 354 files,AMD64 PE,Core pair | PASS:193/454 files,25 safe desktop links |
| Full funded managed original-wallet Q05 | PENDING | PENDING | PENDING |
| Physical/operator acceptance | PENDING_OPERATOR | PENDING_OPERATOR | PENDING_OPERATOR |

Local native 259 tests=225 PASS/34 platform SKIP, exit 0. Genuine final Mac operational
wallet, native Cocoa, fresh-chain/stale-writer recovery and reorg1/12/100 exit 0.
Copied-app node/CLI/WSP mutation preflight denials repeat on this exact executable;
only disposable copies changed and modified Core was never launched. Such
negatives do not substitute for real-blockchain E2E. Qt color-scheme override
signals are distinct from physically changing OS appearance settings.

## Exact CI, packages and evidence

All 10 exact-head checks SUCCESS. [Saved snapshot](evidence/issue45/PR67_C21BBD1_ALL_CI.json).
[Mac](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/39077453134) · [Windows](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/39077452994) · [Linux](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/39077452955) · [28 canonical vectors](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/39077452947)

| Artifact | Payload | SHA-256 |
|---|---|---|
| [Mac](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/39077453134/artifacts/12117347546) | .app.zip | `76a8ea1b81d8bbda5f5f6be24fa167ba5bce005c0782a59abbb973bac0df5f61` |
| [Mac](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/39077453134/artifacts/12117347546) | .dmg | `073361dd1531ce3cc11e0392945debb2f50ba5b16fca38bae037cdfa46e14a6f` |
| [Windows](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/39077452994/artifacts/12118470526) | operational x64 .zip | `bb4c5b977954d9ef56a8703616f9ce4ebdcd81bee79a2ce36b9195ecb472f82c` |
| [Linux desktop](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/39077452955/artifacts/12117747394) | .tar.gz | `2220ea35272c36ca03c887acf9865b447a6bac47dd6f7592248ea95b6577e986` |
| [Linux headless](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/39077452955/artifacts/12117546942) | .tar.gz | `5e281b5293f941b5262d176c6a7d04c40d6f9884650fbf6b2a8f396c660daecc` |

Actual downloads match GitHub API outer digest and all RC/payload/file manifests.
Native source inventory, exact tested executable hash, Qt backend and Core-fault
receipt agree. Independent original Core pairs remain unchanged; Mac ARM64 Mach-O,
Windows AMD64 PE, Linux ELF/Core verified. Windows354files; Linux193/454files,
25safe desktop links. The headless package retains no Qt and is N/A for GUI roles.
Public receipts: `docs/evidence/issue45/PR67_C21BBD1_*.json`; full local logs,
redacted screenshots, inspector scripts and packages:
`outputs/pr67-resume-20261017T220014`. Artifact retention14 days; no bit-for-bit
reproducibility across different toolchains asserted. Build/source/dependency
receipts accompany the exact packages. Later docs heads keep their own CI and
binaries; never relabel these c21bbd1 artifacts.

Use a clean native checkout at this tested SHA, hold the engineering lease and
follow each existing platform workflow for exact Core/WSP/dependency setup.
Mac/Windows builders require the final-executable Core-fault proof before
publication; Windows retains private Core staging. Linux keeps separate no-Qt
headless and xcb jobs and independent approved developer manifest/root witness;
only the explicit CI operator provisions a disposable witness, never the app.
Mac repeats the managed-process operator with QT_QPA_PLATFORM=cocoa and the
final executable's --ci-real-core-wallet-cocoa mode in separate output directories.
All keys/wallets/Keychains/credentials are disposable test fixtures, never owner
wallets, default Keychain or miners. Pinned WSP ac55f13423620252bdbf848c7e8a280c3b84721e;
[original Core pair hashes](PR67_PLATFORM_QUALIFICATION.md) remain unchanged.

## Remaining scope and release disposition

Independent68–71 remain unchanged. Their original-wallet live view, funded
reopen and crash-during-write work is not integrated.69 additional password
prompt needs modal exclusion at eventual qualified integration. Old-base green
cannot qualify changed ancestry. Read-only status/snapshot grants no signer.
Preserve original test keys, native custody/anchors/leases, rollback and all
signed/uncertain reservations; never repair/delete/release them for a PASS.

Current normal app-path/LaunchServices UI remains blocked by Mac lock screen;
0 matching app processes observed after the attempt. No bypass/default owner
Keychain action. Physical Finder/focus/keyboard/retina/fonts/camera/OS-Auto/sleep
and human usability remain PENDING_OPERATOR, as do physical Windows/Linux.
Native runner receipts and artifact inspection on Mac are not local Win/Linux
execution. Unlocked SQLite/memory lifetime, power-loss/disk failure, same-UID
host/loader/dependency trust, cross-Mac recovery, release signing/notarization
and full original-wallet integration retain explicit limitations.

REGTEST engineering preview only, not Final/production/mainnet/real-funds.
v0.1.12 remains candidate-only; Core Update Manager P1 deferred. Main, RC1,
upstream Core, owner wallets/anchors/miners and active branches preserved.
