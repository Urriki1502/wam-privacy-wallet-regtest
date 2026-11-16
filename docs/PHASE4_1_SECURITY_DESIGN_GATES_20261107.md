# Phase 4.1 — packaging and unresolved custody design gates

Internal REGTEST engineering only. No mainnet, release, acceptance or new native
writer authority. Q06 accepted=false; G6/G7/V19 BLOCKED. Owner approval is still
required before adopting any revised Q18 budget.

The default macOS builder now builds two clearly separated executables. The
qualification-only directory retains the existing diagnostic binary and full
frozen probe suite; it is not distributed as the allowlisted wallet. The latter
uses production_entry, whose only argument is read-only --check-bundle; all
other argv are refused before resources/owners are opened, regardless of CI or
other environment flags. Build-time policy explicitly enumerates wallet modules,
excludes every nonmember (including CLI/alternate entries), and audits the actual
PYZ inventory. Developer tools and tests stay in the repository. Other-platform
runtime dependencies stay in the allowlist where current source imports them;
Windows/Linux builders have not been converted or natively qualified by this
macOS work. Their existing artifacts are not claimed production-hardened.

The separate qualification binary proves runtime regression paths with the same
source, not the final allowlisted executable. Normal-entry external GUI E2E of
the latter is mandatory before a complete local gate claim. No env flag can
re-enable its excluded probes. Artifact receipt explicitly says normal UI E2E
pending until actual separate evidence exists; no inheritance of acceptance.

Remaining gates, all design-only:

- Working SQLite is plaintext in a 0600 file inside a 0700 directory. BIP352
  tweaks/public outputs/history/reservations remain privacy-sensitive. Encryption
  requires reviewing database lifecycle, journal/WAL/temp files, key availability,
  crash consistency and native checkpoint binding. No new storage writer here.
- On fault, retained runtime preserves ambiguous transaction evidence. Destructive
  wiping could destroy irreversible reservation/recovery evidence; do not wipe
  or silently unlink it. SSD/APFS snapshots also preclude secure-erasure claims.
- ENOSPC/crash publication must fail closed. Reopening cannot select an older
  convenient checkpoint or reconstruct a native anchor. A recovery protocol
  needs original-owner proof, atomic publication/CAS, and crash-cut review.
- Signed-not-broadcast durable intent is not unsigned. Recovery requires binding
  signed bytes, approved recipient/amount/fee, original native identity and all
  irreversible reservations. No automatic signing/reconstruction/rebroadcast.
- Broadcast timeout or mempool absence proves neither write failure nor final
  transaction absence. Preserve uncertain state; distinguish canonical confirmed,
  conflicting, orphaned and merely unobserved outcomes without releasing locks.

Clipboard: clear the consumed unchanged snapshot after Paste, including failure,
but retain content republished during synchronous processing. Qt dataChanged
and text equality guard against overwriting newer observable content. QClipboard
has no cross-process atomic compare-and-clear primitive: a race after the last
comparison remains a platform limitation, and clipboard-history managers are
outside the deletion guarantee. The intentional verify_requested phrase signal
remains the existing explicit confirmation channel to the backend; Paste/cancel
must not emit it. No additional secret logs, errors or diagnostic signals.


Runtime graph correction: the existing explicit once-only REGTEST funding GUI
called fund_checkpoint_fixture from a developer scenario. The function body was
moved unchanged to regtest_funding, with a compatibility re-export from the
scenario and one backend import update. Its existing original-owner, new-profile,
RPC consent/attestation and once-only rules remain. No fault injection/scenario
entrypoint is carried into the production module. This preserves existing GUI
functionality while excluding the complete developer scenario.

Clipboard API cleanup errors must also be contained: a final read, clear or
signal disconnect error produces only the existing fixed validation error and
invalidates the input fields where the Qt widgets remain accessible. No blind
clear or retry follows an uncertain clipboard operation. This is an error
containment guarantee, not proof that clipboard content was erased when its
platform API failed. Destroyed widgets/Python copies/history remain subject
to the stated erasure limitations. Injected adapter tests are fault tests, not
a claim that a native macOS secret disclosure incident was observed.
