# Issue #45 / PR #56 — Official WAM v0.1.12 Signed Archive CI

Scope: a new isolated-host CI job verifies the **real official** WAM v0.1.12
signing key, SHA256SUMS.asc, SHA256SUMS, and WAM Core archive bytes for
macOS ARM64, Windows x64 and Linux x64. It builds on the offline preflight
in PR #55 and does **not** execute or install the Core binary.

## Security and evidence boundaries

- **Key trust:** the existing release verifier pins publisher fingerprint
  `4BD4 A8D3 AFD4 3F5C BCB5 00E2 3798 462F E00A DBA4` independently.
- **Network:** HTTPS only to fixed official release/tag endpoints or narrowly
  allowlisted GitHub asset redirect hosts. No ambient proxy, local auth or wallet.
- **Cryptography:** verify signed manifest via actual isolated GnuPG, then each
  downloaded archive SHA256 against the signed manifest; inspect only bounded
  platform-specific member names and sizes. No extraction or executable launch.
- **Evidence:** artifact `v012-signed-intake.json` includes source HEAD,
  signer, signed sums digest, platform archive digests and NOT-APPROVED flags.
- **Unit tests:** downloader negative tests use fake HTTP responses; those tests
  alone are NEVER evidence of signing or genuine archive authenticity.
- **Release metadata:** the `MANDATORY:` line is untrusted advisory metadata.
  The detached checksum signature does **not** sign the release body's text.
- **No change:** v0.1.11 qualification, current Core RPC, Sign/Broadcast, WSP,
  custody, GUI, RC1, upstream Core, and deferred Core Update Manager unchanged.

## Status

- PR #55 offline signed intake: component tests established; native/frozen
  and issue-integrated acceptance tracked separately.
- PR #56 official release cryptographic verification: PENDING until the
  **exact PR HEAD** GitHub Actions workflow completes and its artifact is read.
- Actual v0.1.12 executable pair pin, REGTEST BIP94/core-version profile,
  mining, maturity, BIP39, WSP, sign/broadcast/reorg, packaged/native and
  physical three-OS acceptance: **PENDING**; never infer R-02 PASS.
- An inaccessible download or verification failure is a red result,
  not a fallback to unchecked installation or v0.1.11 receipts.

Next: pinned v0.1.12 executable member hashes and real native REGTEST
compatibility tests on an isolated node without touching the user's miner.
