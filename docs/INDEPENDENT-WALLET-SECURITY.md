# Independent internal wallet contract gate

Review input: wam-security V6/V7 at
`c9b1ce872c2b0b65276883d4e210b6a2f7c96467`. Adapt independent state exploration,
mutation sensitivity and explicit trust limits; import no consensus/pool/fabric
framework, reviewer policy exceptions or unsupported release attestations.

`scripts/audit_wallet_security.py` runs in a separate process using standard
library only. It never imports wallet code or trusts its E2E PASS flags. It
checks exact Sign/Broadcast review, live-input guard ordering, operation lease,
irreversible persistence before crypto/submission, fault retention, custody
close/delete calls, stale-writer comparison and create-only/fsync publication.
Independent crash-state exploration checks eight boundaries and detects four
mutations: early signature, early network, forgotten uncertainty and replayed
approval. A source-order mutation must also be rejected.

The evaluator independently pins both original Core member hashes. For final
bundles it compares every scanner source member with the actual clean pinned
WSP checkout, not the bundle's own manifest, and verifies the original ICNS.
It blocks before running a package if any measured contract fails. Source and
package receipts are uploaded in the existing real-Core workflow; no new job
or third workflow. Genuine functional E2E remains mandatory and separate.

**Limits:** these are internal automated contracts, not outside reviewer
approval, a second independent builder, full program refinement/formal proof,
or evidence that a compiled PYZ reproduces every source member. AST checks can
miss semantic bypasses; reviewed immutable source and genuine E2E complement
them. Abstract model results are not real blockchain acceptance. Runtime
loader/same-UID malware, hardware power loss, unlocked SQLite encryption and
production custody remain unqualified. Missing/failing evidence never implies
approval; this gate cannot authorize transactions or waive application gates.
