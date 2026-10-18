# Issue #45 — K-05 Legacy Berkeley DB (BDB) safe refusal

**P0 refusal only. P1 migration is NOT implemented in Fusion.** DEV WAM confirmed that the published **v0.1.12 node** binaries provide a platform-dependent **Core-owned migratewallet RPC**; **Fusion must NOT write a converter**. One K-05 Draft PR based on green K-04 #85. The Fusion project's pinned v0.1.11 has not been equivalently qualified for this claim.

## Supported vs unsupported formats

| Input | Treatment |
|---|---|
| Core-native SQLite descriptor `.dat` | Unchanged K-04 strict native file/SQLite header/size/ACL/WAL checks; still only offline inspection in GUI and isolated genuine Core REGTEST quarantine restore in qualified CI |
| Legacy Berkeley DB `wallet.dat` (`.dat`) | Detect **candidate** Btree/Hash page magic at DB metadata offset 12 from at most 32 header bytes **before any K-04 private-file custody check**; refuse with `K05_BDB_DEPRECATED_UNSUPPORTED`. A ZIP/USB import mode 0644 must receive the correct BDB explanation. No load/conversion/key parsing |
| Unknown/malformed `.dat` | `K05_UNKNOWN_CORE_DAT_DENIED` or stricter K-04 custody/size/mutation refusal. Unknown is NEVER treated as safe or convertible |
| Fusion encrypted `.enc` | `K05_FUSION_ENCRYPTED_BACKUP_SEPARATE` before opening. Use the separately protected Fusion vault restore path, NOT Core restorewallet |
| BIP39 mnemonic (e.g. `.txt`) | `K05_MNEMONIC_TEXT_NOT_WALLET_DAT` **without opening or reading the file**; words/passphrase belong only in an approved BIP39 wallet recovery workflow, not Core file import |

The BDB header signature is only a **rejection heuristic**. A plausible magic does not prove Berkeley DB integrity, WAM provenance, a specific chain/network, ownership, encryption or compatibility. Unknown/non-matching files are refused just as strongly. Nothing in this PR attempts to discover private descriptors, decrypt seed material or inspect a BDB database.

## DEV WAM v0.1.12 binary compatibility (review of #86, 2026-10-18)

DEV WAM inspected **published binaries**, not merely upstream source:

| Actual WAM Core v0.1.12 binary | BDB support | Core-owned migration |
|---|---|---|
| `wamd` / `wam-cli` Windows x86_64 | Linked | `migratewallet` available |
| `wamd` / `wam-cli` macOS arm64 | Linked | `migratewallet` available |
| `wamd` / `wam-cli` Linux x86_64 | No BDB | Refuses with `Build does not support Berkeley DB database format` |
| `wam-qt` all three | No BDB | Not an available migration UI |

The Core `migratewallet` process takes a passphrase for encrypted wallets, creates an original `<wallet>-<timestamp>.legacy.bak` and may yield multiple descriptor wallets (including watch-only/solvable distinctions). **Do not copy, reimplement, or expose this RPC from Fusion.** Operators need an independently verified Core version, isolation, an original immutable backup and expert guidance; the plan remains deferred at the END of Issue #45. This table applies to **v0.1.12 nodes** only and cannot be automatically inferred for the pinned v0.1.11 used by Fusion.

**K-05 exact regression fixed from DEV review:** a regular old `wallet.dat` with mode `0644` used to hit `K04_SQLITE_SOURCE_CUSTODY_DENIED` before K-05's BDB classifier, yielding a generic GUI denial. The new dispatch first performs a bounded read-only 32-byte header check (regular, no symlink/hardlink, stable native fd) solely for negative classification, then applies **the exact unchanged K-04 custody restriction** before any positive SQLite acceptance/copy. For `0644` SQLite backups, the GUI reports the safe route: verify owner and use a trusted private copy with mode `0600`; no automatic chmod or permission repair.

## GUI and attack surface

The existing K-04 picker and single-file drag/drop now distinguish `.dat`, `.enc` and (accidentally selected) mnemonic text. The GUI emits only pre-defined non-secret categories. It explicitly says legacy BDB is deprecated/unsupported and that any future migration must follow approved upstream WAM Core guidance. The original source is untouched. File inspection cannot call Core, start/stop a miner, mutate datadir/SQLite, sign, import an account, broadcast or auto-sweep. Sensitive filenames, paths, raw errors, keys, descriptors, balances and mnemonic text are never inserted into status messages.

## Native security tests

- Headless portable negative tests: publicly constructed *dummy* 4/8KiB header fixtures for BDB Btree/Hash magics in both endiannesses, stable original SHA before/after, unknown `.dat`, live WAL marker, symlink, denied staging, zero conversion path and `.enc`/`.txt` never opened.
- Original K-04 genuine SQLite positive tests remain mandatory; failing a K-05 classifier must NEVER relax the existing SQLite rule or approve BDB.
- Native Qt tests on macOS/Windows/Linux exercise code-specific explanatory refusals and ensure no authenticated Core IPC, wallet adoption, signer or private seed display.
- Existing macOS/Windows/Linux native/frozen true-Core REGTEST wallet checks, WSP 28 canonical BIP352 vectors, custody and K-04 SQLite quarantine roundtrip remain gates for this HEAD.

## Deliberately pending

No BDB-to-SQLite conversion, no use of Berkeley DB tooling in Fusion, no WAM mainnet file reading, no real owner's miner wallet, no Core-native wallet load in the persistent managed Core, no recovered-account authority, and no manual deletion/overwrite. Genuine user-backed BDB fixtures are intentionally excluded from CI. P1 conversion needs a published, tested upstream path plus independent review and operator consent; physical cross-platform usability and DEV/Codex acceptance are separately PENDING.
