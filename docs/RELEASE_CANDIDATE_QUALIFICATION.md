# WAM-Fusion-REGTEST-RC1 qualification

Candidate branch: integration/wam-fusion-regtest-v1-qualification.
Status before new exact-head execution: CODE_INTEGRATED; native/frozen
qualification PENDING. Predecessor PASS is baseline only. The final evidence
revision will identify the immutable qualified CODE SHA, all new native run URLs,
actual published artifacts/hashes/expiry and local MacBook proof. No main merge.

| Platform | Source E2E | Frozen E2E | Custody | Core provenance | Human acceptance |
| --- | --- | --- | --- | --- | --- |
| macOS ARM64 | PENDING new exact SHA | PENDING new exact SHA | Keychain, unchanged gates | Official signed v0.1.11, independent node/CLI pins | PENDING_OPERATOR; local automated Cocoa planned |
| Windows x64 | PENDING new exact SHA | PENDING new exact SHA and DPI | Credential Manager/protected NTFS | Official signed v0.1.11, independent node/CLI pins | PENDING_OPERATOR |
| Linux x86_64 | PENDING native Ubuntu/CLI/xcb | PENDING desktop + no-Qt | Private storage + independent root witness | Reviewed developer Core / stackRW; not official signed release | PHYSICAL_LINUX_ACCEPTANCE=PENDING_OPERATOR, owner has no authorized host |

Milestones are separate: CODE_INTEGRATED, NATIVE_CI_QUALIFIED,
FROZEN_BINARY_QUALIFIED, PHYSICAL_OR_HUMAN_ACCEPTED, DEV_WAM_REVIEWED.
Only actual observed evidence may advance them. READY FOR OWNER REGTEST TESTING
requires same-commit mandatory native gates and published qualified artifacts;
remaining operator-only steps must be disclosed. No FINAL, MAINNET or PRODUCTION.

Review: RC1_SECURITY_AND_DEPENDENCY_REVIEW.md. Practical operator procedure:
OWNER_REGTEST_ACCEPTANCE.md. DEV review draft: DEV_WAM_REVIEW_HANDOFF.md.
Portable backup stays design-only/not required; native platform bindings remain.

Rebuild: checkout the exact qualified code SHA and dispatch the four existing
workflows named in DEV_WAM_REVIEW_HANDOFF. Artifacts retain14days; never reuse a
new unchecked Core hash/system library or claim a build PASS because a predecessor
succeeded. RWE Linux release remains rejected. Build recipes/tools/closure must
be independently inspectable in per-platform and common RC manifests.
