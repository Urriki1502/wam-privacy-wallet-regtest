# Q10–Q20 source reuse inventory — 2026-11-07

Baseline `64f207c1c2bf804e7392816603487d877e7ef359`. This is a dependency
inventory, not a second acceptance ledger. Source changes invalidate affected
qualification; original ledger and all historical FAIL receipts remain intact.

| Q | Reuse source | Existing tests/proof | Verified gap / local action |
|---|---|---|---|
| Q10 PARTIAL | bip39_recovery_proof.py, bip39_reconciliation.py, bip39_scanner_checkpoint.py, wallet_recovery.py | test_q06_bip39_recovery_proof.py, test_q06_bip39_scanner_checkpoint.py;64f genuine native/frozen same-chain proof | Seven-field public metadata contract absent. Seed-only recovery grants no signer/reservations authority; clean-device custody remains BLOCKED. No .dat recovery. |
| Q11 PARTIAL | wsp_live.py public mining fixture; WSP wallet._balance; exact Core subsidy.cpp and pool maturity tests | 64f frozen mining/wallet proof, not dedicated99/100/101 or400000 boundary proof | Add genuine observational maturity fixture and compiled unchanged upstream subsidy vectors. No qualified mining seed/descriptor bridge or unified mining balance. |
| Q12 PARTIAL | wallet_session.py, bip39_spend_session.py, managed_wallet_checkpoint.py | test_q06_bip39_signer_bridge.py, test_q06_bip39_scanner_checkpoint.py;64f native/frozen spend/cancel/reopen | Full conflict/drop/reorg/crash-cut matrix remains PENDING; reuse irreversible monotonicity tests, no automatic replay/release. |
| Q13 PARTIAL | WSP codec.py/core.decode_address; cli_rpc.py and exact Core/pool decoder | test_q06_bip39_12.py public vectors; pool address-validation.test.js | Add119/120/121 namespace, exactHRP/type/checksum/case negatives and independent HD/BIP84 vector proof. Restricted Core validateaddress is not allowed by current RPC scope; do not bypass it. |
| Q14 PARTIAL | shared_regtest.py, shared_network_probe.py, bip39_reconciliation.py | test_shared_regtest.py, test_q06_bip39_reconciliation.py;64f same-host V1–V18 native/frozen PASS | Supplied audit's29448e5-only observation is stale:64f evidence exists in bundle-input/security-remediation-zcxicX/common-three-os-64f207c.json. Still no blanket Q14 PASS; deep mid-rescan reorg incomplete, physicalV19 BLOCKED. |
| Q15 EXISTS/PARTIAL | official_core_v013.py, release.py, windows_release_preflight.py, linux_official_core.py | test_official_core_v013_intake.py, test_windows_release_preflight.py;64f five package sets/23native jobsPASS,2SKIP | Supplied25PASS observation differs from final23PASS/2SKIP summary. Reauthenticate staged Mac binary; Win/Linux current candidate execution unavailable locally. No publisher identity from ad-hoc Fusion signing. |
| Q16 EXISTS/PARTIAL | custody.py, bip39_native_checkpoint.py, native storage/witness modules | test_q06_bip39_native_checkpoint.py and19Q05native/frozen cases at64f | Physical/independent harsh fault lab and cross-OS current new-source proof remain BLOCKED. Never touch existing keychain/anchors for this phase. |
| Q18 PARTIAL | history_pages.py, q04_miner_loop.py, WSP Scanner.sync | existing page/resource bounds and prior scoped miner-loop proofs | High-volume eligible-input/ECDH benchmark and deep mid-rescan reorg not qualified. No retroactive performance threshold or blanket stressPASS. |
| Q19 PARTIAL | docs/WAM_CORE_V013_COMPATIBILITY_AND_MIGRATION.md; wallet_recovery.py; core profile pin checks | tests/test_q05_wallet_checkpoint.py, test_official_core_v013_intake.py and native profile refusal proofs | Existing v011 profile conversion MIGRATION_PENDING, excluded. Reuse synthetic refusal tests only; no access to retained profiles or migratewallet. |
| Q20 EXISTS/PARTIAL | network_policy.py, rpc_scope.py, json_rpc.py, telemetry.py, gui errors | test_network_policy.py, test_gui_error_privacy.py;64f scoped native/frozen | Existing telemetry is in-process counters, not exported sink proof. Run reusable egress/redaction regressions; systematic per-platform crash/artifact forensic coverage remains PENDING. |

Full Q10–Q20 qualification is PENDING/BLOCKED, none accepted. New independently
safe probes are local contract evidence, not feature activation or Q handoff.
Windows/Linux cannot be executed natively on this Mac; no CI dispatch authorized.
The initial full source guard refused the newly supplied untracked ADR package
(`Q05_NATIVE_PROBE_CLEAN_SOURCE_REQUIRED`, retained diagnostic). Enumerate only
the three exact owner Markdown paths alongside the six retained audits, retaining
regular-file/owner/single-link/non-executable/stable-read checks and separate
hashes. Unknown Markdown and Python in that same directory must still refuse.
No folder-wide exemption, move, ignore or acceptance shortcut. A successful source
preflight is not a native/frozen build or acceptance receipt.

Q07/Q08/Q09/Q17: OWNER_DE_SCOPED future development; old IDs/cases/tests retained.
Q06 ledger remains0PASS/0FAIL/4PENDING/15STALE/5BLOCKED; G0PENDING,
G1–G5STALE,G6/G7BLOCKED,accepted=false. No new handoff/main integration authority.
