# Acceptance rules — actual Core REGTEST only

- **CORE SMOKE PASS** requires a real official *signed and hashed* WAM v0.1.11 `wamd` launched in a new disposable REGTEST datadir with real localhost `wam-cli` RPC. Chain `regtest`, 101 blocks confirmed, peers = 0, process stopped and temp datadir removed. This is the first milestone, not a claim of WSP E2E.
- **WSP ALGORITHM PASS** requires all 28 canonical BIP352 vector suites against source pinned at `ac55f13423620252bdbf848c7e8a280c3b84721e` (no new arithmetic implementation).
- **REAL WSP RECEIVE E2E PASS** requires a *real on-chain transaction* with BIP352 output mined by WAM v0.1.11, actual WSP-1 Scanner.sync to SQLite, GUI shows real Receive/Balance/History, restart and reorg. Vectors alone do **not** satisfy it.
- **REAL WALLET SEND E2E PASS** requires user consent, review-gated and isolated REGTEST-only PSBT signing, Core `sendrawtransaction`, mined confirmation, and no mainnet permission. Merely finding `createpsbt` API does not imply PSBTv2 support.
- **PACKAGE PASS** requires a native Apple Silicon `.app` and `.dmg` booting on a MacBook with the above real Core and WSP flows. Signing/notarization is separate.
- The old repository is a library of reviewed code/tests, not an authorization to merge all 427 files. Port only the exact modules needed.
- Build is experimental and handles **no real user secrets, funds or mainnet**. The authenticated archive does not constitute a production-grade code-signing, launch or loader chain.
