# Mandatory Issue45 Q-gate governance

Read this file, live [Issue45](https://github.com/Urriki1502/wam-privacy-wallet-regtest/issues/45),
the [owner's sequential protocol](https://github.com/Urriki1502/wam-privacy-wallet-regtest/issues/45#issuecomment-6379544993),
and **tests/acceptance/issue45.json** before touching code in every session.
That versioned JSON is the single authoritative Q01–Q20 ledger. Other historical
reports/PRs are evidence, not competing trackers or permission to advance.

1. **Only Q01 is ACTIVE.** Work Q01 → Q02 → … → Q20. Never activate Q+1 until
   the current Q is ACCEPTED, or the owner explicitly records an exception.
   Old phase-progress instructions and green component CI do not unlock a Q.
2. Inspect live main, PR ancestry, dirty work, exact-head checks and evidence.
   Hold `python3 scripts/engineering_lease.py --hold` throughout engineering;
   refuse overlap. Preserve other work, historical FAILs and frozen RC1.
3. Use one focused integration Draft PR based on verified current main for the
   ACTIVE Q. Inspect/selectively port only dependencies needed by that Q;
   never merge a historical multi-feature stack. Fix retries in the same PR.
4. Enumerate every mandatory positive/negative/platform/operator case in the
   ledger. Each case has exactly one PASS/FAIL/PENDING/BLOCKED/STALE, with exact
   source, Core trust/version/digests, WSP pin, OS, CI run/job, artifact hashes
   and timestamp when evidence exists. Missing tests and SKIP are PENDING.
5. Require G0 requirements, G1 source/security, G2 native, G3 final frozen,
   G4 functional/adversarial, G5 evidence integrity, G6 human/independent and
   G7 main integration as applicable. Justify any non-applicability using the
   canonical spec; never silently omit a gate. Source tests cannot replace
   genuine Core, final binaries, physical/operator or independent review.
6. Material source/test/dependency/Core/WSP/artifact changes make affected
   prior evidence STALE. Keep the original FAIL trail. Never weaken tests,
   fake Core/RPC acceptance, release reservations or reset anchors for green CI.
7. All candidate gates must qualify before requesting owner merge approval.
   **No automatic merge.** After explicit approval and merge, verify the exact
   merged main and delivered bytes. Only then mark ACCEPTED and unlock Q+1.
   A successful workflow is never Q acceptance. V1 remains HOLD otherwise.
8. External prerequisites require BLOCKED plus actor, exact missing evidence
   and next action. Continue only independent work within the SAME Q; do not
   switch to another Q. Do not assume quota reset, buy credits or create retries.

REGTEST/disposable funds only. Never use owner wallets, keys, anchors, miners,
mainnet, real funds or production deployment. Preserve native custody, rollback,
ownership, signing and uncertain-reservation gates. Do not modify upstream Core
or silently change qualified v0.1.11/WSP pins. Reviewed developer Linux Core is
not a signed official release. No force-push or direct main/RC1 modification.

Session reports MUST use the owner's fields: ACTIVE Q; Requirement coverage N/N;
Case results PASS/FAIL/PENDING/BLOCKED/STALE counts; G0–G7 actual statuses;
PR/HEAD SHA; macOS native/frozen; Windows native/frozen; Linux native/frozen;
Human/independent sign-off; Unresolved blockers; Exact next action; Q ACCEPTED
YES/NO. Report only the active Q and material blockers, no vague percentages.
