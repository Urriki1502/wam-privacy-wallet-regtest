# Issue #45 R-05 — Public artifact privacy guard (first security slice)

One Draft PR stacked on R-04 #105 exact green commit
`11425c75bbcef8fec5463aa71b76df34811f6e85`.
REGTEST only. This is a **defense-in-depth publication check**, not an
independent security audit or approval of final V1.

## Existing work deliberately reused

The existing `scripts/audit_wallet_security.py`, native Core/WSP
functional integration, OS-native credential guards and fail-closed
sign/broadcast recovery contracts remain unchanged. The Mac source,
Core and frozen audits, Windows native private custody, Linux owner/witness
and BIP352 native suites continue to execute.

## Implementation

`r05_public_privacy.py` inspects the final **public output directory** after
the existing R-04 complete inventory and SHA-256 check but before builder
success/publication. It uses the strict R-04 real-file tree walker and
rejects output files named like private Core wallet/config/credentials,
encrypted databases, OS Keychain data, temporary secrets and backups.

For UTF-8 public JSON, TXT, Markdown, LOG, YAML, CSV and configuration
surfaces, the scanner checks bounded bytes for high-confidence plaintext
credentials: RPC password assignments, named JSON secret/seed/private
key values, exported private-key headers, Basic authorization headers
and serialized extended private keys. The validation emits **fixed reason
codes only** and does not echo filenames, credentials, private paths, seeds
or invalid data. Read-only; no mutations and no wallet/runtime requests.

Integrated into existing macOS/Windows/Linux native bundle builders after
`audit_candidate_output`. The platform-independent unit suite tests
positive public outputs, nested private paths, malformed content and
synthetic leak markers; tests never use genuine owner secrets.

## Limits: pending mandatory R-05 P0

- Scan does **not** inspect encrypted archives, ZIP/tar/DMG binary payloads,
  executable bytes, screenshots, crash dumps, OS process logs or network
  traffic and DNS; it cannot prove absence of secrets in those channels.
- Literal-pattern filtering cannot detect all encodings, unknown wallet key
  formats or indirect secret disclosures. The scanner cannot attest that the
  publisher/provenance itself is trusted or that no compromised runner exists.
- **Independent** security review of `wsp_live.py`,
  `encrypted_storage.py`, `payjoin_safety.py`, signer, JSON-RPC, custody,
  backup/recovery and migration, including malformation/mutation/crash tests
  on exact final three-OS frozen binaries, is **PENDING**.
- Physical/DEV external review, vulnerability remediation and final
  REGTEST production-equivalent acceptance are separate authorization
  gates. No authentic node, signing permission, mainnet or install
  permission is obtained through this checker.

Do not change Issue #45 registry statuses to PASS on source-only tests.
The result `R05_PUBLIC_TEXT_AND_PATH_AUDIT_PASS` is scoped to public
output files inspected, nothing else.
