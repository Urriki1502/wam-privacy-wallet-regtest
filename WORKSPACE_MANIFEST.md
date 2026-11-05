# Canonical workspace manifest

## Current status — 2026-11-05 pre-Codex handoff

The sections below this one are historical checkpoints. They still describe older SHAs (`29448e5`, `e48d6cc`, `aaf2de2`, and the 2026-11-04 Phase 0 branch). They are not the current source identity and were not rewritten as if `c61e3c5` had produced them.

| Item | Actual local result |
|---|---|
| Workspace and Git root | `/Users/dinhdang/Documents/WAM-Q06-Audit-20261102` |
| Branch | `remediation/post-dev-review-20261105` |
| Qualified executable SHA | `c61e3c5be4b8519dc6c4d9eb56d124fce84cf02d` |
| Remote | `https://github.com/Urriki1502/wam-privacy-wallet-regtest.git` |
| Fetched remediation tip | same SHA, ahead/behind 0/0. No remote-tracking ref is stored for this branch because `remote.origin.fetch` only maps the older Q06 feature branch. |
| Other worktree | `/Users/dinhdang/Documents/WAM-RC-sidecars/checkout-56ea3618` detached `56ea3618`, retained |
| Public RC index | `artifacts/rc-c61e3c5/` local-only via `.git/info/exclude` |
| Inventory index | `evidence/workspace-audit/INVENTORY_20261105.md` local-only |
| Private data | `bundle-input/`, `.wam-regtest-temp/`, `dist/` retained and not copied into public indexes |
| Historical builds | `build/qualified-*`, `build/retained-artifacts`, `package-output/` retained in place |
| Live processes | no `wamd` or wallet GUI at audit time; historical PIDs were not signalled |
| Acceptance | Q06 accepted=false; G6 BLOCKED; G7 BLOCKED; V19 BLOCKED / NOT EXECUTED |

Three-platform RC for `c61e3c5`, inner package SHA256 re-hashed locally on 2026-11-05:

- macOS run `42040071124`, artifact `13424195214`: DMG `e1128214d12970f759b4e612646a03d8003a3d6da951c365a291595d164ad346`; app zip `039b5be60b8b18355b890035075236304a0ac31adab7df5388f261ad6155d413`
- Windows run `42045852754`, artifact `13424489894`: zip `13fdc01f87959ba761eba96ebef2942bca1b0fda3ed2f52129f4031dee62d2b5`. Also success: `42045859130`, `42045866296`, `42045874094`, `42045880498`
- Linux run `42045846771`, 9/9: desktop `90bc21e6af55091e974919ef60f4bc9dbbfb4e1c8d2aaf18b1df69367342c549`; headless `77f1f2c986d3fb66c922765796952aef326573ba58856dc484aea7632b990647`

Core remains official signed v0.1.11 on macOS and Windows, and reviewed developer-built v0.1.11 on Linux (`official_signed_core_release=false`). WSP remains `ac55f13423620252bdbf848c7e8a280c3b84721e`. v0.1.13 is not integrated. A later documentation commit of this file does not requalify those packages.

Resume: read `ENGINEERING_HANDOFF.md` first, acquire `python3 scripts/engineering_lease.py --hold`, and start the v0.1.13 migration only on a dedicated branch in the next authorized session. Do not push, merge, or dispatch CI from this inventory update.

**Historical V1-NET runtime/build checkpoint: `29448e5e89079dc070b83766031c91c5ef1a9195`.** Actual frozen macOS/Core/Cocoa V1–V18 PASS (including explicit GUI reorg reconciliation + restart and isolated Q06 on the same binary); V19 physical two machines BLOCKED. Artifact `build/qualified-v1-29448e5/package-output/WAM-Privacy-Wallet-REGTEST-macOS-ARM64.dmg`, SHA256 `3bea788d550bffa7b4195f827a8891c1aeafde2b5fec0ea85aa404b1981eb07a`; executable `a86046ada47f9df6a57df4d93dcc7671281f3aa058624c8f7f66de9d59ed2535`. All 19 manifest members, ZIP and read-only DMG contents independently matched. This focused V1 qualification does not relabel unexecuted full exact-commit Q01–Q05/cross-OS checks as PASS. [Current detailed evidence](docs/V1_NET_LOCAL_ENGINEERING_20261104.md).

Source regression 611 discovered / 578 PASS / 33 SKIP / exit 0; latest focused reconciliation guards 7 PASS. Additional real native recovery from still-live faulted sessions passed with unchanged reservations and clean new owners. Historical orphan PIDs 7234/7250 remain read-only/unauthorized for process actions; new tests used 45954–45957. Product/two-machine defaults remain 29554/29555. Old owner-tested/Q06/V1 artifacts, failed receipts and private runtime generations are preserved. Q06 accepted=false; G6 physical retest pending, G7 independent BLOCKED; no acceptance ledger change, push, merge, CI dispatch or mainnet.

Read `ENGINEERING_HANDOFF.md` FIRST for transfer/current Git/process state. It is an intentionally Git-ignored mutable operational document, not runtime source or another acceptance ledger. Acquire the existing engineering lease before any edits; Codex and Cursor must not write concurrently. A qualified runtime SHA above may precede documentation-only HEAD updates; verify both.

Latest standalone Q06 artifact: qualified runtime/build source `e48d6cc23eeb36e279611608f6021291142a0e04`, Q06 branch documentation HEAD `f9c23f3`. Artifact `build/qualified-q06-e48d6cc/package-output/WAM-Privacy-Wallet-REGTEST-macOS-ARM64.dmg`, SHA256 `961bdc61c2c69ef15e3fd6d3719602b67a21653dc512854a80d42b113ac2acd0`; 104 scoped Q06 source PASS / exit 0, actual final frozen Q01–Q06/Core/GUI/Q05 gates PASS, 54 manifest members and read-only DMG contents independently verified. See [current Q06 evidence](docs/Q06_LOCAL_STABILIZATION_20261104.md). This DMG has isolated REGTEST only; old qualified snapshots remain preserved.

V1 code checkpoint `cbfafee` follows separate local commits `9baac93`, `84249fe`, `ba0c823`, `7ba9d3a`. Latest focused policy/native-dialog/cleanup scope: 10 PASS / exit 0. The earlier full source scope remains 602 discovered / 569 PASS / 33 SKIP / exit 0, rather than an assertion that every later source change was replayed in that full run. Exact-commit network/frozen V1, checkpoint-crossing reorg wallet recovery, and physical two-machine evidence remain unqualified. Two orphaned failed-lab Core processes still require a narrow owner exception/manual stop; no process action is authorized by their historical PID alone. [V1 evidence and next actions](docs/V1_NET_LOCAL_ENGINEERING_20261104.md). Q06 accepted=false; G6 owner retest open, G7 independent BLOCKED; no formal handoff/merge/release acceptance.

Current V1 continuation (2026-11-04): local branch `feature/v1-net-shared-regtest-20261104`; scoped implementation/evidence and unresolved process/reorg/frozen/two-machine gates are documented in [V1-NET local engineering](docs/V1_NET_LOCAL_ENGINEERING_20261104.md). Native development-tree V1–V16 passed; this is not exact-commit/frozen/physical acceptance. Source regression: 602 discovered / 569 PASS / 33 SKIP / exit 0, plus 8 focused shared-policy/cleanup PASS. Two orphaned disposable reorg Core owners require a narrow owner exception/manual stop before reusing standard ports. Preserve their profiles, journals and signed evidence. Q06 accepted=false; do not treat the historical Phase 0 tables below as current branch state.

Current continuation: owner-approved local stabilization now has qualified runtime/build source `aaf2de2a13471f955c367561e64276e5353180c5`, 561 executed source PASS / 33 platform skips, and successful actual-Core/native/frozen macOS evidence. See [current stabilization result](docs/Q06_LOCAL_STABILIZATION_20261104.md). Q06 accepted=false; physical/independent/full integration gates remain open. The owner has authorized a separate local V1-NET branch after these tests. The Phase 0 inventory below is a dated historical snapshot, not current HEAD/artifact status.

Stable Q06 artifact snapshot: `build/qualified-q06-aaf2de2/package-output/`; DMG SHA256 `d482f8c2562a7f4c2162d58595ad808357b74ad7c0555419c08df23f4f227f43`. Older owner-tested and failed artifacts are preserved at `build/retained-artifacts/`; engineering logs at `build/local-evidence-20261104/`; local pinned toolchain at `build/local-toolchain/`. Private disposable runtime data is retained separately under `.wam-regtest-temp` / `bundle-input` and must not be committed or shipped.

Audit date: 2026-11-04. Scope: PHASE 0 ONLY. No application/test/fixture edits, tests, Core launch, wallet operations, build, commits, branch changes, push, CI dispatch or acceptance-ledger mutation were performed. The six root audit documents are review material, not another acceptance ledger.

Canonical path: `/Users/dinhdang/Documents/WAM-Q06-Audit-20261102`.

## Source identity

| Item | Read-only observation |
|---|---|
| Repository | Present at canonical root; one registered worktree |
| Branch | `feature/issue45-q06-bip39-12word-20261031` |
| HEAD | `8df48952eb4c3c6f2f1db86d31c58125fb2a7e7e` |
| Initial tracked/untracked status | Clean; generated outputs are ignored |
| Literal source verification | All 405 HEAD file blobs match actual local bytes; no application imports used |
| Git limitation | Shallow boundary `f6587f6df1061ae08fc12d5cf3a8e82dda67421d`; no local main/origin/main ref; main merge commits unavailable as local objects |
| Live main, GitHub GET | `35553f674851282c6e107e02ba02ef2a7ac5ce64` |
| Live PR #140 | Draft, unmerged; head `414bebb07ac4705274a0b82617d8e72441b77cbe` |
| Relationship | PR head is a local ancestor; five additional local commits. GitHub main→PR comparison: ahead 166, behind 0, merge base equals live main. This is not approval to merge that history |
| WSP checkout | Nested independent repo `wsp-upstream`, detached `ac55f13423620252bdbf848c7e8a280c3b84721e`, clean; all 33 WSP Python blobs match pinned Git objects |

Canonical source is a verified candidate matching the owner-reported HEAD, rather than merely a DMG directory. Historical repositories are retained as evidence/dependency candidates. None was selected as a replacement source. Full historical integration ancestry cannot be established from this shallow checkout alone; do not infer missing objects mean non-ancestry.

Five local-only commits, newest first: `8df4895` modal recovery dialog; `fc2ae55` backup/recovery UX; `24447ff` reopen import; `5b02e7b` in-session lock/unlock; `95f874a` executor acknowledgement command. Their combined diff from PR head touches eight files, 799 additions / 81 deletions. See the architecture matrix and gap register before approving edits.

## Immutable artifact observations

| Artifact | Bytes | Independently calculated SHA256 |
|---|---:|---|
| `package-output/WAM-Privacy-Wallet-REGTEST-macOS-ARM64.dmg` | 63908849 | `b2e52eef06bf2c088797b629dd0fc453df0c9ec58c16caef5abaeec967df18c7` |
| `package-output/WAM-Privacy-Wallet-REGTEST-macOS-ARM64.app.zip` | 56246857 | `5c92b4667a833d3bc27bcd714061b188f7427a9858e4345d49fcab5dec8c9f13` |
| ZIP and dist app executable | See package metadata | `d0889b1c90dda98db3c565bd1c656c13f8c87beba564bb46c623c0fdb320bf93` |
| `core/wamd` | 12256680 | `7298de701e467eb28b4806cbcbe35edb393861b4b97117017fee4c1b194e3068` |
| `core/wam-cli` | 511736 | `81a031ebf9b3060b19061b29756d43bcd09b32ad778348b8c3d8321397076e82` |

The DMG matches the owner's expected bytes. The ZIP contains the same executable as dist, original matching Core members under Frameworks/core, and `Resources/Q05_BUILD_SOURCE.json` naming this HEAD. Resource aliases are ZIP symlinks, not alternate tiny Core executables. All 54 files in the release candidate manifest exist and match their recorded hashes. The app is ARM64, ad-hoc signed, with no TeamIdentifier (`codesign -dv`). No Developer ID/notarization qualification is inferred.

Build/source receipt claims `source_unchanged_across_build=true` and `tracked_source_matches_head=true`; its inventory digest is `cfc680dabc12b11d3dab5fe160aca4ca9e181aef10dfba732604abfbaf92b307`. The stamp explicitly sets dependency-supply-chain qualification and same-UID host tamper proof false. DMG interior was not mounted or executed during Phase 0: source→DMG association relies on matching manifest, ZIP stamp and existing build evidence, not a fresh independent reproducible build or embedded-DMG-code comparison.

Core receipt names official v0.1.11 archive SHA `6e10ea10cc324e947c9d646ba8276412175edd0f168c0d95ca5228ccc37f5afb`, publisher fingerprint `4BD4A8D3AFD43F5CBCB500E23798462FE00ADBA4`, and `signed_archive_verified=true`. Actual executable hashes match local receipt and ZIP; the detached upstream signature was not freshly reverified here. Preserve reviewed developer-built Linux trust as distinct from signed official Mac/Windows.

## Custody and session discipline

Engineering lease was acquired with the required `python3 scripts/engineering_lease.py --hold` after filesystem approval for `.git/wam-engineering.lock`; it is held while audit work runs and released at audit completion. It guards cooperating work in this Git common directory only. Process inventory via `ps` was denied by the sandbox; absence of other agents/Core processes is not established. No process was adopted, stopped or signalled.

`tests/acceptance/issue45.json` remains the sole case-level ledger. Active Q06; `accepted=false`. Owner's 2026-11-04 physical Send/Unlock failures supersede any interpretation of blanket acceptance, without changing the ledger in Phase 0. Current owner physical G6: FAIL pending repair/retest; G7 independent: BLOCKED. Engineering handoff NO; full acceptance NO; V1-NET BLOCKED.

Before the next session: verify path, this manifest, HEAD, dirty/untracked/ignored outputs, ledger and this audit; acquire lease; identify concurrent changes; obtain the owner's Phase 1 approval with an exact repair scope. Keep all original wallet state and existing builds. No GitHub push/merge/dispatch or source commit is authorized by this audit.

## Document index

- [Full audit](PHASE0_FULL_AUDIT_REPORT.md)
- [Architecture and case matrix](Q01_Q06_ARCHITECTURE_MATRIX.md)
- [Gap/risk register](Q05_Q06_GAP_REGISTER.md)
- [Legacy inventory and archival proposal](LEGACY_WORKSPACE_INVENTORY.md)
- [Repair sequence for owner approval](Q05_Q06_REPAIR_PLAN.md)


## Canonical structured inventory (read-only metadata)

| Path | Classification / purpose | Regular files / bytes | Notes |
|---|---|---:|---|
| `.DS_Store` | Root source/document or preview artifact | 1 / 14340 | 0 symlinks; bytes counted without following links |
| `.git` | A Git metadata; shallow source history | 108 / 5117672 | 0 symlinks; bytes counted without following links |
| `.github` | Source CI workflow contracts | 10 / 101591 | 0 symlinks; bytes counted without following links |
| `.gitignore` | Root source/document or preview artifact | 1 / 388 | 0 symlinks; bytes counted without following links |
| `.wam-regtest-temp` | E disposable runtime parent; empty at audit | 0 / 0 | 0 symlinks; bytes counted without following links |
| `AGENTS.md` | Root source/document or preview artifact | 1 / 9446 | 0 symlinks; bytes counted without following links |
| `LICENSE` | Root source/document or preview artifact | 1 / 1088 | 0 symlinks; bytes counted without following links |
| `README.md` | Root source/document or preview artifact | 1 / 11519 | 0 symlinks; bytes counted without following links |
| `WAM Privacy Wallet REGTEST.spec` | Root source/document or preview artifact | 1 / 1995 | 0 symlinks; bytes counted without following links |
| `assets` | Source branding/icon inputs | 3 / 2780181 | 0 symlinks; bytes counted without following links |
| `build` | C generated PyInstaller build/TOC/cache | 16 / 18648181 | 0 symlinks; bytes counted without following links |
| `bundle-input` | C transient build staging; empty at inspection | 0 / 0 | 0 symlinks; bytes counted without following links |
| `core` | C pinned native Core binary pair/receipt | 3 / 12769002 | 0 symlinks; bytes counted without following links |
| `dist` | C final frozen .app plus onedir sibling | 695 / 276515541 | 183 symlinks; bytes counted without following links |
| `docs` | B source contracts and historical acceptance evidence | 177 / 2315466 | 0 symlinks; bytes counted without following links |
| `fusion-ui-review` | B/C screenshots and visual receipt | 16 / 2006669 | 0 symlinks; bytes counted without following links |
| `package-output` | B/C current and preserved artifacts/receipts | 59 / 246051678 | 0 symlinks; bytes counted without following links |
| `pyproject.toml` | Root source/document or preview artifact | 1 / 576 | 0 symlinks; bytes counted without following links |
| `real-regtest-gui-preview.png` | Root source/document or preview artifact | 1 / 182699 | 0 symlinks; bytes counted without following links |
| `real-regtest-security-preview.png` | Root source/document or preview artifact | 1 / 90347 | 0 symlinks; bytes counted without following links |
| `real-regtest-wallet-preview.png` | Root source/document or preview artifact | 1 / 129669 | 0 symlinks; bytes counted without following links |
| `requirements` | Source exact dependency hash locks | 2 / 33142 | 0 symlinks; bytes counted without following links |
| `scripts` | Source build/qualification/governance scripts | 32 / 263180 | 0 symlinks; bytes counted without following links |
| `src` | A application modules and generated egg metadata | 197 / 2545471 | 0 symlinks; bytes counted without following links |
| `tests` | Source acceptance ledger, tests and public fixtures | 154 / 2675196 | 0 symlinks; bytes counted without following links |
| `wsp-upstream` | A pinned independent dependency Git repo | 1664 / 3320389 | 0 symlinks; bytes counted without following links |

Independent reconstruction of the public source-inventory digest from all current Git-tracked blobs/bytes matches the build receipt: `cfc680dabc12b11d3dab5fe160aca4ca9e181aef10dfba732604abfbaf92b307`. This verifies current input identity, not historical host integrity.

Lease lifecycle: engineering lease released cleanly at Phase 0 completion; no engineering continues in the background. Reacquire before any approved follow-up work.

## Owner-approved continuation — 2026-11-04

Owner approved Phase 0 and authorized scoped local fixes/tests/builds/commits in this workspace, then a separate local V1-NET branch only after Q05/Q06 engineering tests pass. This supersedes the earlier stop-for-Phase-1-approval and advance-approval wording in the audit/repair proposal. No remote push/PR/merge/dispatch; no original wallet migration/deletion; accepted=false and G6/G7 remain unchanged. The required engineering lease was reacquired for this continuation. Native Qt tests require desktop access outside the process sandbox; environment/tool permissions remain distinct from owner scope authorization.
