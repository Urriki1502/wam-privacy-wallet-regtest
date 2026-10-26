# Q03 persistent authenticated JSON-RPC qualification

This is the engineering review for existing Draft PR #131, not independent
security approval, physical Windows acceptance, a release or permission for Q04.
The canonical case states remain in tests/acceptance/issue45.json.

## Reproduced defects and focused repair

On the supplied source 7529e416, six new source contracts failed and one raised
an unredacted unexpected exception. Credential checks outside the cleanup path
left a client usable after drift and restoration; cookie headers reread mutable
bytes after attestation; a reply could be returned without a post-response
credential check; exhausted HTTP 503 retries retained a live session; HTTP
construction/read failures did not quarantine the owned scope. A separate lock
contract also reproduced that locking/closing a wallet retained its cached HTTP
client and Basic-auth header, including an already-locked close.

The repair pins the authenticated header once, attests before the first use and
before/after requests, closes and clears auth on every terminal transport error,
and permanently rejects restored credentials on that closed client. Only the
existing idempotent reads retry HTTP 503, at most three attempts with two bounded
backoffs; exhaustion revokes. HTTP failure quarantines the owned scope and
clears the cached genesis grant. Wallet faults, lock and close discard the
cached client. Unlock and Core reauthentication remain explicit; no anchor,
reservation, native custody, write allowlist, signing or broadcast replay rule
was relaxed. All write/broadcast methods remain on the signed CLI boundary.

The source review also examined process/socket ownership, loopback-only endpoint
selection, metadata identity versus full hashing, five-second trust-cache expiry,
response limits, duplicate JSON keys, error redaction and restart behavior.
Owned Popen/image/metadata checks remain on reused requests; new sockets are
proved to belong to the owned process before auth is sent. This is not hardened
protection against OS/same-user compromise or secure zeroization of immutable
Python strings. No independent signoff is inferred from this engineering review.

## Genuine-Core reuse proof

The existing native and final-frozen wallet fixtures now measure five ordinary
snapshots after warm-up. Receipts/logs must show zero CLI spawns, zero full Core
verification, zero new client/connection objects and zero actual new TCP
connections; actual HTTP request count must increase. Trust-cache refresh itself
may occur and must not trigger CLI or binary hashing. Both Linux desktop and
headless are measured separately. Mac final app offscreen and Cocoa paths emit
separate measurements. Windows default, 125% and 150% packaged receipts remain
distinct. A separate native Mac genuine Core-generated-cookie measurement is
published with source/checkout/Core/WSP identity. Supplemental local HTTP/mock
negative tests are never represented as positive genuine-Core E2E.

## Evidence reconciliation rules

The old 4/4 successful runs 40264463015 / 40264463096 / 40264463084 /
40264463118 are retained as pre-repair history. Their workflow source is
7529e4163b057fa0cf48247f207e67fadf1e51f2, while the actual PR merge checkout
in build receipts is 5caa87593ec9e3ceec147f9f2a3d77e5dc6edb6a. These are
different identities with equal trees; neither is silently substituted for the
other, or for the old runtime e21ee069. Runtime changes require fresh proof.

scripts/update_q03_ledger.py now requires explicit run IDs, runtime-source SHA
and downloaded artifacts. It reads live Actions run/job/artifact metadata,
requires successful jobs and nonexpired nonzero API digests, hashes each outer
artifact ZIP, checks build/manifest source and checkout trees, verifies every
included manifest member plus final payload hashes and the actual nested Core
pair, and requires genuine-Core repeated-read receipts. Mac internal Core
symlinks must resolve to the pinned regular Frameworks/core members. Missing,
tampered or unsupported evidence aborts before any ledger write. There is no
zero-placeholder fallback, current-HEAD guessing or shared macOS Core hash.

Core CLI/daemon pins, in that order:

| Platform | CLI SHA-256 | Daemon SHA-256 | Trust |
|---|---|---|---|
| macOS ARM64 | 81a031ebf9b3060b19061b29756d43bcd09b32ad778348b8c3d8321397076e82 | 7298de701e467eb28b4806cbcbe35edb393861b4b97117017fee4c1b194e3068 | official-signed-v0.1.11 Core |
| Windows x64 | 538a6d1b918b698ce76a949dda982fdda6776e33ba057efaac59b1af59e59d21 | 31717319535c5b784b2bed3b4d3c9a727f5c062e9534b4d27c59d2ffd04e95a1 | official-signed-v0.1.11 Core |
| Linux x86_64 | ada9dabd56d0859b9d64c0b20a05c33cb039b2573f75088443b45c35d5379652 | ccc9f0f1d299a1e98a49ff83859aa03e994e83e6ea4b7cd60c327eb1e0e8e4d6 | reviewed-developer-source-build |

Linux native/frozen jobs consume the pinned developer artifact from run
38697805476, approved manifest
e77a5745263b8fdbcffdb282af22800b6f7805f033c09f00738e997150a0f806;
a developer-core job in the same new workflow is separately identified and is
not substituted for that consumer provenance. WSP remains
ac55f13423620252bdbf848c7e8a280c3b84721e, Core v0.1.11 and REGTEST only.

## Acceptance boundaries

Q03 has 26 enumerated cases: 24 technical PASS and two external BLOCKED.
The verified runtime is 5af0899b9654ef109858f267b174e5e5a7062ab3; the
artifact-qualified workflow source is 21cb8bcc4be398ed4c4101cdac8d3d6751473d8a
and actual merge checkout is 45739d156bb7fc86e2a03ac7308e70abfa6886aa.
The source/checkout trees are equal. All four workflows succeeded:
macOS 40280168107, Windows 40280168097, Linux 40280168104 and WSP
40280168109. Native and final-frozen artifacts were independently reconciled
against live API ZIP digests, their inner manifests, final payloads and actual
Core bytes. Genuine reuse receipts show five cycles, 55 HTTP requests, zero CLI
spawns, zero full binary verifications and zero new TCP connections.

The ledger records that immutable evidence snapshot. Later documentation,
ledger and test-only descendants require fresh latest-HEAD CI and check-only
artifact verification; they never relabel the recorded source/checkout or
change the runtime identity. Supplemental local Q03 contracts: 42 PASS;
governance contracts: 10 PASS. The preceding complete local offscreen suite
ran 220 tests (187 PASS, 33 platform SKIP); the supplemental contracts and the
final snapshot are additionally covered by latest-HEAD hosted qualification.
G0–G5 PASS; G6 and G7 BLOCKED.
The physical Windows console/flicker/independent-GUI observation and independent
security review remain external BLOCKED. G7 must also remain BLOCKED until the
owner separately authorizes Q03 integration and exact-main postmerge proof is
available; Q02 focus authorization is not Q03 merge approval. Q03 remains the
only engineering-active Q, accepted=false, Draft/unmerged, with Q04 queued.
