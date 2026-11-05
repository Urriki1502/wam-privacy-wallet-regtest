# Joint Owner / Developer acceptance checklist

Pinned source: `3ab3e527cb90930631c4265f12923981452bf21e`  
WSP: `ac55f13423620252bdbf848c7e8a280c3b84721e`  
Q06 `accepted=false`. G6/G7 **unchanged** until named humans complete them.  
Agents (Cursor/Codex) **must not** fill Owner, Developer, or Independent verdicts.

Status vocabulary: `PASS` (named evidence), `FAIL` (retained), `PENDING`, `BLOCKED`, `NOT EXECUTED`. Skipped ≠ PASS.

Official Core v0.1.11: GPG `VALIDSIG` over `SHA256SUMS` from `https://wamcoin.org` (fingerprint `4BD4A8D3AFD43F5CBCB500E23798462FE00ADBA4`). GitHub Releases 404. Details: `docs/UPSTREAM_CORE_V0.1.11_VERIFICATION.md`.

## OWNER (human only)

| Platform | Build SHA256 | Physical evidence | PASS/FAIL/BLOCKED | Acceptance | Date |
| --- | --- | --- | --- | --- | --- |
| macOS ARM64 | | | | | |
| Windows x64 | | | | | |
| Linux x86_64 | | | | | |

## DEVELOPER (human only; independent rebuild)

| Platform | Rebuilt artifact SHA256 | Build environment | Security observations | Tests | Acceptance | Date |
| --- | --- | --- | --- | --- | --- | --- |
| macOS ARM64 | | | | | | |
| Windows x64 | | | | | | |
| Linux x86_64 | | | | | | |

Developer review is **not** automatically G7.

## INDEPENDENT REVIEWER (human only)

| Scope | Findings | Evidence reviewed | Decision | Date |
| --- | --- | --- | --- | --- |
| | | | | |

## Platform build / install

| Item | macOS ARM64 | Windows x64 | Linux x86_64 desktop | Linux x86_64 headless |
| --- | --- | --- | --- | --- |
| Same source SHA packaged | FAIL (full builder stopped; no DMG) | BLOCKED | BLOCKED | BLOCKED |
| Artifact SHA256 recorded | — | — | — | — |
| Core bytes match pin | local `core/` matches receipt; frozen restore unproven for this SHA | official PE pin | developer ELF pin | developer ELF pin |
| Presented as signed official wallet | NO (ad-hoc at most) | NO (unsigned) | NO | NO |
| Install / first start (disposable profile) | PENDING owner/dev | BLOCKED | BLOCKED | BLOCKED |
| Clean process shutdown | PENDING | BLOCKED | BLOCKED | BLOCKED |

## Functional matrix (each OS that actually runs)

Record job/receipt, OS, package SHA, Core digest, timestamp. Disposable REGTEST only.

| Case | macOS | Windows | Linux desktop |
| --- | --- | --- | --- |
| Core verification (identity ≠ live process) | PASS (frozen cocoa/offscreen Core gates) | BLOCKED | BLOCKED |
| Create 12-word wallet | PASS (`--ci-q06-bip39-readonly`) | BLOCKED | BLOCKED |
| Backup + recovery verification (no seed in screenshots) | PASS (cocoa wallet + Q06 readonly restore) | BLOCKED | BLOCKED |
| Lock / Unlock | PASS (cocoa packaged wallet) | BLOCKED | BLOCKED |
| BIP352 Receive | PASS (readonly funded scan + Qt bind) | BLOCKED | BLOCKED |
| Prepare / Sign / Broadcast | FAIL (Q06 spend stopped after `SIGNED_ANCHORED_PASS`; cocoa Q05-path send still PASS) | BLOCKED | BLOCKED |
| Mempool acceptance | NOT COMPLETE for Q06 spend | BLOCKED | BLOCKED |
| On-chain confirmation | NOT COMPLETE for Q06 spend | BLOCKED | BLOCKED |
| Balance + History (verified snapshot only) | PASS on readonly/cocoa paths | BLOCKED | BLOCKED |
| Reservation protection / no auto-retry | PASS on cocoa wallet reorg/lost-broadcast path | BLOCKED | BLOCKED |
| Theme Automatic / Light / Dark | PASS (`MACOS_COCOA_PACKAGED_AUTO_LIGHT_DARK_REAL_CORE_WALLET_PASS`) | BLOCKED | BLOCKED |
| Page motion + Reduced Motion | PASS frozen `--ci-ui-layout` (no Core) | BLOCKED | BLOCKED |
| Shared REGTEST P2P (29555, RPC 127.0.0.1:29554) | NOT REACHED this build / V19 still physical | BLOCKED | BLOCKED |

Source-only Mac presentation tests (not Core E2E, not Q06 ledger): 34 unittest OK on 2026-11-05 (`tests.test_fusion_v21_layout`, `test_fusion_design`, `test_q06_bip39_fusion_gui`, `test_ui_text_layout`).

RC1 native CI PASS at `144d877` (runs 38747153198 / 38747163508 / 38747174307) is **historical**. Those Actions artifacts are expired (`total_count=0` on 2026-11-05). See `docs/PLATFORM_REUSE_GAP_MATRIX.md`. Not V2.2 qualification.

## V19 two physical computers

Procedure: `docs/V19_PHYSICAL_ACCEPTANCE_READY.md` and `docs/V1_NET_TWO_COMPUTER_ACCEPTANCE.md`.  
Node A / Node B: same candidate, new Shared profiles, one miner, genesis `b88f3d262f285e38e184f50bf3eea1c8e615486ae67d3d9eaf0976fbd6d3d30d`, magic `WAMR`.

| Evidence | Result |
| --- | --- |
| Second distinct physical computer | **missing** |
| V19 | **BLOCKED / NOT EXECUTED** |

## Human sign-off (blank until humans write)

| Role | Name | Date | Verdict (PASS/FAIL/BLOCKED) | Evidence links | Notes |
| --- | --- | --- | --- | --- | --- |
| Owner | | | | | |
| Developer | | | | | |
| Independent reviewer (G7) | | | | | |
| Physical observation (G6) | | | | | |

Final release decision: **NOT AUTHORIZED**. `production_qualified=false`. `official_final_release=false`.

## Remaining defects (engineering)

- No frozen V2.2 macOS DMG from this SHA (deliberate: do not overwrite `package-output/`).
- No Windows or Linux runner in this workspace.
- Compact Overview still needs vertical scroll at 1024×768.
- Linux Fusion uses developer-built Core; official gnu tarball `bd010ed6…` is GPG-listed but **not** the Linux packager input; official ELF **members** remain UNVERIFIED here.
- V19 hardware absent.
- Official Core ignores `rpcbind`/`port` unless they sit in a `[regtest]` section.

## Agent attestation (not a human verdict)

Prepared locally by Cursor as documentation/recipes only. No Owner PASS, Developer PASS, G6, G7, Q06 acceptance, or production release is claimed.
