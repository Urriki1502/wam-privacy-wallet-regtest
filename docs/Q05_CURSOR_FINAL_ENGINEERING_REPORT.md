# Q05 Cursor final engineering report — owner review 2026-10-29

**Executive outcome: CONDITIONAL**

This isolated Cursor branch is a reviewable engineering candidate for
history completeness, bounded GUI presentation, and fail-closed
interrupted-publication inspection. It is **not** a canonical Q05
acceptance package. Genuine Core, native/frozen three-OS, physical, and
independent-review predicates are unsatisfied. Ledger `accepted` remains
`false` on purpose.

Prepared 28 Oct 2026, ~22:50 ICT (Asia/Saigon). Linux x86_64 cloud agent.
No signed `wamd` / `wam-cli` on this host.

---

## 1. Outcome

| Question | Answer |
|---|---|
| Formal Q-GATE acceptance | **NO** |
| Owner merge of this branch or PR #138 | **NO** (conditional later) |
| Ready for Codex inspect / cherry-pick of history + inspect APIs | **YES** |
| Ready for native/frozen/physical PASS | **NO** |

## 2. Branch, HEAD, commits

- Isolated branch: `cursor/q05-history-pagination-9c81`
- Implementation HEAD at this report’s engineering commit:
  `ed538a36daee77b0eed61508eee36ff16ebc8bad`
- Codex Draft #138 HEAD (revalidated): `9b0361c6211f500ef78d0ace171c1bb6a5a10329`
- `origin/main`: `4bc6f658e4c00e0a8c5d3c9da7d79aab0a54dfae`
- Base of Cursor work: Codex `9b0361c` (not rebased)

Cursor-only commits after Codex HEAD:

1. `9e55ab92f9e3007d33a4026dabe87b3f68721401` — snapshot history paging
2. `5910727d16e8df6c59b81f80578d660e6f676de4` — 1,001,000 ceiling + session/GUI SQL paging
3. `a757f4c74e6503911478ba30644c44092701704f` — Engineer 2 checkpoint note
4. `ed538a36daee77b0eed61508eee36ff16ebc8bad` — GUI window 250 + publication inspect
5. This report commit (follows)

No force-push. No second PR. No merge.

## 3. Files and architecture

**Changed (Cursor):** `history_pages.py`, `managed_wallet_checkpoint.py`,
`wallet_session.py`, `wallet_read.py`, `windows_wallet_read.py`,
`fusion_pages.py`, `gui_errors.py`, tests, this report and Engineer 2 checkpoint.

**Decisions**

- Public `Wallet.history()` / `balance()` each `BEGIN IMMEDIATE`; complete
  reads use `_history` / `_balance` inside one `store.transaction()`.
- Canonical fingerprint is SHA-256 of `json.dumps(..., sort_keys=True)` of
  the full ASC `height,txid` array (same bytes as hashing the whole list).
- WSP hard ceiling: 1_000_000 offset + 1000 limit = **1,001,000** readable
  rows. Exactly that count is complete; 1,001,001 is `HISTORY_INCOMPLETE`.
- GUI/session keep a **250-row newest window** (`deque` tail) after hashing
  every row. Incomplete windows are labeled, not silent truncation.
- Disclosure uses `SELECT ... WHERE txid=?` on the live snapshot, not a
  100-row `history()` scan.
- Interrupted publication: Codex already fail-closes (orphan preserved,
  runtime blocks reopen, `recovery_completed=false`). Cursor adds
  read-only `publication_ambiguity()`; **no** auto-adopt, delete, or
  native-anchor advance.
- Vault/KDF/AEAD, journal v1/v2, supervisor ownership, broadcast policy
  unchanged.

## 4. Requirements

**Completed (engineering, this branch, unit-proven)**

- Complete WSP history fingerprint for 0 / 999 / 1000 / 1001 / 2500 /
  1,001,000; reject 1,001,001.
- Consistent SQLite snapshot; detect overlapping/short/mutated pages.
- Chain-tip match before and after long history reads (checkpoint + session).
- Signed/uncertain reservation fingerprint preserved in observation.
- Bounded GUI history presentation with completeness flag.
- Fail-closed publication ambiguity inspect.

**Partial**

- Interrupted recovery: refuse/preserve proven; **successful**
  authenticated resume after cut is intentionally **not** implemented
  (would require owner-reviewed adopt-or-quarantine of plaintext runtime).
- Dirty-owner / crash recovery: remains Codex `CoreSupervisor`
  recover-stop/recover-dead on #138; Cursor did not duplicate it.
- GUI START→RESTORE managed-Core: still `WalletSession` (own Core), not
  supervisor-owned GUI. No Core binary here to integrate.

**Blocked**

- Genuine Core E2E, frozen packages, physical clean-device, independent
  review, owner merge, Q04 G6/G7, Windows 125% DPI on this agent.

## 5. Test matrix (actual)

| Suite | Result |
|---|---|
| `unittest discover -s tests -p 'test_q05*.py'` | **106 PASS / 0 FAIL / 0 SKIP** at `ed538a3` |
| `tests.test_history_pages` | PASS |
| `tests.test_gui_error_privacy` | PASS |
| `tests.test_q_gate_ledger` | **13 PASS** (ledger still `accepted=false`) |
| `tests.test_fusion_design` | **NOT EXECUTED** (no PySide6 in this image) |
| Genuine signed Core REGTEST | **NOT EXECUTED** (no `wamd`/`wam-cli`) |
| macOS native/frozen | **NOT EXECUTED** |
| Windows native/frozen/DPI 125%/150% | **NOT EXECUTED** |
| Linux frozen / developer Core | **NOT EXECUTED** |
| Physical / independent | **NOT EXECUTED** |
| Full CI matrix on this SHA | **NOT EXECUTED** (no dispatch of GitHub workflows from this agent) |

Do not treat unit PASS as native PASS.

## 6. Genuine Core / native / frozen by OS

| OS | Genuine Core | Native Q05 | Frozen |
|---|---|---|---|
| macOS ARM64 | NOT EXECUTED | NOT EXECUTED (Codex supplemental receipts on **other SHAs** such as 264faa2 are not this HEAD) | NOT EXECUTED |
| Windows x64 | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |
| Linux x86_64 | NOT EXECUTED | unit/source only | NOT EXECUTED |

Historical FAIL retained in ledger (Windows fixture `d6a3acf` job 122798348528). Not relabeled.

## 7. All 37 canonical Q05 cases

Ledger file: `tests/acceptance/issue45.json`. **No case was written to PASS.**
Implementation SHA for Cursor engineering: `ed538a36daee77b0eed61508eee36ff16ebc8bad`.

| ID | Platform | Layer | Canonical | Engineering note |
|---|---|---|---|---|
| Q05-COVERAGE | shared | SOURCE | PENDING | Matrix enumerated; packaging provenance incomplete |
| Q05-OWNERSHIP-BOUNDARY | shared | SOURCE | PENDING | Codex supervisor contracts exist; not re-proven this HEAD native |
| Q05-IDENTITY-FINGERPRINT | shared | SOURCE | PENDING | Journal v2 on #138; Cursor did not change identity |
| Q05-DURABILITY-CONTRACT | shared | SOURCE | PENDING | History fingerprint + vault save order unchanged; no Core fsync E2E here |
| Q05-NO-SILENT-RESTORE | shared | NEGATIVE | PENDING | Runtime/orphan inspect + existing restore refusals; no Core |
| Q05-WRONG-CORE-REFUSAL | shared | NEGATIVE | PENDING | Existing contracts; Core not run |
| Q05-STALE-LEASE-RECOVERY | shared | NEGATIVE | PENDING | Codex; Cursor did not add PID adoption |
| Q05-OS-PROVENANCE | shared | SOURCE | PENDING | Pins recorded; this SHA not frozen |
| Q05-MANAGED-START-MACOS | macos-arm64 | CORE_E2E | PENDING | NOT EXECUTED |
| Q05-GRACEFUL-SHUTDOWN-MACOS | macos-arm64 | CORE_E2E | PENDING | NOT EXECUTED |
| Q05-CRASH-RECOVER-MACOS | macos-arm64 | CORE_E2E | PENDING | NOT EXECUTED (older SHA local_requalification only) |
| Q05-REATTACH-MACOS | macos-arm64 | CORE_E2E | PENDING | NOT EXECUTED |
| Q05-PERSISTENCE-MACOS | macos-arm64 | CORE_E2E | PENDING | History paging is source-only |
| Q05-INTERRUPTED-RECOVERY-MACOS | macos-arm64 | NEGATIVE | PENDING | Probe refuse/preserve on other SHA; this HEAD NOT EXECUTED |
| Q05-CONCURRENT-OWNER-MACOS | macos-arm64 | NEGATIVE | PENDING | NOT EXECUTED |
| Q05-FROZEN-MACOS | macos-arm64 | FROZEN | PENDING | NOT EXECUTED |
| Q05-MANAGED-START-WINDOWS | windows-x64 | CORE_E2E | PENDING | NOT EXECUTED |
| Q05-GRACEFUL-SHUTDOWN-WINDOWS | windows-x64 | CORE_E2E | PENDING | NOT EXECUTED |
| Q05-CRASH-RECOVER-WINDOWS | windows-x64 | CORE_E2E | PENDING | NOT EXECUTED |
| Q05-REATTACH-WINDOWS | windows-x64 | CORE_E2E | PENDING | NOT EXECUTED |
| Q05-PERSISTENCE-WINDOWS | windows-x64 | CORE_E2E | PENDING | SQL window source only |
| Q05-INTERRUPTED-RECOVERY-WINDOWS | windows-x64 | NEGATIVE | PENDING | NOT EXECUTED |
| Q05-CONCURRENT-OWNER-WINDOWS | windows-x64 | NEGATIVE | PENDING | NOT EXECUTED |
| Q05-FROZEN-WINDOWS | windows-x64 | FROZEN | PENDING | NOT EXECUTED; historical 125% FAIL retained |
| Q05-MANAGED-START-LINUX | linux-x86_64 | CORE_E2E | PENDING | No Core binary |
| Q05-GRACEFUL-SHUTDOWN-LINUX | linux-x86_64 | CORE_E2E | PENDING | No Core binary |
| Q05-CRASH-RECOVER-LINUX | linux-x86_64 | CORE_E2E | PENDING | No Core binary |
| Q05-REATTACH-LINUX | linux-x86_64 | CORE_E2E | PENDING | No Core binary |
| Q05-PERSISTENCE-LINUX | linux-x86_64 | CORE_E2E | PENDING | Unit only |
| Q05-INTERRUPTED-RECOVERY-LINUX | linux-x86_64 | NEGATIVE | PENDING | Inspect API unit; no Core cut |
| Q05-CONCURRENT-OWNER-LINUX | linux-x86_64 | NEGATIVE | PENDING | Supervisor unit on #138; not this native |
| Q05-FROZEN-LINUX | linux-x86_64 | FROZEN | PENDING | NOT EXECUTED |
| Q05-PHYSICAL-MACOS | macos-arm64 | PHYSICAL | PENDING | Operator |
| Q05-PHYSICAL-WINDOWS | windows-x64 | PHYSICAL | PENDING | Operator + DPI |
| Q05-PHYSICAL-LINUX | linux-x86_64 | PHYSICAL | PENDING | Operator |
| Q05-INDEPENDENT | shared | DEV_REVIEWED | PENDING | Independent reviewer |
| Q05-MERGE-AUTH | shared | MAIN | PENDING | Owner 2026-10-29+ |

## 8. G0–G7 (Q05 object)

All applicable, all **PENDING** in the ledger. Not updated.

| Gate | Meaning (short) | Disposition |
|---|---|---|
| G0 | Provenance / coverage | PENDING |
| G1 | Source security / identity | PENDING |
| G2 | Native Core E2E | PENDING |
| G3 | Durability / recovery | PENDING |
| G4 | Trust / wrong-core | PENDING |
| G5 | Frozen / merge artifacts | PENDING |
| G6 | Physical | PENDING (Q04 G6 also BLOCKED separately) |
| G7 | Independent review | PENDING (Q04 G7 BLOCKED separately) |

## 9. Security / recovery / custody / reservations

- REGTEST only; no mainnet endpoint added.
- No automatic uncertain-tx retry; no reservation release.
- Native anchor not advanced by Cursor recovery code.
- Unknown SQLite / orphan `.enc` preserved; `publication_ambiguity`
  `automatic_recovery_allowed=false`.
- History GUI cannot claim a 250-row window is the full wallet when
  `history_complete` is false.
- Codex interrupted probe remains the native refuse/preserve proof
  (`recovery_completed=false` on its SHA), not this HEAD.

## 10. Open P0/P1 and external blockers

**P0**

- No genuine Core on this agent → no START→RESTORE proof.
- Successful interrupted-write recovery still open by design.
- Cross-process dirty-owner with live Core still Codex/#138 native work.
- Packaged GUI + managed supervisor not wired.

**P1**

- Windows 125% frozen clipping historical FAIL (ledger historical_evidence).
- Full CI on Cursor SHA not run.
- PySide6 absent here; HistoryPage banner untested in GUI process.

**External**

- Physical three-OS, independent reviewer, owner merge authorization.
- Q04 G6/G7 must not be waived.

## 11. Integration plan for Codex PR #138

Do **not** merge the Cursor branch as a stack. Suggested cherry-picks onto
#138 after Codex recovery lands:

1. `9e55ab9` history snapshot paging (or equivalent squash of 1–2).
2. `5910727` session/read paging + 1,001,000 ceiling.
3. `ed538a3` GUI window + `publication_ambiguity`.
4. Skip or rewrite checkpoint markdown commits if they fight
   `docs/Q05_STAGE_A_CHECKPOINT.md`.

Conflicts: low if Codex has not edited `managed_wallet_checkpoint._snapshot`
or `wallet_session.snapshot`. If Codex still has `wallet.history(limit=1000)`,
take Cursor’s `_snapshot` / `history_pages.py` wholesale.

Re-run: `test_q05*.py`, `test_history_pages.py`, then native interrupted
probe and wallet checkpoint probe on the **combined** SHA.

## 12. Owner merge recommendation

**NO** for main / acceptance.

**CONDITIONAL YES** for later integration into Draft #138 only after:

- Codex reviews history_pages + no nested BEGIN IMMEDIATE.
- Combined native macOS (at least) checkpoint + interrupted-cut probe on
  the merged SHA.
- No ledger `accepted=true` until G2/G3/G5/G6/G7 evidence exists.

Q05 remains `processing=ACTIVE`, 37 PENDING, `accepted=false`.
ENGINEERING HANDOFF: **NO**. FULL Q ACCEPTED: **NO**.
