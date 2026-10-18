# Issue #45 — K-04 Core-native SQLite descriptor wallet .dat

**One K-04 Draft PR. This is an isolated REGTEST quarantine-restore slice, NOT permission to import personal wallet.dat into the managed Fusion Core or expose Core private descriptors to WSP.**

## Already implemented

- Source selected via a Qt file picker or single local `.dat` drag/drop is checked in a worker. GUI only displays sanitized `SQLite header accepted · network/provenance UNVERIFIED · NO IMPORT`. File selection never calls Core, loads a wallet or activates a signer.
- Read-only native fd and SQLite 100-byte header preflight; regular file only, exact `.dat` suffix, size 4 KiB–128 MiB, reject symlink/hardlink, live `-wal`/`-shm`/`-journal` and unsafe POSIX mode. Refuse Berkeley DB or arbitrary bytes. No database SQL queries, no descriptor parsing from the raw backup.
- Independent SHA256/size plus native inode/mtime/ctime checks before and after copying; create-only owner-private copy, no overwrite of original. Unexpected source mutation fails closed. A failed/partial private stage is not silently adopted/deleted.
- A separate disposable signed WAM Core v0.1.11 REGTEST fixture calls **actual Core RPC** `createwallet`, `backupwallet`, `restorewallet`, `getwalletinfo`, `listdescriptors(false)` on an isolated chain. The source/Core wallet is created using public disposable test fixture keys only. A second Core-native instance restores the exact staged SQLite bytes and must attest REGTEST genesis, descriptor wallet SQLite format and equal public-only descriptor identity. The source and staged bytes are hashed once again after Core restore.
- Core-supplied **public** descriptor identities are compared for exact duplicate and partial overlap. Any overlap is refused; never request private descriptors or decode Core keys from SQLite. Existing legacy WSP/BIP39 vault/Keychain/CredentialManager/root-witness accounts are not changed or adopted.

## Explicit boundaries & pending acceptance

- The production-style managed Core remains unchanged. No arbitrary external `wallet.dat`, same-UID miner DB, active wallet under WAL, Core mainnet, auto-sweep, password prompt, or loadwallet/restorewallet call from ordinary GUI/Scanner/Signer is enabled. GUI import is **inspection-only**; the restore path is exercised solely against two Core processes launched and owned by a disposable qualification fixture.
- The `.dat` SQLite header alone does **not** attest network/genesis, ownership, or descriptor provenance. Only the pinned genuine Core under an isolated REGTEST chain can validate that; a local `.dat` cannot be declared a WAM REGTEST wallet on header alone.
- Real encrypted Core wallet restore (including locked/private keys enabled), duplicate/partially-overlapping active target wallet registry, true managed-Core lifecycle-controlled adoption, and cross-platform **Mac→Windows→Linux** portability of the SAME signed fixture remain **PENDING** until evidence specifically proves them. Matching live-source and restored public identities is an isolated-quarantine proof, not an authorization to add them to the active account list.
- Code and test suite distinguish Core SQLite `.dat`, deprecated Berkeley DB wallet.dat, Fusion encrypted `.enc` and BIP39 mnemonic; these are not interchangeable. K-05 handles user guidance for BDB and K-06 account registry, K-08 portable clean-device recovery. Never modify/erase imported source.
- CI runs the actual native Core backup→restore fixture on macOS ARM64, Windows x64 and Linux x86_64 Qt native with the existing verified Core trust and independent root witness. Frozen GUI smoke, physical drag/drop usability, malicious SQLite native fuzzing and independent Codex/DEV review remain separate PENDING gates. A runner marked SKIP is not automatically a PASS.

**K-04 must not be declared fully P0-accepted merely from a passing quarantine fixture.** No real funds, mainnet, unattended import, auto-merge or altering owner's live miner.