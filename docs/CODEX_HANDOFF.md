# V1 REGTEST engineering handoff — 2026-10-14

This is the current operational handoff for **`Urriki1502/wam-privacy-wallet-regtest`**.
The former `Urriki1502/wam-privacy-wallet` is a **read-only reference**,
not the V1 implementation target. Before any work, refresh origin/main, open
PRs, current HEAD, required workflow runs and the local working tree. Preserve
uncommitted work. This checkpoint is valid only for the source revision below.

## Verified source and CI checkpoint

- Main HEAD checked: `50e1ea94df61b8400cbab3bffe0fbdd285c6b419`
  (merge PR #16, BIP352-aware fail-closed PayJoin sender review).
- On 2026-10-14, GitHub reported **no open PRs and no open issues** for this
  repository. Recheck rather than relying on this snapshot.
- Exact-main [REAL Core native workflow run](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38538104971):
  **SUCCESS**, including both source native WAM Core/WSP/Qt E2E and frozen
  macOS ARM64 `.app`/`.dmg` E2E jobs.
- Exact-main [28 canonical BIP352 vectors run](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38538105031):
  **SUCCESS**.
- Frozen application artifact (GitHub artifact ID `11880449638`):
  `WAM-Privacy-Wallet-REGTEST-macOS-ARM64-50e1ea94df61b8400cbab3bffe0fbdd285c6b419`.
  Its source is the successful REAL Core run above. A successful workflow
  and downloadable artifact do **not** establish hands-on Finder acceptance,
  notarization, independent security audit or production release.
- Pinned WSP-1 source remains
  `ac55f13423620252bdbf848c7e8a280c3b84721e`; use the real WSP
  implementation, do not introduce new BIP352 arithmetic.
- Official signed WAM Core **v0.1.11 macOS ARM64**, with original member hashes:
  `wamd = 7298de701e467eb28b4806cbcbe35edb393861b4b97117017fee4c1b194e3068`;
  `wam-cli = 81a031ebf9b3060b19061b29756d43bcd09b32ad778348b8c3d8321397076e82`.
  Release signer fingerprint:
  `4BD4A8D3AFD43F5CBCB500E23798462FE00ADBA4`.

## V1 delivered engineering scope (source + recorded acceptance)

- Real, isolated, signed WAM Core regtest; no peers, no mainnet or real funds.
- Actual WSP BIP352 receive, scanner, SQLite balance/history, restart and
  reorg tests at depths 1/12/100. Canonical upstream vectors remain mandatory.
- Review-gated Prepare, separate Sign approval, separate Broadcast, mined
  confirmation, actual sender change and conservative irreversible reservations.
- Encrypted snapshots and current same-Mac Keychain anchor, lock/unlock,
  cross-session recovery with stale-writer denial and no silent downgrade.
- Native macOS ARM64 Qt application, appearance support, original WAM artwork,
  final frozen executable tests, verified DMG creation and SHA256 manifest.
- Selected local disclosure with explicit consent and redacted evidence;
  local network privacy policy with no remote fallback.
- PR #16 added **canonical PSBTv2 PayJoin sender safety review only**:
  no BIP78/BIP77 transport, no signing/broadcast authority and an explicit
  `PJ_BIP352_REDERIVATION_UNQUALIFIED` denial for unqualified BIP352 PayJoin.
  BIP352 x PayJoin execution belongs to **V2**, not the V1 critical path.

## Next acceptance unit — do not mistake CI for a human Mac test

1. Download the exact-main frozen application artifact from run
   `38538104971`, compare its `SHA256SUMS.json` with the downloaded bytes,
   preserve the workflow/run/source SHA and original signed Core provenance.
2. On an actual Apple Silicon MacBook, test Finder launch, Gatekeeper
   right-click Open for the **ad-hoc / unnotarized** preview, Dock icon,
   Receive/Balance/History, prepare/review/sign/broadcast, confirmation,
   Lock/Unlock, latest encrypted backup and **same-Mac** recovery with fresh
   disposable test keys. Never use actual funds, personal wallets or seed data.
3. Repeat the **supplemental** native Cocoa appearance/real-Core acceptance
   (offscreen CI does not qualify native OS events):
   `QT_QPA_PLATFORM=cocoa 'dist/WAM Privacy Wallet REGTEST.app/Contents/MacOS/WAM Privacy Wallet REGTEST' --ci-real-core-wallet-cocoa`
   from a trusted, freshly qualified local build. Record actual logs/checks
   without private material. Do not label this PASS until executed.
4. If these steps expose a reproducible issue, make a small isolated fix,
   negative regression and exact-HEAD PR. Preserve both mandatory workflows,
   source and frozen app real-Core E2E, independent wallet security checks and
   28 BIP352 vectors. Do not weaken denial to make CI green.

## Remaining limitations and explicit hold rules

- `V1 REGTEST engineering CI PASS` is supported at the pinned HEAD;
  `V1 HUMAN OPERATOR ACCEPTED` is **NOT YET VERIFIED** here.
- Preview is ad-hoc signed, **not Developer ID notarized**. No production
  key custody, personal keys, mainnet, actual money, remote node, proxy,
  PayJoin transport or V2 BIP352×PayJoin.
- Unlocked SQLite is plaintext in an owner-only disposable runtime; memory
  erasure is best effort; same-UID malware, hardware power loss, full
  dual-store rollback, cross-Mac backup migration and uncertain/orphan
  reconciliation are not production-qualified.
- Never change WAM Core or frozen upstream WSP as a shortcut; no bulk import
  from old wallet/privacy/security repos. Do not merge unrelated pending or
  frozen branches from those repositories.
- No automatic deployment, no tagging as production, no reporting tests
  as executed unless the exact source revision and corresponding evidence
  were actually observed.

## Local verification pointers

Follow [README](../README.md), [WALLET-REGTEST](WALLET-REGTEST.md),
[ACCEPTANCE](ACCEPTANCE.md), [SECURITY-REUSE](SECURITY-REUSE.md),
[INDEPENDENT-WALLET-SECURITY](INDEPENDENT-WALLET-SECURITY.md) and
[PAYJOIN-SAFETY](PAYJOIN-SAFETY.md). The only GitHub workflows to preserve are
`.github/workflows/real-core-regtest.yml` and
`.github/workflows/bip352-vectors.yml`.

Historical note: the previous handoff stopped at PR #13 with disclosure
pending. It was superseded by the merged V1 work through PR #16 and must not
be used as a work queue.
