# Phase 3 — architecture inventory, Q10 recovery contract, Q14 reorg design (2026-11-07)

Status: engineering design record for Q10/Q11/Q13/Q14 on branch
`research/v1-compatibility-20261107`, starting HEAD `21f9902`. It grants no
runtime, merge, mainnet, signer, migration or acceptance authority. Results and
receipts are recorded in the ignored evidence directory and handoff, bound to
the exact final HEAD; this file holds only design facts and decisions.
Q06 `accepted=false`; G6/G7/V19 BLOCKED; Q07/Q08/Q09/Q17 OWNER_DE_SCOPED.

## 1. Architecture inventory (no refactor performed)

| Boundary | Modules (src/wam_regtest unless noted) | Shared runtime or REGTEST-only |
|---|---|---|
| Shared wallet engine | pinned WSP `wam_sp` (scanner, store, wallet, psbt, codec, core) at `ac55f134`; `wallet_session.WalletSession` | Shared runtime |
| BIP39/BIP32/BIP352 derivation | `bip39_12.py` (coin type 1, account 0, `m/352'/1'/0'/{1',0'}/0`), WSP `hd.py` | Shared runtime, REGTEST profile v1 only |
| Native custody | `custody.py`, `vault.py` (Q05), `bip39_seed_vault.py`, `bip39_native_checkpoint.py` (Q06), `managed_wallet_checkpoint.py`, Windows/Linux private storage, anchor/witness modules | Shared runtime |
| Transaction / reservation engine | WSP `wallet.py` (propose/mark_signed/broadcast/release_draft), `wallet_session.py`, `bip39_spend_session.py`, `bip39_scanner_checkpoint.require_irreversible_preserved` | Shared runtime |
| Scanner / checkpoint | WSP `scanner.py`/`store.py`, `bip39_scanner_checkpoint.py`, `bip39_native_checkpoint.py`, `bip39_reconciliation.py` (Shared-only) | Shared runtime |
| WAM Core supervisor | `core_supervisor.py`, `core_process.py`, `rpc_scope.py`, `cli_rpc.py`, `json_rpc.py`, `rpc_credentials.py`, `network_policy.py`, `official_core_v013.py` | Shared runtime |
| REGTEST-only test infrastructure | `q0*_probe.py`, `q05_*_scenario.py`, `q04_*`, `shared_network_probe.py`, `wallet_probe.py`, `security_probe.py`, `desktop_probe.py`, `ui_layout_probe.py`, `wsp_live.public_regtest_mining_address`, `scripts/probe_*.py` | REGTEST-only, but most probes ship inside the frozen package as `--ci-*` modes |
| GUI presentation | `bip39_owner_gui.py` (base window), `bip39_fusion_gui.py`, `fusion_ui.py`, `fusion_pages.py`, `bip39_backup_page.py`, `managed_gui.py`, `operational_gui.py`, `windows_read_gui.py`, `external_core_gui.py` | Shared runtime |

Duplication and coupling observed (reported only; no mass refactor):

1. Two native checkpoint writers with the same anchor/CAS idea: Q05
   `vault.Vault.save` and Q06 `bip39_native_checkpoint._publish_advanced_candidate`
   (via `_Q06NativeScannerVault`). Both are qualified separately; merging them
   would be a custody-format change and is out of scope.
2. `bip39_reconcile.py` (historical B2c read-only reconcile) has no runtime
   caller; only `tests/test_q06_bip39_reconcile.py` imports it. Its role is now
   covered by `bip39_reconciliation.py`. Removal needs an owner decision because
   historical evidence references it.
3. The reservation-map helper exists three times: `bip39_spend_session._reservation_map`,
   an inner `reservations()` in `advance_owned_candidate`, and `bip39_reconcile._reservations`.
4. RPC parameter validation is layered twice: `cli_rpc.validate` (finite owned
   allowlist) and `WalletCoreCli.call` (re-validates gettxout/testmempoolaccept/
   sendrawtransaction). Defensive but duplicated.
5. Test probes live in the runtime package and are reachable in the frozen app
   through `--ci-*` modes gated by environment variables. This couples product
   bytes to qualification code; every probe change re-baselines the frozen artifact.
6. Address namespace constants are spread: WSP `core.HRP='wamrtsp'`,
   `cli_rpc` regex `wamrt1…`, `recovery_metadata` `hrp`. They agree today and the
   Phase 3 tests pin them together.

## 2. Q11 mining compatibility facts

- Fusion's BIP352 wallet never holds coinbase: WSP `Scanner._block` skips every
  coinbase transaction, and BIP352 outputs require input keys a coinbase lacks.
  Immature-coinbase accounting therefore applies only to a mining account.
- No mining account is qualified. `wsp_live.public_regtest_mining_address` is a
  public fixture, not owner payout. Mining signer/descriptor authority stays
  BLOCKED pending a reviewed descriptor-custody design.
- Core-wallet spendability (`getbalances`/`listunspent`) is not in the finite
  RPC allowlist. Observing it requires an explicit owner decision to add
  read-only wallet methods for a disposable test wallet; it is not bypassed.
- Pinned chainparams: regtest halving interval 150, treasury 5% through height
  400000, coinbase maturity 100 (wallet formula `max(0, 101 - depth)`).
- Upstream discrepancy: the regtest chainparams comment says the treasury is
  the "testnet burn address (hash160 = 20 zero bytes)", but the literal
  `TQkMCz4r2oWuFjAu8mAeGYDMuz4BNkmofz` decodes (version 65) to hash160
  `a21b54367f4bd15b9b33e6e9e8b87c5b2fab5c16`, a real key. Report upstream; Fusion
  must not describe regtest treasury coins as provably unspendable.

## 3. Q13 address and derivation decisions

- Keep REGTEST profile `fusion-bip39-12-bip32-bip352-regtest-v1` byte-for-byte:
  coin type 1, account 0, scan `m/352'/1'/0'/1'/0`, spend `m/352'/1'/0'/0'/0`.
- WAM coin type 5718349, BIP84 `m/84'/5718349'/0'/0/0`, BIP86
  `m/86'/5718349'/0'/0/0` (reserved, never exposed) remain offline vectors only.
- Payment recipients are accepted only through WSP `Intent.validate` →
  `decode_address(code, 'wamrtsp')`: full Bech32m decode, exact HRP equality
  (never prefix), version 0, 66-byte payload of two valid points.
- `wamsp`/`twamsp`/`wamrtsp` remain PROPOSED, non-production until namespace approval.
- Wrong-network SegWit strings never reach Core: `cli_rpc.validate` admits only
  lowercase `wamrt1…` for `generatetoaddress`. Any Core RPC error, including a
  Core parser rejection, latches the owned RPC scope fault (`rpc_scope.route`);
  only explicit `reauthenticate_owned` of the same original process clears it.
  A probe that omitted this left its own disposable Core unable to stop.

## 4. Q10 recovery contract (ADR-Q10-01, PROPOSED)

The seven public fields (`recovery_metadata.validate_public_metadata`) are hints,
never authority.

| Field | Safe to integrate now? | Reason |
|---|---|---|
| format version | Yes (constant) | Pure identifier; no state. |
| network + genesis | Yes (constant) | Equals runtime `REGTEST_GENESIS`; mismatches refuse. |
| birthday height | Only as `1` | Runtime scans from 1 (`ScanAccount.birthday=1`). A larger hint could skip funds; it must never narrow the scan until authenticated against the original chain. |
| mining descriptors | No (`null`) | No qualified mining account; descriptor custody unreviewed. |
| BIP352 paths | Yes (constant) | Test proves they equal the real runtime derivation. |
| HRP | Yes (constant) | Equals WSP `HRP`. |
| label high-water mark | Only as `0` | Runtime allocates no labels (`labels=()`). |

Integration decision: no writer or profile/backup format change is made in
Phase 3. The validator stays detached; a later builder may emit the constants
above without touching custody.

Recovery layers are distinct and must not be conflated:

| Layer | What proves it | Status |
|---|---|---|
| Seed identity recovery | Same 12 words → same receive code (`bip39_12`) | Implemented |
| Same-chain balance/history | Fresh scanner from height 1 on the ORIGINAL authenticated chain reproduces TXIDs/atoms (`q06_same_chain_restore_probe`) | Implemented, native/frozen macOS only |
| Native state continuity | Native anchor generation + encrypted checkpoint on the same device | Implemented, same device only |
| Signed/uncertain reservation recovery | Requires the native checkpoint; a seed-only restore cannot know about prior irreversible reservations | Not available on a clean device |
| Authorization to spend | Explicit activation over verified native state | Never granted by seed or metadata |

Clean-device spending recovery threat model: an attacker or a stale backup can
present a seed with no record of a signed-but-unbroadcast payment. A clean
device would treat those inputs as free and could build a conflicting payment
(double-spend of the user's own intent, fee loss, or confusing history). A
fresh empty REGTEST chain could also make the wallet look restored with zero
history. Therefore clean-device recovery may restore identity and read-only
history on the original chain, but MUST NOT grant spending until either
(a) irreversible-state continuity is proven from authenticated native evidence,
or (b) an approved design defines an explicit operator-acknowledged
"no prior intents" declaration with conflict detection. Neither exists yet:
**design blocker, owner/reviewer approval required.**

## 5. Q14 scanner and reorg design facts

- WSP commits each block atomically after checking `previousblockhash` against
  the stored tip and re-checks `getblockhash` after each block, so a reorg
  during a scan raises `CHAIN_CHANGED_RETRY` with a consistent partial store;
  the next sync binary-searches the fork and rolls back (`max_reorg=10000`).
- `Store._rollback` removes coins/spends/blocks/history/mempool rows above the
  fork and never touches `reservations` or `labels`.
- Labels are key configuration, never derived from chain data, so a reorg
  cannot advance or rewind a label allocation. Fusion allocates none.
- Fusion native custody refuses any reorg crossing the anchored checkpoint tip
  (`_require_confirmed_descendant`); the session faults, runtime and
  reservations are retained, reopen activation is refused. Only Shared profiles
  have an explicit recovery (`reconcile_shared`: authenticated fresh rescan,
  stronger-chainwork proof, irreversible reservations preserved, native N+1).
- Isolated-profile reorg recovery is NOT implemented: **design blocker**.
- Orphaned payments are never rebroadcast automatically.

## 6. TX-03 / TX-05 compatibility (decisions required)

- TX-03 signed-not-broadcast: native state keeps the `signed` reservation across
  restart and reorg; the signed PSBT is retained only as create-only encrypted
  evidence. Resuming or abandoning such a payment needs an approved design
  (abandon requires proof the transaction can never confirm, e.g. a confirmed
  conflict of every input). Compatible with Q10: a seed-only recovery cannot see
  it, which is why clean-device spending stays blocked.
- TX-05 broadcast uncertainty: `uncertain` is persisted before RPC. After a
  reorg, an orphaned broadcast payment returns to the mempool or disappears;
  classification as dropped/conflicted must use chain evidence (confirmed
  conflicting spend), never mempool absence. Compatible with Q14 rollback
  because reservations survive rollback unchanged.
- A recovered unsigned draft alongside broadcast reservations stays refused.

Owner decisions requested:

1. Approve or reject read-only Core wallet RPC (`getbalances`) for disposable
   test wallets (Q11 Core-wallet spendability observation).
2. Mining descriptor custody design (Q11/Q10 field 4).
3. Clean-device spending recovery policy (Q10 threat model above).
4. Isolated-profile reorg recovery design (Q14).
5. TX-03 abandon/resume and TX-05 classification designs.
6. Disposition of unused `bip39_reconcile.py` and probe-in-package coupling.
