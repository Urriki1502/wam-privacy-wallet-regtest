# V1 scope and compatibility ADR — reconciled 2026-11-07

Status: local proposal implementing the owner's conversation-level scope decision;
not a Q transition, acceptance, deployment or network authorization.
Inspected baseline: `64f207c1c2bf804e7392816603487d877e7ef359`, existing
`feature/official-core-v013-three-platform-20261105`, Draft #141 base
`c61e3c5be4b8519dc6c4d9eb56d124fce84cf02d`. Live main is
`35553f674851282c6e107e02ba02ef2a7ac5ce64`; no remote mutation authorized.

The three original owner documents remain unchanged in
`WAM_Fusion_ADR_Gap_Audit_Codex_2026-11-06/`; intake hashes are in
`bundle-input/adr-q10-q20-20261107/intake.json` (local operational evidence).
The existing detached sidecar is historical and was not used or modified.

## Decisions and authority

- Q07/Q08/Q09/Q17 are OWNER_DE_SCOPED for future V1 development only. Preserve
  ORDER Q01–Q20, existing code, case states, identifiers, tests and evidence.
- Q10–Q16/Q18–Q20 form the future ordered roadmap. Q06 remains the sole active
  ledger Q, `accepted=false`. Prepare isolated offline contracts/probes only;
  no runtime feature activation, transition or new PR. A real authenticated owner
  decision URL is missing: governance activation remains PENDING. Do not invent it.
- `q_gate.validate` remains authoritative and unchanged. A separate draft scope
  evaluator must call it, retain all in-scope FAIL visibility and never grant
  acceptance/transition/release authority. Do not implement excluded imports via
  Q10/Q19. Q17 de-scoping does not remove Qt security/keyboard/DPI regressions.
- Keep G6/G7/V19 BLOCKED. No writes to retained wallet/anchor/reservation state,
  no descriptor custody bridge, old-format conversion or automatic repair.

## Verified source facts, before implementation

Core source is `b3fb899ddb1ceab7e9b3b12ccd034ad1b4be8186` and member/archive
pins are `src/wam_regtest/official_core_v013.py:17`. Its upstream repository is
an overlay on Bitcoin v28.1 (`scripts/fetch-upstream.sh`), not a complete Bitcoin
source tree. Missing base files are not evidence of missing Core functionality.
Core source facts still need exact signed-binary observables where applicable.

1. [SLIP-0044](https://github.com/satoshilabs/slips/blob/master/slip-0044.md)
   lists WAM 5718349, matching `WAM_BIP44_COIN_TYPE=0x57414D` in exact
   [wam-params.h](https://github.com/wamcoin-Project/wam-coin/blob/b3fb899ddb1ceab7e9b3b12ccd034ad1b4be8186/src/wam/wam-params.h).
   Test chains retain coin type 1. `bip39_12.py:PROFILE` and `_key` already
   preserve `m/352'/1'/account'/role'/0`; no profile rewrite is needed.
2. Pinned WSP `ac55f13423620252bdbf848c7e8a280c3b84721e` already supplies
   `hd.ExtendedPrivate`, `silent_key`, strict long `codec.decode` and
   `core.decode_address`. Its `core.HRP` is explicitly draft `wamrtsp`.
   WSP `profile.py` still documents its original v0.1.11 source; this is a
   historical static dependency fact, not proof of v0.1.13 incompatibility.
   Existing exact64f Core-backed compatibility evidence is separate.
3. [SLIP-0173](https://github.com/satoshilabs/slips/blob/master/slip-0173.md)
   registers SegWit `wam/twam/wamrt`, matching exact Core
   `src/wam/chainparams.cpp`. It does not establish WAM-SP namespace approval.
   `wamsp/twamsp/wamrtsp` remain proposed/offline, lengths119/120/121.
   Reuse full decoder/checksum/key-point validation; no startswith or 90-char cap.
4. Offline BIP84 mining and reserved BIP86 vectors must not become runtime wallets.
   `wsp_live.public_regtest_mining_address` uses globally known scalar31, not
   an owner's BIP84 account. Pool util/stratum accept SegWit; execute the exact
   pool decoder on public generated fixtures, not a live pool.
5. Maturity: distinguish Core wallet availability formula101-depth from
   next-block mempool/consensus acceptance. Probe depths99/100/101 rather than
   assert an untested equivalence. Do not add restricted wallet RPC methods just
   to obtain a favorable test. Unified mining-account spendability remains HOLD.
6. Treasury epochs use `(height-1)/200000` and inclusive sunset400000 in exact
   `src/wam/consensus/subsidy.cpp`. Compile unchanged upstream source with minimal
   type stubs for scoped deterministic vectors; this is not a rebuilt Core or
   executable proof at height400000. Never mine400k blocks or edit consensus.
7. `bip39_recovery_proof.verify_mnemonic_on_original_chain` already performs
   independent same-chain history/balance rescan and explicitly returns
   signer/broadcast false, clean-device recovery false, reservations-restored
   false. Seven public metadata fields cannot replace native custody/journals.

## Ordered local patches and phase boundaries

Phase0: this ADR and source reuse inventory first. Governance: tested draft-only
scope view, no ledger mutation. Phase1: public offline independent HD/codec
vectors and exact Core/pool compatibility probe. Phase2: public metadata
validation contract with no persistence/keys/descriptor import; maturity and
treasury boundary observations; reuse existing recovery/reservation negatives.
Later phases: reuse provenance/network/custody regression coverage; no new
scanner/transaction/anchor state machine without separately qualified design.
Stress thresholds must be declared before a measured final workload, not inferred
from a short probe. Cross-platform/frozen/physical work remains unexecuted for any
new candidate until actual matching proof; no push or Actions dispatch is allowed.
