# Owner acceptance/UX audit delivery — 16 October 2026

Only Urriki1502/wam-privacy-wallet-regtest. Worktree work/owner-acceptance.
Preserved qualified RC1 code144d87700b87a241467172adfad3692b41e1d273 and
main50e1ea94df61b8400cbab3bffe0fbdd285c6b419; latest remote verification confirms
both unchanged. Legacy repository/upstream Core/original owner wallet and Keychain
were not modified. No automatic merge, release, production/mainnet or DEV message.

## Immutable code and documentation dependency

Proposed CODE427d3b0789d0b7e2da1f506c8dde860b5c6b4575 lives on
`audit/rc1-owner-acceptance-20261016`:
https://github.com/Urriki1502/wam-privacy-wallet-regtest/pull/38 (Draft).
It is stacked on PR37, docs/wam-fusion-regtest-rc1-evidence/D10fa54.
Current `docs/rc1-owner-acceptance-evidence-20261016` is a separate docs-only
branch stacked on PR38. Keep the code branch at427d3b0: final downloaded/native
artifacts refer to that exact source AND checkout, never the docs commit.
See [audit/matrix/downloads](OWNER_ACCEPTANCE_AUDIT.md) and
[evidence index](evidence/owner-audit/qualification/PUBLISHED_ARTIFACTS.json).

## Completed actual proof

-50 local real-Core/Cocoa owner checks: baseline46PASS/4FAIL; proposed50PASS.
 Four failed baseline checks are3UX defects: generic DENIED, false Not verified
 after local input refusal, and Sync erasing pending feedback (other/self).
 Each source version also passed actual Fresh selector/masked-password/live
 snapshot/close. Startup audit explicitly routes the REAL native anchor factory
 to a named test Keychain; default owner Keychain/Finder consent is untested.
-Receive/independently decoded rendered QR;14 invalid inputs; exact review;
 Cancel/Approve Sign and Broadcast; real mempool/confirmed-only balance; mined
 other-recipient and self-payment math; history; latest backup/Lock/Unlock/
 wrong-password/failed recovery;6native keyboard/passphrase cases; navigation,
 resize, fonts, themes, worker responsiveness and background sync.
-132 contract tests run:99PASS,33SKIPPED,0FAIL; independent wallet auditor PASS.
 Native security regression retains reorg1/12/100, OS lease/contention/kill,
 interrupted publication, stale storage, wrong/missing anchor, recovery keys/
 reservations and genuinely lost accepted Core broadcast response. The report
 distinguishes source receipts and frozen entrypoints, never mocks as real E2E.
-Additional actual Mac payment-stale regression PASS: same-wallet separate vault
 writer advances native test-Keychain anchor, refusal before signer/RPC, positive
 native signing control, no mempool submission, irreversible signed reservations.
 This source-only audit reuses the Windows helper logic with named native Mac
 Keychain routing. Original Mac cross-session receipt's two false stale-payment
 fields were NOT treated as PASS; separate MAC_STALE_PAYMENT_RECEIPT.json proves
 these cases. Initial supplemental harness attempts are not acceptance results.
-All8 SAME-CODE workflow_dispatch runs SUCCESS:
 vectors38843576037, macOS38843580133, Windows38843585494,
 Linux38843589482, Win-preflight38843594122, Win-Core38843598553,
 Win-receive38843604563, Win-readQt38843609070.
 Linux repeated developer-Core job actually SUCCESS. PR38 has9SUCCESS +1
 conditional developer-core SKIPPED; do not relabel that skip PASS.
-All4 downloaded packages: manifests/all public hashes/archive members/independent
 Core pair/WSP33sourcefiles/original brand verified. Windows PE AMD64/DPI125/150;
 Linux ELF/Core/bootloader RW stack, reviewed root helper and no-Qt headless.
-New Mac app downloaded from artifact12022821744 actually ran Cocoa on Mac14,9,
 macOS27.0.1 ARM64, 04:46:49–04:47:46UTC16October. Full frozen real Core/Qt/
 security/recovery/reorg/appearance PASS, exit0, DMG VALID, strict deep ad-hoc
 signature valid, official Core bytes unchanged, no owned audit process survives.
 Windows/Linux native executable PASS is RUNNER evidence, not physical hardware.

Published exact427d3b0 artifact IDs: Mac12022821744, Windows12023245350,
Linux desktop12022432490/headless12022796655. Expire30October2026. Artifact
links/payload SHA256/Core SHA256/expiry in qualification/PUBLISHED_ARTIFACTS.json.
macOS/Windows official signed v0.1.11; Linux explicitly reviewed developer build,
not official-signed qualification. Official Linux executable-stack gate remains
closed. Rebuild success never silently replaces independently approved hashes.
WSPac55f13423620252bdbf848c7e8a280c3b84721e unchanged. Runtime crypto/storage/
RPC/lease/reservation policies unchanged; proposed production changes only GUI
safe public error mapping/Last verified/last locally submitted confirmation cue.

## Remaining disposition

Keep Draft PR38 unmerged for owner review. Technical disposable REGTEST native/
frozen qualification is complete; no Final/production claim. Remaining
PENDING_OPERATOR: human legibility/comfort/focus, actual screen/Retina/external
monitor/camera QR, Finder/Gatekeeper/OS approval, real OS-wide appearance changes,
Windows10/11 hardware and physical Linux desktop/headless. Owner already reported
no authorized physical Linux host; do not ask again or substitute Xvfb as physical.
Linux OS Auto Unknown stays PENDING. Unlocked plaintext SQLite, memory best effort,
16epochs, platform-bound recovery, root/whole-anchor/profile rollback, power-loss
and loader-binding limitations remain explicit. PayJoin execution remains V2 HOLD.

The owner's pre-existing app/Core5770/5772 were observed initially; exact-path
read-only AX selection timed out. No owner window operation was performed. Later
read-only process inspection found them absent; cause not observed. Do not claim
to know the owner's exact input/failure or that engineering closed that session.
No existing anchor was deleted or signed/uncertain reservation released.

## Lease, resume log and usage history

Common-Git engineering lease session9827/PID6842 was held throughout engineering.
Release it after the final pushed checkpoint; actual release is recorded in the
separate local outputs/owner-acceptance-20261016/RESUME_LOG.txt. A future engineer
must inspect active threads/processes and acquire its own exclusive lease using
`python3 scripts/engineering_lease.py --hold`; exit73 means refuse concurrent
engineering. Never infer authority from an old recorded PID/session.

Earlier automatic approval review rejected git add because account usage was
exhausted; it explicitly did not execute the action and did not determine it
unsafe. Only docs edits preceding git add ran. After the owner's continuation,
actual usage refresh04:45:59UTC reported ordinaryUsageAllowed=true, primary1%,
weekly47%; engineering resumed without buying/resetting credits or assuming a
reset. Existing single-continuation automation remains PAUSED: no recurring retry,
scheduler update, credit reset or charge was created.

Full public logs/downloads/isolated screenshots and executed drivers are in
outputs/owner-acceptance-20261016. Only redacted public receipts/screenshots belong
in Git. No private keys/passphrases/RPC credentials/DB/backups/Keychains. First
partial audit attempts corrected harness framing/pixels, not wallet safety gates;
only completed receipts count. Next: review proposed GUI wording/readiness using
the evidence, then perform only remaining physical observations on disposable data.
