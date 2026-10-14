# WAM REGTEST V1 macOS + V1.1 Windows — Codex engineering handoff

**Checkpoint: 2026-10-14, approximately 18:27 Asia/Ho_Chi_Minh.**
This is a bounded engineering handoff, not a production release declaration.
**Authoritative repo:** `Urriki1502/wam-privacy-wallet-regtest`.
Do not replace it with the previous `wam-privacy-wallet` GUI preview.

## 1. Known-good macOS baseline

- `main` checked at `50e1ea94df61b8400cbab3bffe0fbdd285c6b419`.
- Genuine WAM Core v0.1.11 macOS ARM64 with signed published artifacts, frozen WSP-1 source `ac55f13423620252bdbf848c7e8a280c3b84721e`.
- Mac source and frozen `.app/.dmg` E2E passed on main workflow `38538104971`; BIP352 28 vector suites passed `38538105031`.
- macOS has actual REGTEST Prepare / Review / Sign / Broadcast, BIP352 scanner/SQLite, encrypted backup, same-Mac Keychain anchor, crash/reservations and recovery tests. A real human Finder/Gatekeeper session remains a separate signoff gate, not implied by CI.
- PR #17 updates the *main* V1 handoff. Handle it separately from stacked Windows feature PRs.

## 2. Windows x64 staged PR chain (all DRAFT and UNMERGED)

| PR | Branch / upstream dependency | What is QUALIFIED by recorded exact-head CI |
| --- | --- | --- |
| [#18](https://github.com/Urriki1502/wam-privacy-wallet-regtest/pull/18) | base `main` | Signed official Windows Core v0.1.11 ZIP/PE64 offline, real Win32 scanner locks, WSP vector & SQLite tests. Native run `38553023417` PASS. |
| [#19](https://github.com/Urriki1502/wam-privacy-wallet-regtest/pull/19) | base #18 head | Genuine signed Windows `wamd.exe` + `wam-cli.exe`, isolated zero-peer REGTEST, 101 blocks, node stop. Native run `38553685424` PASS. |
| [#20](https://github.com/Urriki1502/wam-privacy-wallet-regtest/pull/20) | base #19 head | Actual 102-height WSP-1 BIP352 receive, SQLite history, restart with no double-credit. Native run `38554304076` PASS. |
| [#21](https://github.com/Urriki1502/wam-privacy-wallet-regtest/pull/21) | base #20 head | Qt read-only Receive/Balance/History through genuine Windows Core + real WSP scanner. Native run `38555730191` PASS. No operational signer. |
| [#22](https://github.com/Urriki1502/wam-privacy-wallet-regtest/pull/22) | base #21 head | Windows Credential Manager *public metadata only* checkpoint CAS and global mutex with native contention/stale-writer tests. Runs `38556433978` and `38556527230` PASS. Not connected to vault/session. |

When this handoff was authored, #22 head was `8c77ce5f4955ffc29b45c57f82c241cdee250542`, and final native Mac workflow on that head was **still running**. Refresh actual HEAD and exact-head checks; never carry forward stale statuses. WSP vector workflow `38556527122` and native Windows credential workflow `38556527230` had succeeded at that revision.

**Critical:** These are stacked PRs; the lack of Windows CI failures on an ancestor does NOT automatically qualify its descendant. Examine diff vs parent. Merge bottom-up only after independent review and all exact-head requirements; don't merge five PRs in reverse order. Preserve main until final review.

## 3. Proven Windows source and security boundaries

- `src/wam_regtest/windows_release_preflight.py`: exact official GPG/SHA256Sums, PE64/AMD64 ZIP checks, no execution rights.
- `src/wam_regtest/windows_core_regtest_smoke.py`: the exact verified Core ZIP is staged and executed in disposable Windows REGTEST, zero peers. Explicit opt-in.
- `src/wam_regtest/windows_wsp_regtest.py`: source-pinned scanner + public **nonsecret** BIP352 fixture; real transaction broadcast and 102-block confirmation on TEST ONLY.
- `src/wam_regtest/windows_wallet_read.py` + `windows_read_gui.py`: reuses **original** macOS `RegtestWalletWindow`, native Qt, exact signed Core hash and fresh WSP SQLite chain tip. It is READ ONLY.
- `src/wam_regtest/windows_checkpoint_anchor.py`: public generation/digest in Windows Credential Manager + same-wallet cross-process global mutex, no spend key/password. **Independent API contract only**, NOT yet plugged into real `CheckpointVault`.
- Original `src/wam_regtest/vault.py`, `encrypted_storage.py`, `wallet_session.py`, `core.py` and `package_entry.py` are **macOS dependent**. Do not flip a platform flag or add mock fcntl/Keychain to bypass fail-closed controls.
- Original Windows GUI/Qt-only packaging exists in old repo PR #170 and #206; borrow packaging/build tactics, NOT their preview-only RPC/mock assumptions.
- Linux remains HOLD. BIP352 x PayJoin transaction execution remains V2; V1 PayJoin review is validation-only.

## 4. Mandatory work before Windows can claim functional macOS parity

**W4.1 Secure custody (P0):** Implement native owner-only Windows datadir, ACL/owner validation, reject junctions/reparse points, secure create-only ciphertext publication/atomicity, journal & crash tests. Only after independent fail-closed validation integrate `WindowsCredentialAnchor` with a Windows-native `CheckpointVault` equivalent. Prove generation/digest monotonicity, stale-writer and file-only rollback denial; reject cross-user access and competing sessions. The credential anchor itself is not enough.

**W4.2 Operational signer (P0):** Reuse pinned WSP-1 transaction build, the macOS economic-intent `WalletSession`, irreversible reservation commits **before** native signature, no silent rollback after uncertain broadcast, separate user approvals for Prepare/Sign/Broadcast. Test live Core mempool+confirmation, malformed proposal refusal, process-crash and uncertain-state preservation on Windows. Do not enable until W4.1 passes.

**W4.3 Backup/recovery (P0):** Encrypted snapshots, wrong passphrase, crash/restart, same-user same-PC recovery, wrong store/anchor and stale file rollback denial, regtest chain rescan and reservations preserved. No unsupported profile migration claims.

**W4.4 Frozen Windows application (P1):** Adapt old repo Windows PyInstaller recipe to package **this real** wallet, PySide6 native resources, pinned WSP/coin libraries and exact official Core. Verify PE file hashes/manifest after bundling, packaged process is genuine, no DLL substitution, and run fresh-process Windows GUI, sign/broadcast/recover E2E. Emit `.exe`/installer artifact and checksum. Qt preview success is not final wallet evidence.

**W4.5 Release gates (P0):** macOS baseline must remain PASS; Windows signed Core, BIP352 vectors, WSP scanner/locks, real payment, Qt read, wallet E2E, recovery and negative tests PASS on exact PR HEAD. Final hands-on Windows 10/11 x64 operator acceptance distinct from GitHub Windows Server runner. Human hands-on Mac Finder acceptance likewise remains separately required.

## 5. Execution rules for next Codex session

1. Refresh main, all stacked PRs, actual local Mac checkout and workflow statuses. Don't overwrite uncommitted state.
2. Complete security integration in small PRs with source/test evidence. No CI/test skips to force green; keep the old `main` Mac flow intact.
3. Use REGTEST only, disposable public fixture and fresh test wallets. Never use mainnet, real keys or money.
4. Preserve source pin, official Core GPG fingerprint and SHA256 identity; do not modify upstream Core/WSP, or import broad legacy mock implementations.
5. Do not merge, tag a Final release, or assert macOS/Windows functional parity until all gates above are satisfied.
6. Provide a final two-platform matrix: feature, exact commit, CI job/run, platform, result, user-facing artifact digest, remaining blockers and honest signoff.
