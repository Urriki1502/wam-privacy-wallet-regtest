# WAM Fusion — Pre-Mainnet Security Audit Charter (REGTEST)

**Date:** 2026-11-06  
**Status:** READ-ONLY SCOPING / PRELIMINARY REVIEW; NOT A SECURITY CERTIFICATION  
**Repository:** https://github.com/Urriki1502/wam-privacy-wallet-regtest  
**Candidate:** Draft PR #141, `b187cde17b12ae5f7c11f0611d5f4b1661bfc90b`  
**Baseline:** `remediation/post-dev-review-20261105` at `c61e3c5be4b8519dc6c4d9eb56d124fce84cf02d`  
**Core:** official signed WAM Core v0.1.13; **WSP pin:** `ac55f13423620252bdbf848c7e8a280c3b84721e`  
**Network:** REGTEST only; production/mainnet remains prohibited.  
**Governance:** `Q06.accepted=false`, G6/G7/V19 BLOCKED, PR Draft, no release/merge.

## Executive decision (Vietnamese)

Đề xuất mở audit độc lập cho **thực thi ví REGTEST v0.1.13** trước khi mở bất kỳ tính năng mainnet nào. Mục tiêu là bảo vệ tính đúng đắn của giao dịch, bảo mật seed/khóa riêng, chống lừa đảo Core/RPC/P2P, giữ bền vững reservations/checkpoints, khôi phục được sau lỗi, và bảo vệ toàn bộ chuỗi cung ứng ứng dụng. **Không có chứng chỉ an toàn tuyệt đối**; audit phải ghi lại giới hạn, bằng chứng và rủi ro còn lại. CI xanh không thay G7 độc lập.

## Evidence sources read in preliminary review

- `src/wam_regtest/wallet_session.py`: exact commitment, durable reservation before signing, uncertainty before broadcast, chain/UTXO equality, no automatic replay.
- `src/wam_regtest/fusion_pages.py`: distinct visible Sign and Broadcast dialogs; Cancel default.
- `src/wam_regtest/wallet_executor.py`: serialized commands and owner still pending on timeouts.
- `src/wam_regtest/core_process.py`, `core_supervisor.py`: original process and native identity checks; profile pins; REGTEST-only.
- `src/wam_regtest/network_policy.py`, `json_rpc.py`, `shared_regtest.py`: bounded RPC scope, localhost RPC, manual bounded Core P2P.
- `src/wam_regtest/official_core_v013.py`: source pins, signed release intake.
- `src/wam_regtest/bip39_seed_vault.py`, `managed_wallet_session.py`, `wallet_recovery.py`: encrypted seed, platform witness, restore and antirollback guardrails.
- `docs/INDEPENDENT-WALLET-SECURITY.md`, `docs/SECURITY-REUSE.md`, `docs/RC1_SECURITY_AND_DEPENDENCY_REVIEW.md`, `docs/Q06_FINAL_ENGINEERING_AUDIT.md`.
- GitHub 8 core qualification workflows at exact candidate HEAD were successful. This only establishes their stated test scopes.

**Important:** Older documents are source-specific historical evidence, not new candidate acceptance. Preliminary inspection did not execute fuzzing, fault injection or penetration tests; no exploitable Critical/High vulnerability has been proven or ruled out.

## Threat model — explicit attacker classes

1. Malicious remote P2P peer; chain tip / mempool / reorg / fee manipulation and eclipse-like isolation.
2. Hostile or spoofed local Core RPC endpoint; altered executable, datadir, config, cookie or port listener.
3. Another unprivileged local OS user; filesystem links, ACLs, credential and process races.
4. Same-UID malicious process; injection into GUI/native runtime, memory or Keychain-accessible surfaces. **Currently outside guaranteed protection.**
5. Corrupt or interrupted storage; power loss, partial checkpoint publication, fsync failure, stale lease, anchor rollback and lost witness.
6. Malicious or compromised installer/dependency/artifact/signing flow; poisoned build/CI runner.
7. Human mistakes: wrong recipient/network, incomplete backup, stale chain, bad fee, accidental signing/retry, imported profile mismatch.
8. Root/administrator or OS/kernel compromise: no software-only guarantee; define isolation requirements instead of claiming resistance.

## Preliminary risk register (risk priority, NOT confirmed exploit severity)

| ID | Risk/Question | Evidence status | Audit priority | Minimum validation / intended disposition |
|---|---|---|---|---|
| AUD-01 | Plaintext scanner SQLite while wallet is unlocked: exposure, temporary files and crash cleanup | Documented preview limitation | P0 mainnet review | Inventory actual contents and permissions; crash kill; leftover SQLite/WAL/SHM; prove cleanup or document leak boundary |
| AUD-02 | Seed, passphrase and native private key copies live in managed/native memory | Documented best-effort zeroization | P0 mainnet review | Trace lifetime through create/restore/lock/error; minimize copies and log/clipboard/UI leakage; assess platform hardening |
| AUD-03 | Native anchor/witness loss, dual-store rollback and inaccessible valid owner recovery | Documented availability/recovery limit | P0 mainnet review | Power-cut simulation at all publication points; safely recover on SAME authenticated chain; never reset old anchor or erase reservation |
| AUD-04 | Signing replay/double click, signing during modal delivery, unknown broadcast result | Existing controls, must adversarially validate | P0 | State-model/fault injection; exact commitment; sign once; separate broadcast; uncertain lock retained |
| AUD-05 | Core/RPC identity spoof, startup race, wrong version/genesis and inherited credentials | Existing controls, hostile scenarios unproven | P0 | Fake listener/port collision, wrong hash/owner, RPC-boundary fuzz and concurrent shutdown; no external RPC |
| AUD-06 | BIP352 scan, UTXO/fee/chain reconciliation, confirmation and reorg under malformed chain data | Genuine E2E tests exist; adversarial coverage to review | P0 | Actual Core fixtures + bounded fuzz; wrong history/coin values must fail-closed; 1/12/100-block reorg |
| AUD-07 | Backup portability and correct funded-history restore; legacy v0.1.11 to v0.1.13 migration | Explicitly PENDING / limited | P0 mainnet gate | Keep old profiles unchanged; distinguish matching mnemonic identity from restored funds; authorization/journal/crash protocol required |
| AUD-08 | Installer/build provenance, dependency integrity, SCA/CVEs, trusted signature, native loader attack | Core signed; Fusion package ad-hoc/unnotarized | P0 release gate | Independent six Core member hashes, source/WSP pin, SBOM+SCA, code-sign/notarization strategy, tampered bundle negatives |
| AUD-09 | Shared REGTEST P2P trust and mainnet discovery future design | Manual one-peer policy today; mainnet not implemented | P0 future network threat model | Manual V19; malicious peer/eclipsed node, unsolicited socket/path, no remote RPC; production Core auto-discovery only after separate audit |
| AUD-10 | Crash/DoS/stuck executor, duplicate sessions, stale lease, native witness exhaustion | Prior races fixed; limits documented | P1, P0 if funds at risk | Repeated launch/stop, resource exhaustion, timeout/cancellation semantics, power failure, no orphan adoption |
| AUD-11 | Transaction approval UI manipulation, amount/fee precision, clipboard/address substitution | Separate dialogs/source controls exist | P0 | GUI visual checks 3 OS, high-DPI, accessibility, wrong-recipient, Unicode, fee bounds, long codes |
| AUD-12 | Metadata/privacy: IP leakage, transaction linkage, logs, artifacts, screenshots | REGTEST privacy foundations only | P1, P0 for declared privacy guarantees | Verify redaction, no credential/seed/PSBT leak, peer visibility, network anonymity claims explicitly absent |
| AUD-13 | Platform gaps: macOS Keychain, Windows Credential Manager/DACL, Linux root witness | Technical CI exists; physical G6 pending | P0 | Native physical operator and root witness; no mock substitution, OS-account and symlink/hardlink attacks |
| AUD-14 | Independent reviewer coverage and fresh exact-head case ledger | G7 blocked; Q06 stale/pending | P0 release gate | Reviewer identity, signed findings/remediation, case-specific evidence with hashes; never auto-mark PASS |

## Mandatory review methodology

### Gate 0 — freeze and inventory (READ ONLY)

- Verify Git status, source SHA, exact PR branch/base, `AGENTS.md`, `ENGINEERING_HANDOFF.md`, and the canonical issue #45.
- Do not modify production or preexisting wallets, keys, seed files, native anchors, external Core processes, immutable evidence or Git history.
- Audit the full deployment model: macOS ARM64, Windows x64, Linux x86_64; GUI and headless; create/restore, same-chain funded history, local RPC and Shared REGTEST P2P.
- Record software composition, Python/PySide6/Qt/WSP/Core, toolchain, artifact signatures and dependency hashes. Identify unsupported platforms.

### Gate 1 — independent code / design review

- Inspect BIP39 entropy, normalization, derivation and WSP BIP352/scanner/PSBT/nonce/key management. Include official test vectors; no custom cryptography.
- Verify password KDF parameters and brute-force exposure for stolen backup; avoid claiming entropy from password length.
- Verify secret lifecycle: unlock, backup display, screenshots, logs, clipboard, process/environment, crash files, exceptions, core dumps, lock/quit.
- Model separate user intent, prepare, sign, broadcast, confirmation, reconcile and refusal states. Check source/binary/OS identity binding.
- Inventory every trust boundary and cross-module invariant; do not treat an internal AST audit as an external audit.

### Gate 2 — adversarial disposable REGTEST tests

- Malformed RPC and P2P responses, wrong genesis/version, competing Core listener, rewritten config/cookie, symlink/alias/hardlink, wrong owner and privilege.
- Crash/fault injection BEFORE/AFTER every durable boundary (checkpoint, native anchor, reservation, crypto, RPC submission); power-loss approximation distinguished from physical power loss.
- Verify that unknown broadcast outcomes never trigger automatic re-sign/rebroadcast, and that all irreversible locks remain attached after restart.
- Test duplicate click/late approval, cancel/timeout, delayed Core, reorg, chain tip drift, old profile rejection and failed storage transitions.
- Run native and FINAL FROZEN binaries at exact source commit on each OS. Never claim macOS tests substitute Windows/Linux.
- Fuzz untrusted JSON-RPC, peer metadata, PSBT and SQLite checkpoint parsing with bounds/time/memory limits; never use public mainnet, real seeds, or wallet datadirs.

### Gate 3 — actionable report (no code edits in the independent review phase)

Each finding: ID, title, severity [Critical/High/Medium/Low/Info], confidence [confirmed/suspected/unknown], affected source lines, security property, adversary prerequisites, reproducible TEST-ONLY steps, redacted evidence/receipt/hash, impact, recommendation, blocking gate, owner/status. Do not post unredacted exploits or secret-bearing data publicly.

- **Critical:** plausible unauthorized signature/asset theft, seed/private-key exposure at trust boundary or bypass of chain/authentication safeguards.
- **High:** reproducible irreversible data loss, replay/incorrect destination or major privilege boundary bypass.
- **Medium:** important privacy/confidentiality/integrity or availability risk without demonstrated catastrophic loss.
- **Low/Info:** defense-in-depth, documentation or UX improvements.
- Severity must reflect exploitability and impact, not merely code complexity.

### Gate 4 — remediation (separate branch and authorization)

- After findings are independently recorded, prioritize P0; smallest reviewed changes and explicit negative regression tests.
- Preserve no-mainnet guard, signed Core/WSP pins, original-owner identity, custody/antirollback and separate sign/broadcast approvals.
- Locally qualify all affected macOS frozen gates FIRST, then push dedicated security fixes and requalify native/frozen Windows/Linux/macOS at exact HEAD.
- No bypasses to gain green CI, no automatic cleanup of unknown Core, no old-profile migration without explicit verified authorization.
- Independent reviewer reruns proof and signs off; owner G6 and physical V19 remain distinct.

## Exit criteria before proposing MAINNET work

- No confirmed unresolved Critical/High finding. Every disputed or unverified P0 control is explicitly BLOCKED, not silently accepted.
- All mandatory target-OS negative tests, real Core/WSP, final frozen and retained-history recovery pass at exact source and artifact checksums.
- User-facing secure backup and recovery strategy demonstrates availability without surrendering irreversible state guarantees.
- End-user app release signature/notarization, reproducibility/provenance, vulnerability response policy and source dependency support are adequately planned/qualified.
- G6 owner physical acceptance, G7 independent security audit and V19 two-host acceptance separately proved as required.
- MAINNET chain parameters, peer discovery, P2P, broadcast, fee behavior, privacy assumptions and on-chain funds require an entirely separate authorized qualification. `mainnet_allowed=false` remains until that point.

## Safe autonomous auditor instruction (copy to independent agent)

> Review Draft PR #141 at exact commit b187cde17b12ae5f7c11f0611d5f4b1661bfc90b as an independent security reviewer. Read AGENTS.md, Issue #45, existing security documents and this charter. Start READ-ONLY; identify threats and audit every listed surface, prioritizing custody/keys, signing/broadcast, recovery, Core RPC, P2P and supply chain. Produce an evidence-linked findings register with severity, confidence and concrete negative tests. Treat prior CI PASS only as scoped evidence, not G7 signoff. Use only disposable REGTEST data for test proposals; never access real wallets, mainnet, or kill/adopt an unverified Core. Do not modify code, ledger, PR, Git history or remote issues in the discovery phase. Keep current Draft #141 intact; after the review report is complete, propose separately scoped remediation PRs. No merge or release.

## Reference links

- Source PR: https://github.com/Urriki1502/wam-privacy-wallet-regtest/pull/141
- Wallet session: https://github.com/Urriki1502/wam-privacy-wallet-regtest/blob/b187cde17b12ae5f7c11f0611d5f4b1661bfc90b/src/wam_regtest/wallet_session.py
- Previous limitations: https://github.com/Urriki1502/wam-privacy-wallet-regtest/blob/b187cde17b12ae5f7c11f0611d5f4b1661bfc90b/docs/RC1_SECURITY_AND_DEPENDENCY_REVIEW.md
- Internal audit limitations: https://github.com/Urriki1502/wam-privacy-wallet-regtest/blob/b187cde17b12ae5f7c11f0611d5f4b1661bfc90b/docs/INDEPENDENT-WALLET-SECURITY.md
- NIST SSDF: https://csrc.nist.gov/pubs/sp/800/218/final
- OWASP Secrets Management: https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet
- Bitcoin Core RPC security: https://github.com/bitcoin/bitcoin/blob/master/doc/JSON-RPC-interface.md
