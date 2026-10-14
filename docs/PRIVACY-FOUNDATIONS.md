# Reviewed privacy foundations — REGTEST only

This wallet reuses narrowly reviewed patterns, not upstream architecture or
source-repository approval. No source Draft/frozen branch is merged here.

| Research source | Reviewed commit | Decision |
| --- | --- | --- |
| wam-privacy main: network_privacy / payjoin_safety | db3d2dcaa540f1129d540101813b761167d33174 | Adapt fail-closed roles, no fallback and sender invariants to actual local Core/WSP interfaces. Normalized prototype models are not real PSBT acceptance. |
| wam-privacy PR #53 disclosure/policy | fad163821e1f2961afdfe7af966eca9ce53a58b2 (open Draft) | Review only; scope, one-use consent, revocation and redacted audit are useful patterns. No upstream qualification or ownership-proof claim. |
| wam-privacy PR #54 network policy | 403fb4889c97a680f3deabdb2a1c0db3fb6c65fd (open Draft) | Review only; no source merge. Tor/I2P/OHTTP labels cannot attest an actual route. |
| wam-silent-wallet privacy_service | 44e749a5c8fde82f672d0bc9d11e43af4e52c673 | Reuse read-only node diagnostics; no proxy setup, remote RPC or anonymity claim. |
| wam-security V6/V7 assurance | c9b1ce872c2b0b65276883d4e210b6a2f7c96467 | Review independent invariant/mutation gates and explicit unknown/red status. Do not import consensus, pools, supply monitoring or claim outside reviewer approval. |
| wam-silent-payments | ac55f13423620252bdbf848c7e8a280c3b84721e | Existing pinned PSBTv2/Signer/scanner retained without upstream modifications. |

## Implemented local network policy

Every actual CLI RPC first validates a bounded owner-private, regular 0600
single-link config. Require the exact disposable REGTEST profile; deny unknown
options, duplicate options, remote bind/connect, proxy/onion/include settings
and fallback before invoking the CLI. Explicit numeric loopback RPC and port
are passed to the verified CLI; its HOME is the private disposable datadir and
inherited proxy/environment configuration is excluded. Config credentials are
never returned in diagnostics or logs. Immutable/native memory clearing is
best effort, including temporary config parsing copies.

Scan and broadcast intentionally share one private local node. This is explicit
local role sharing; there is no public endpoint reuse, remote backend or
PayJoin directory. Settings can perform authenticated read-only real-Core
network diagnostics and display zero peers and no proxy/fallback. A rejected
configuration clears the verification text until a new successful check.

The full real-Core probe uses this same policy, tests the Settings action,
rejects an injected proxy option in its owned disposable config, restores the
fixture, then verifies the genuine node again. No mock/synthetic RPC qualifies
this gate. This provides isolation, not Tor/I2P/OHTTP or general anonymity.
