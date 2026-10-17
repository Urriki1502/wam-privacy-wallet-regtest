Latest: [c21bbd1 actual frozen-owned Core crash/restart qualification](PR67_FROZEN_CORE_CRASH_ACCEPTANCE.md). The e960dff report below is historical.

# PR67 final executable component qualification

Tested code: `e960dff5c1abcd16f6a3ad2272e589d1a4b86e90`.
CI merge checkout: `36d56d9f424dcc9476fcff715d337b3d34d34d8b`; Git independently
verified parents66/`71a1e7b4336054bf0dabf3ca0ee6de174b462154` and tested67.
This qualifies disposable REGTEST components. Full managed-wallet Q05 and
Issue45 V1 remain PENDING. PR67 stays Draft; no automatic merge or new PR.

## Scope and separation of evidence

Previous T05 acceptance launched host Python children even from Linux frozen
acceptance. New fixed CI roles execute the final platform executable as the
separate supervisor, two real pinned WSP scan clients and three genuine Qt GUI
processes. SQLite resumes 0→3→8; Core stays at 101 and the original tip across
clean GUI close, authenticated-ready GUI kill and reopen. The supervisor then
stops only its verified owned Core and exits 0. The test operator remains a
native-source harness. Initial daemon crash/restart, native modal Cancel and
ancillary CLI/disconnect tests in that harness are source/native evidence,
not additional frozen-role claims.

Five final executable refusals must exit 2 promptly and leave the fresh root
empty: absent consent, external Core override, external WSP override, incompatible
supervisor crash flag and report/control-root alias. Windows uses independent
native-private bounded create-only reports instead of stdout. Rebinding Linux
policy is refused; the existing scan entry performs its own one-shot binding.
Qt platform is captured before teardown and compared to actual child reports.
No arbitrary module execution, external resource override, source fallback,
wallet key, anchor or signing authority is added.

## Platform matrix

| Component | macOS ARM64 | Windows x64 | Linux x86_64 |
|---|---|---|---|
| Core provenance | Official signed v0.1.11 | Official signed v0.1.11 | Pinned reviewed developer source build, independent root witness |
| Genuine Core/WSP/SQLite/Qt operational disposable wallet | PASS local/native runner | PASS native runner receipt | PASS native headless/xcb runners |
| Final frozen operational wallet | PASS local app/DMG, Cocoa, runner | PASS native qwindows runner, 125/150% DPI | PASS headless/desktop runners |
| Frozen supervisor / two WSP clients / three Qt clients | PASS offscreen and Cocoa | PASS qwindows runner | PASS xcb desktop; headless has no Qt |
| Five frozen scope refusals | PASS | PASS | PASS desktop |
| Actual downloaded payload/Core/source manifests | PASS | PASS: 354 files, AMD64 PE, Core pair | PASS: 193/454 files, 25 safe desktop links |
| Full funded managed original-wallet Q05 | PENDING | PENDING | PENDING |
| Physical/operator acceptance | PENDING_OPERATOR | PENDING_OPERATOR | PENDING_OPERATOR |

Local native Mac 257 tests=223 PASS/34 platform SKIP, exit 0. SKIP is not platform
PASS. No mock RPC result substitutes for real-Core acceptance. Genuine Mac
frozen full security/recovery/stale-sign/broadcast/reorg1/12/100 passes on both
offscreen and actual Cocoa. Qt color-scheme override signals are tested; no
physical OS preference change is claimed. The exact Mac executable also denies
independently modified node/CLI/WSP resources in disposable copied bundles with
fixed exit 2 codes; original bundle hashes remain unchanged. These negative
preflight tests are not blockchain E2E substitutes.


## Exact CI and downloadable bytes

All 10 exact-head checks completed SUCCESS. [Saved job snapshot](evidence/issue45/PR67_E960DFF_ALL_CI.json).
[Mac](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/39074395017) · [Windows](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/39074394989) · [Linux](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/39074395022) · [28 canonical BIP352 vectors](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/39074395009)

| Artifact | Payload | SHA-256 |
|---|---|---|
| [Mac](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/39074395017/artifacts/12116611460) | .app.zip | `13e13eb8462185ba09ab996efd2d5453b7b9323b403a11b8ece84567d581e94a` |
| Same Mac artifact | .dmg | `3a2cc77d6f761f2ba8872e61770bb48c2cc1b0eb1d9cf00b7d87e44eea51c183` |
| [Windows](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/39074394989/artifacts/12116229163) | operational x64 .zip | `c6d3cdffc56e68c1c54716c622001c0a7e2b7f84f815720cde4409aee7758ac1` |
| [Linux desktop](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/39074395022/artifacts/12116274143) | .tar.gz | `3e060c9a2903573673d4745e96bbb8a703d5a5182ce68c96e4a1fb546a349f7d` |
| [Linux headless](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/39074395022/artifacts/12116802865) | .tar.gz | `570819ca5ab16179d160bf9d1372a86c8f87834e2d17593d2501bb23304f2328` |

Actual downloads were compared to GitHub API outer SHA-256, RC/payload/file
manifests and original independently pinned Core pairs. Mac ARM64 Mach-O,
Windows AMD64 PE and Linux ELF64/Core bytes were checked. New frozen-role
receipts were matched to the actual packaged executable hash, native source
inventory and Qt backend. Public receipts: `docs/evidence/issue45/PR67_E960DFF_*.json`.
[Original Core pairs](PR67_PLATFORM_QUALIFICATION.md) remain unchanged. Pinned WSP
is `ac55f13423620252bdbf848c7e8a280c3b84721e`; Linux approved manifest remains
`e77a5745263b8fdbcffdb282af22800b6f7805f033c09f00738e997150a0f806`.
No bit-for-bit reproducibility across differing toolchains is asserted; exact
build/dependency/source receipts accompany artifacts, retained for 14 days.
Local archives, redacted Qt screenshots, inspector scripts and separate log:
`outputs/pr67-resume-20261017T220014`. Later documentation-head CI and binaries
must keep their own SHA; do not relabel these tested e960dff bytes.

## Reproduce

Use a clean native checkout at the tested code, hold the engineering lease,
and use each existing platform workflow for exact Core/WSP/dependency setup.
Mac `scripts/build_macos_bundle.sh` and Windows `scripts/build_windows_bundle.py`
now require frozen managed-process acceptance before publication. Windows uses
its existing native private Core staging. Linux `scripts/build_linux_wallet.py`
uses the existing separate no-Qt/headless and xcb jobs; only the explicit CI
operator provisions a disposable root witness, never the application.

On Mac the additional native Cocoa process proof is reproducible with
`QT_QPA_PLATFORM=cocoa python scripts/frozen_managed_acceptance.py --core-dir <verified-core> --executable <final-absolute-binary> --output <fresh-public-json>`.
The host harness must load this exact source and pinned WSP; it never replaces
frozen children with host Python. The final Mac executable's separate
`--ci-real-core-wallet-cocoa` mode repeats genuine wallet/security/recovery gates.
Use only disposable REGTEST fixtures and explicitly disposable test Keychains.

## Remaining gates and release disposition

Independent68/94a7649,69/d3aa1f3,70/a4a8257,71/75433cb remain untouched. Their
original-wallet view/funded crash/crash-during-write work is not integrated.
PR69 additional password prompt needs equivalent modal exclusion at eventual
integration. Old-head green must not qualify changed ancestry/runtime. No
read-only Core status or snapshot can authorize signing or release reservations.

The actual normal macOS app-path/LaunchServices UI attempt was blocked by the
locked Mac; readonly process inspection found 0 matching app processes. No
lock-screen bypass, owner wallet or default-Keychain action. Finder startup,
focus/keyboard, retina/fonts, camera QR, physical OS Auto appearance, sleep/wake
and human usability remain PENDING_OPERATOR. Windows/Linux binaries were
inspected on Mac, not locally executed there; native runner evidence is separate.

Plaintext SQLite while unlocked, sensitive Python/native memory lifecycle,
power-loss/disk failures, same-UID/privileged host compromise, dependency/loader
supply chain, cross-Mac recovery, release signing/notarization and full original
wallet integration retain existing limitations. REGTEST preview only; no Final,
production, mainnet or real-funds qualification. v0.1.12 remains candidate-only;
Core Update Manager remains deferred P1. Main, RC1 and upstream Core preserved.
