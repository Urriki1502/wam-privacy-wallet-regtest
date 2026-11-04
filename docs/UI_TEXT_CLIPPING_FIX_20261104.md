# Targeted macOS UI text clipping fix — 4 November 2026

Scope: owner-requested Backup verified description, Settings Advanced controls and shared footer/status only. Local branch `feature/v1-net-shared-regtest-20261104`. Baseline `a921ebb2a6ffad2683c8317258ccaece2bf833db`; UI fix `c7789d413f24d13a835a3ad3b351a0b17fed393c`; final packaged source `6642506ed20a22724b49163e2ffcf0ddad786e33` (review fixture correction). No source changes to custody, signing, Core, networking, checkpoints, reservations or transactions. No acceptance transition, remote action, real wallet access or new Core process.

## Findings and changes — VERIFIED

| Area | Before / cause | Change and measured result at 900×630 Light |
|---|---|---|
| Backup verified | Center-aligned layout item narrowed wrapped description to 194 px, allocated 16 px while text needed 48 px. Hidden stack pages imposed excessive minimum width; native autofill also produced dark background in Light. | Full-width centered text, height-for-width policy; success-only stack sizing restores original policy for verification pages; transparent themed scroll surface. Actual packaged description 587×16 px / required16; 5× longer stress message 587×80 / required80; no horizontal overflow. |
| Advanced controls | Native toolbutton minimum hint omitted stylesheet padding. Collapsed button 28 px vs styled sizeHint40. | Local toggle derives minimum size from current styled sizeHint on text/show/font/style changes. Both open/closed and repeated cycles40 / required40; no fixed maximum height. Existing card padding and actions preserved. |
| Footer/status | Prose wrapped, but an unbroken128-character identifier overflowed horizontally. Initial height-only assertion missed it. | Plain-text footer reserves required vertical space; optional zero-width breaks every24 characters in long tokens. Exact original text remains in tooltip. Geometry checks include rendered width, height, containment and non-overlap. Prose48 / required48; identifier32 / required32; six lines96 / required96. |

Advanced account/balance/tip labels also use wrapping/height-for-width instead of forcing the card width. Existing Light/Automatic/Dark selector and all backup verification behavior remain unchanged. The TXID line edit retains its normal editable/selectable horizontally scrolling presentation; it is not covered over by another widget.

## Changed files

- `src/wam_regtest/bip39_backup_page.py`: success label/scroll sizing and theme background.
- `src/wam_regtest/bip39_fusion_gui.py`: adaptive Advanced toggle and wrapping status presentation.
- `src/wam_regtest/ui_layout_probe.py`: real existing widgets, disabled executor presentation fixture, screenshots/geometry assertions; no backend/Core creation.
- `tests/test_ui_text_layout.py`: layout and truthful UI-only qualification metadata regression.
- `src/wam_regtest/package_entry.py`: hidden `--ci-ui-layout` invokes the fixture after the existing bundle integrity check; no normal launch change.
- `scripts/build_macos_bundle.sh`: narrow `--ui-layout-focused` path reuses packaging/signing/hash checks without rerunning wallet/Core scenarios.
- `src/wam_regtest/release_candidate.py`: UI-only qualification explicitly does not claim full native wallet/Core E2E.
- This report. Mutable ignored root `ENGINEERING_HANDOFF.md` is updated separately.

## Actual checks and evidence

All paths below are local evidence retained in this canonical workspace. UI fixtures prove actual rendering, not real wallet/network acceptance.

| Check | Result | Evidence |
|---|---|---|
| New focused native Cocoa tests | PASS2 / FAIL0 | [final focused rerun](../build/local-evidence-20261104/ui-layout-expanded-final.log) |
| Existing GUI Q06 tests | PASS5 / FAIL0 | [GUI log](../build/local-evidence-20261104/ui-layout-final-existing-gui.log) |
| Existing backup/verify/lock UI contracts | PASS32 / FAIL0 | [backup log](../build/local-evidence-20261104/ui-layout-final-backup.log) |
| Final frozen `.app`, native Cocoa Retina2× | PASS44 geometry records / FAIL0 | [receipt](../package-output/ui-layout-native/evidence.json) |
| Same frozen `.app`, controlled scale1× | PASS44 geometry records / FAIL0 | [receipt](../package-output/ui-layout-scale-1x/evidence.json) |
| Source/WSP binding, bundle crypto/self-check, unchanged original Core bytes, DMG verification | PASS | [build log](../build/local-evidence-20261104/ui-layout-frozen-final.log) |
| 73 manifest member hashes, ZIP executable, read-only DMG executable/Core match; own volume detached | PASS | [verification](../build/local-evidence-20261104/ui-delivery-verification.json) |
| Owner's exact physical window/display configuration | BLOCKED on owner dimensions/review; not provided | Tested minimum900×630 and default1260×810; physical available screen1512×874 logical/nativeDPR2. Controlled1× is not a second physical display. |
| New candidate real-Core/transaction/P2P acceptance | NOT EXECUTED in this UI-only task | Prior qualified bytes/evidence preserved; no automatic transfer of full qualification to changed frozen bytes. |

Focused commands before rebuilding (native Cocoa on macOS):

```sh
build/local-toolchain/bin/python -I scripts/run_macos_source_tests.py --pattern test_ui_text_layout.py
build/local-toolchain/bin/python -I scripts/run_macos_source_tests.py --pattern 'test_q06_bip39*gui*.py'
build/local-toolchain/bin/python -I scripts/run_macos_source_tests.py --pattern test_q06_bip39_backup_ack.py
PATH="$PWD/build/local-toolchain/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin" bash scripts/build_macos_bundle.sh --ui-layout-focused
build/local-toolchain/bin/python -I build/local-evidence-20261104/verify_ui_delivery.py
```

Both frozen executions use a retained fresh working directory under `bundle-input/ui-layout-*`, remove developer Python/Qt environment paths and run the final bundled executable. They cover both window sizes, Light/Dark, successful backup and longer-text stress case, return to verification sizing policy, expanded/collapsed/repeated toggle, diagnostic labels and three footer message shapes. No recovery phrase, password, key, cookie or live wallet is needed.

The first diagnostic fixture had `closed=True` without a join method, causing timer AttributeErrors; this is retained in intermediate logs and is not a product unlock failure. Final fixture stops polling before showing. The first fix still clipped the collapsed toggle; retained `ui-clipping-after-source2/` demonstrates that failure. A later screenshot inspection caught unbroken-token overflow missed by height-only assertions; final checks now also assert text width. First frozen candidate `c7789d4` passed rendering checks but its fixture retained a wrong page heading on a repeated navigation row; `6642506` corrects the fixture and adds expanded bottom review. None of these intermediate results is substituted for final-byte proof.

## Before/after visual evidence

Before images are actual native Qt source rendering at baseline, not a replay of the old frozen app. After images below come from the actual final frozen `.app` at source6642506. All images show presentation fixtures without wallet state. UI text stress images are labeled separately from the normal message.

| Surface | Before native source | After final packaged Cocoa |
|---|---|---|
| Backup / Light900 | [before](../build/local-evidence-20261104/ui-clipping-before/backup-900-1.png) | [after](../package-output/ui-layout-native/backup-900-1.png) |
| Backup / Dark900 | [before](../build/local-evidence-20261104/ui-clipping-before/backup-900-2.png) | [after](../package-output/ui-layout-native/backup-900-2.png) |
| Advanced collapsed / Light900 | [before](../build/local-evidence-20261104/ui-clipping-before/advanced-900-1-False.png) | [after](../package-output/ui-layout-native/advanced-900-1-False.png) |
| Advanced expanded / Dark900 | [before](../build/local-evidence-20261104/ui-clipping-before/advanced-900-2-True.png) | [top](../package-output/ui-layout-native/advanced-900-2-True.png), [bottom](../package-output/ui-layout-native/advanced-bottom-900-2.png) |
| Long footer prose / Light900 | [before](../build/local-evidence-20261104/ui-clipping-before/footer-900-1.png) | [after](../package-output/ui-layout-native/footer-900-1-0.png) |

Additional final packaged stress evidence: [long identifier](../package-output/ui-layout-native/footer-900-1-1.png), [six-line footer](../package-output/ui-layout-native/footer-900-2-2.png), [wrapped backup](../package-output/ui-layout-native/backup-wrapped-900-2.png), [default-size Light backup](../package-output/ui-layout-native/backup-1260-1.png), [1× expanded card](../package-output/ui-layout-scale-1x/advanced-900-2-True.png).

## Final artifact and retained work

Unnotarized local macOS ARM64 UI candidate, build source **6642506ed20a22724b49163e2ffcf0ddad786e33**:

- [DMG](../package-output/WAM-Privacy-Wallet-REGTEST-macOS-ARM64.dmg): SHA256 `538acd184e85a79964fc976efbecbcd8a572e1cf5fd78fcaab288f2ba01a87bc`.
- ZIP SHA256 `e54e7ea4399b11dac9f011f4ce8646ea5d97b1ba337cc56e693d3c57b5fe12e9`.
- Executable SHA256 `7ad6bbe027d1a594378ecb9d1bad5c79637347e68efe278cc4c0c5df5eb4c28f`.
- Core wamd `7298de701e467eb28b4806cbcbe35edb393861b4b97117017fee4c1b194e3068`; cli `81a031ebf9b3060b19061b29756d43bcd09b32ad778348b8c3d8321397076e82`; original signed0.1.11/WSP ac55f134 unchanged.

Previous public V1 package/dist retained under `build/retained-artifacts/pre-ui-c7789d4/`; first UI candidate under `build/retained-artifacts/ui-c7789d4/`. Qualified V1 snapshot `build/qualified-v1-29448e5/` and isolated Q06 snapshot `build/qualified-q06-e48d6cc/` unchanged. No wallet/runtime cleanup, adoption, reset, broadcast or reservation manipulation. Foreign orphan Core7234/7250 remain read-only; no new Core leaked.

Q06 accepted=false. G6 owner physical retest pending; G7 independent sign-off BLOCKED; V19 actual two-computer physical test remains BLOCKED. Ledger blob unchanged `0e93a2b213d7dab6d0f5bc9c26997c68493aed8a`. No G0–G7 transition/full acceptance/engineering-focus handoff is asserted. Remaining action is owner visual review at the exact affected window/display configuration and the previously recorded independent/physical backlog. No reproducible FAIL remains in this targeted UI matrix.
