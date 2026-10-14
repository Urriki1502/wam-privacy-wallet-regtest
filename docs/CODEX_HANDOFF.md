# Codex rolling engineering handoff — 2026-10-14

Always refresh GitHub, origin/main, open PRs and working tree before proceeding.
Preserve interim ChatGPT/user work. Official repository only:
`Urriki1502/wam-privacy-wallet-regtest`; no legacy/upstream modifications.

## Exact checkpoint identities

- Verified main: `b215dcd1431d3f34c19ad48d5fd64c1727a1fad0` (PR #12 merged).
- Network implementation: `feature/local-network-privacy-policy`,
  `8ede00c0f445f46d68fa5a6df613af43d93fe22f`.
- Current engineering branch: `security/independent-wallet-contract-gate`.
- Independent-gate implementation commit:
  `1c9919d233563d3280923704487248f27e55d08f`.
- This handoff-only commit follows that implementation; obtain the exact
  published PR HEAD with `gh pr list --state open --json number,headRefOid`.
  No application code is changed by the handoff itself.

## Completed / verified

PRs #1–#12 merged. PR #12: all three checks PASS at exact implementation HEAD;
source/package run 38529671510, canonical vectors 38529671523. 35 unit contracts,
28 BIP352 suites, genuine signed Core / WSP / SQLite / native Qt / recovery /
real reorg 1/12/100 and final packaged E2E PASS. Local bundle also PASS.

PR #12 enforces private exact REGTEST config before every CLI RPC, numeric
loopback, isolated CLI HOME/environment, and read-only Settings diagnostics.
It denies proxy/include/remote/fallback and clears stale verification. Explicit
local scan/broadcast role sharing; no anonymity or remote networking claim.

Independent gate code committed above: no wallet imports/runtime PASS flags;
AST critical contracts, crash-boundary and mutation evaluation, direct pinned
Core hashes, bundled WSP source comparison and original ICNS check. Local
source and existing qualified package evaluation PASS. New integrated CI and
fresh package evaluation are **PENDING**; do not merge until all checks pass.
No external reviewer or independent-builder approval is asserted.

## Next engineering actions

1. Publish/inspect the independent-gate PR, attach it, verify its source and
   package receipts, retained real-Core and vectors; merge only qualified HEAD.
2. Implement wallet-local selective disclosure using exact fields, same
   unlocked/authenticated session, fresh explicit consent, one-use/revoked
   authorization and redacted audit. Source facts from real local WSP history,
   not RPC-owned annotations. No cryptographic ownership-proof claim.
3. Adapt PayJoin sender safety to real WSP PSBTv2 bytes and authenticated local
   input ownership/UTXOs. Keep validation-only until BIP352 input changes,
   receiver finalization, protocol/transport/signing are qualified; do not
   expand transaction authority or network scope without explicit approval.
4. Continue orphan/power-loss and SQLite/memory lifecycle hardening. Refresh
   packaged Cocoa regression only when relevant new integration warrants it.

## Reproduction (macOS ARM64, private disposable REGTEST only)

```bash
source .venv/bin/activate
python -m unittest discover -s tests -v
python scripts/audit_wallet_security.py --root . --core core --output audit.json
QT_QPA_PLATFORM=offscreen python -m wam_regtest.cli smoke --core-dir core \
  --wsp-source-root wsp-upstream --confirm-disposable-regtest \
  --confirm-public-fixture-payment --confirm-real-gui-e2e \
  --confirm-security-e2e --confirm-wallet-e2e --report NEW-public-evidence.json
bash scripts/build_macos_bundle.sh
QT_QPA_PLATFORM=cocoa 'dist/WAM Privacy Wallet REGTEST.app/Contents/MacOS/WAM Privacy Wallet REGTEST' --ci-real-core-wallet-cocoa
```

Reports are create-only; choose a new path. Preserve exact WSP pin
`ac55f13423620252bdbf848c7e8a280c3b84721e` and independent official Core hashes.
Keep only two workflows; never replace genuine E2E with models/mocks.

## Source review and hard limits

Research pins and open Draft PR #53/#54 status: PRIVACY-FOUNDATIONS.md. Draft
source branches remain unmerged. No CORE-003, consensus or shielded imports.

No genuine external blocker currently. Operator Finder/Gatekeeper/passphrase
hands-on acceptance is still pending and distinct from automated MacBook QA.
Preview unnotarized; unlocked SQLite plaintext; memory clearing best effort;
Keychain loss/replacement fail closed; no Cross-Mac; 16 epochs; uncertain locks
may remain permanent; orphan needs deliberate diagnosis; hardware power loss,
same-UID malware/both-store rollback and production custody are unqualified.
No mainnet, real funds, personal keys or secrets in logs/artifacts/commits.
