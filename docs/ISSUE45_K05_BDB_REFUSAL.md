# Issue #45 — K-05 Legacy Berkeley DB (BDB) safe refusal

**P0 refusal only. P1 conversion is NOT implemented and is blocked on an explicitly supported WAM Core upstream migration contract, fixed independent vectors and DEV/security review.** One K-05 Draft PR based on green K-04 #85.

## Supported vs unsupported formats

| Input | Treatment |
|---|---|
| Core-native SQLite descriptor `.dat` | Unchanged K-04 strict native file/SQLite header/size/ACL/WAL checks; still only offline inspection in GUI and isolated genuine Core REGTEST quarantine restore in qualified CI |
| Legacy Berkeley DB `wallet.dat` (`.dat`) | Detect **candidate** Btree/Hash page magic at DB metadata offset 12 from at most 32 header bytes; refuse with `K05_BDB_DEPRECATED_UNSUPPORTED`. Do not load/convert/parse keys, descriptors, or migrations |
| Unknown/malformed `.dat` | `K05_UNKNOWN_CORE_DAT_DENIED` or stricter K-04 custody/size/mutation refusal. Unknown is NEVER treated as safe or convertible |
| Fusion encrypted `.enc` | `K05_FUSION_ENCRYPTED_BACKUP_SEPARATE` before opening. Use the separately protected Fusion vault restore path, NOT Core restorewallet |
| BIP39 mnemonic (e.g. `.txt`) | `K05_MNEMONIC_TEXT_NOT_WALLET_DAT` **without opening or reading the file**; words/passphrase belong only in an approved BIP39 wallet recovery workflow, not Core file import |

The BDB header signature is only a **rejection heuristic**. A plausible magic does not prove Berkeley DB integrity, WAM provenance, a specific chain/network, ownership, encryption or compatibility. Unknown/non-matching files are refused just as strongly. Nothing in this PR attempts to discover private descriptors, decrypt seed material or inspect a BDB database.

## GUI and attack surface

The existing K-04 picker and single-file drag/drop now distinguish `.dat`, `.enc` and (accidentally selected) mnemonic text. The GUI emits only pre-defined non-secret categories. It explicitly says legacy BDB is deprecated/unsupported and that any future migration must follow approved upstream WAM Core guidance. The original source is untouched. File inspection cannot call Core, start/stop a miner, mutate datadir/SQLite, sign, import an account, broadcast or auto-sweep. Sensitive filenames, paths, raw errors, keys, descriptors, balances and mnemonic text are never inserted into status messages.

## Native security tests

- Headless portable negative tests: publicly constructed *dummy* 4/8KiB header fixtures for BDB Btree/Hash magics in both endiannesses, stable original SHA before/after, unknown `.dat`, live WAL marker, symlink, denied staging, zero conversion path and `.enc`/`.txt` never opened.
- Original K-04 genuine SQLite positive tests remain mandatory; failing a K-05 classifier must NEVER relax the existing SQLite rule or approve BDB.
- Native Qt tests on macOS/Windows/Linux exercise code-specific explanatory refusals and ensure no authenticated Core IPC, wallet adoption, signer or private seed display.
- Existing macOS/Windows/Linux native/frozen true-Core REGTEST wallet checks, WSP 28 canonical BIP352 vectors, custody and K-04 SQLite quarantine roundtrip remain gates for this HEAD.

## Deliberately pending

No BDB-to-SQLite conversion, no use of Berkeley DB tooling in Fusion, no WAM mainnet file reading, no real owner's miner wallet, no Core-native wallet load in the persistent managed Core, no recovered-account authority, and no manual deletion/overwrite. Genuine user-backed BDB fixtures are intentionally excluded from CI. P1 conversion needs a published, tested upstream path plus independent review and operator consent; physical cross-platform usability and DEV/Codex acceptance are separately PENDING.
