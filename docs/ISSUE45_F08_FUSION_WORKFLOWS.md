# F-08 — Fusion six-screen navigation and guided managed REGTEST setup

Issue #45 / Phase F / F-08 [P0], one Draft PR stacked directly on F-07.

## What is implemented

The existing Fusion **operational** wallet has six distinct navigable
pages: Overview, Receive (live BIP352 payment code + QR), History
(confirmed scanner rows/details), Send (separate exact review, Sign
and Broadcast approvals), Security (lock, encrypted backup, guarded
recovery and local disclosure), and Settings (theme, isolated node
privacy/identity, explicit sync). These are inherited unchanged;
no new private-key, signing, mining or network implementation is
added in F-08. The managed window instead has a separately locked
supervisor-facing workflow.

F-08 adds **Get Started** to the existing three read-only managed
navigation entries (Overview, Receive, History), using a scrollable,
responsive native Qt screen with explicit steps:

1. Check the supervisor-authenticated Core state and verified tip
   height. The button to start Core delegates to the original,
   ownership-guarded supervisor control and stays disabled unless
   that control already allows it.
2. Create a NEW BIP39 WSP wallet only when no vault exists, or
   verify the existing encrypted wallet. There is no automatic seed,
   wallet, signer, or balance adoption by the page itself.
3. Inspect a Core SQLite `.dat` or Fusion `.enc` **without
   importing**, converting Berkeley DB, changing the source or
   creating another wallet. Genuine SQLite .dat import remains a
   separate, explicitly unqualified workflow; the label must say
   `NO IMPORT`.
4. Read-only view, manually save encrypted checkpoint, or request
   the existing separately consented REGTEST Send window. Previewing
   the managed status does **not** unlock signing or broadcast.

Get Started controls delegate to pre-existing managed actions and
mirror only their actual `isEnabled()` policy after every status
and worker transition. No direct Core RPC, file read, seed, account
selection or transaction side effect occurs when the page is
constructed, refreshed or navigated. Unsafe/unverified states show
no verified balance or trustworthy Core height. Busy workers disable
all onboarding controls; disappearing supervisor trust revokes
create/verify/send regardless of last snapshot.

The prior managed topbar held more than ten long buttons. All
secondary actions now live in the **scrollable** onboarding screen;
Refresh, Start owned Core and Stop owned Core remain in the toolbar.
The first managed view defaults to Get Started. Read-only
Overview/Receive/History indices remain 0/1/2, while the fully
operational six-screen view retains its original indices and its
developer-only Mining Account restrictions. Managed original wallet
mining remains hidden/disabled.

## Validation and honest acceptance boundaries

- Native Qt UNIT: seven `test_f08_*` cases in `tests/test_fusion_managed_gui.py` check the
  welcome page and protected existing navigation, startup/worker/
  pending-state disablement, vault-create vs verification, original
  guarded action mirroring and hostile status rejection without
  contacting any Core or creating a key.
- Native runtime CI: Linux experimental REGTEST, macOS ARM64
  signed Core, Windows x64 signed Core, and BIP352 must all
  PASS at the **exact final PR SHA**. The existing GUI/Send/
  Backup/Recovery tests must continue passing.
- **NOT** accepted merely from green CI: appearance review
  on separate physical HiDPI screens; full user click-through
  of six screens on all three clean hosts; imported descriptor
  / native SQLite `.dat` integration (currently inspection
  only); external wallet selection; long-running sync; frozen
  distribution; 12/24-word create + cross-host restore; deep
  historical reorg and reliable unconfirmed silent incoming
  discovery. These remain independent operator qualification
  / Issue #45 P0 gates until evidenced.

No mainnet, imported production credentials, automatic migrations,
consensus changes, release signoff or merges are authorized.
