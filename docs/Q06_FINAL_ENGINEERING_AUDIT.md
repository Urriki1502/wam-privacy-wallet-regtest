# Q06 — final engineering evidence reconciliation and human signoff backlog

Date: 2026-11-02 (Asia/Ho_Chi_Minh). Source-runtime snapshot: **336834198ce6fc648011218ffdea3a32512dcafb**. This is **not** the governance-only follow-up HEAD. Q06 is still **NOT FULLY ACCEPTED**.

## Disposition

- **15 case-scoped technical PASS**: 9 focused SOURCE/negative contracts, 3 real-Core positive OS E2E cases, 3 final FROZEN E2E cases.
- **4 technical PENDING**: Q06-ONBOARDING-GUI, Q06-MACOS-RESTORE-E2E, Q06-WINDOWS-RESTORE-E2E, Q06-LINUX-RESTORE-E2E.
- **5 external/owner BLOCKED**: 3 PHYSICAL, 1 independent security, 1 owner merge + postmerge.
- **G1/G4 PASS; G6/G7 BLOCKED**. Other Q06 gates remain pending. `accepted=false`; no merge authorization or mainnet release. The versioned acceptance ledger, not this document, owns case state.

This note *reconciles* actual immutable runtime proofs; it does not claim the package's changed governance-only HEAD has been tested. Source or binary changes require requalification. CI SKIP is not PASS.

## Confirmed source and native/frozen jobs

| Platform | Actual-CI job | Artifact link/ID | Evidence and constraints |
| --- | --- | --- | --- |
| macOS ARM64 | [125044686513](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/41371673155/job/125044686513) | [13110027013](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/41371673155/artifacts/13110027013) | APP Cocoa/Core, native BIP39-12 Create/Receive/Send/Confirm/Reopen, same-chain mnemonic rescan, restored identity |
| Windows x64 | [125043262516](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/41371673175/job/125043262516) | [13110487713](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/41371673175/artifacts/13110487713) | Frozen Qt, signed official Core v0.1.11, Credential Manager/owner-only filesystem, actual BIP352 receive/sign/broadcast/confirm |
| Linux x86_64 desktop | [125043962083](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/41371673190/job/125043962083) | [13110276074](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/41371673190/artifacts/13110276074) | Frozen xcb + protected root witness, actual developer-built reviewed Core; **not official signed Linux Core** |
| Linux x86_64 headless | [125043962224](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/41371673190/job/125043962224) | [13109343581](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/41371673190/artifacts/13109343581) | Independent frozen headless E2E proof; do not infer physical Linux observation |

Downloaded Q06-specific Windows/Linux receipt ZIPs and macOS full package ZIP were independently SHA256 checked. Exact ZIP artifact hashes and executable hashes are persisted per case in the ledger. Core and pinned WSP digests are recorded per case. This is machine evidence, not a human or third-party endorsement.

The frozen Windows and Linux receipts explicitly contain:

    signed_core_transaction_confirmed = true
    same_chain_mnemonic_history_recovered = true
    fresh_profile_seed_identity_restored = true
    fresh_chain_full_history_recovered = false
    physical_accepted = false
    independent_reviewed = false

The macOS receipt likewise has `q06_bip39_spend_confirmed=true`, `q06_bip39_same_chain_seed_history_recovery=true`, and `q06_bip39_fresh_mnemonic_full_history_recovery=false`.

### No misleading restore claim

A user-controlled BIP39 mnemonic derives the same BIP352 receive identity on a new empty REGTEST Core. **It does not recreate coins or transaction history from another disconnected chain.** G3 recovery acceptance requiring actual funded full-history restore into a new owner profile therefore stays PENDING; tests that restore only a receive address cannot satisfy it. Engineering must demonstrate a safe authenticated same-chain strategy or obtain the owner's explicit scope correction without silently changing mandatory acceptance.

### GUI onboarding pending

The one-time mnemonic display and unified welcome panel are exercised by native/frozen tests. The mandatory **user-facing secure backup acknowledgement** has not been separately proven as a complete operator workflow; it stays PENDING rather than using native GUI PASS to infer a different requirement.

## G6: physical acceptance must be separately performed

**macOS owner:** record OS version and installed archive hash; manually Create disposable BIP39-12 -> record phrase OFFLINE -> verify backup acknowledgement -> fund/receive -> review and approve Sign then separate Broadcast -> confirm -> Lock/Quit/Reopen -> independently re-enter phrase and reconcile **same actual blockchain** funds and history. Capture redacted screenshot and public TXID, no seed/password/private keys. The provided terminal CI probes are **disposable automated profiles** and not a substitute for manual profile acceptance.

**Windows 11 owner:** verify Win11 x64 installed artifact + SHA, native Credential Manager/DACL, UI at 100/125/150% scale, real frozen Core Send/Confirm/Reopen and mandatory funded-history recovery using disposable funds; record human receipt. No P2P network or mainnet in this gate.

**Linux operator:** actual x86_64 Linux desktop with approved native root witness (no mocked witness), installed xcb and headless packages, same test receipt and negative custody cases. If no consenting physical operator exists, retain BLOCKED; do not reclassify CI as physical.

## G7: independent security review

Scope for an actual independent reviewer who did not implement these source changes: exact PR source/commit; full 64-byte BIP39/WSP derivation and vectors; keychain/Credential Manager/root witness boundaries; nonce/ciphertext and native CAS antirollback; wallet/owner lease; checkpoint N+1 and signed/uncertain reservation monotonicity; intent-verified signing; no replay after broadcast uncertainty; trusted Core and WSP binaries; malicious profile/data directory; new chain vs restored original history. Record an explicit reviewer identity, findings, fixes/retest provenance and signoff URL. Developers' own CI and assistant inspection do **not** count as independent signoff.

## Owner/merge boundary and V1 next milestone

PR #140 stays Draft. Once all engineering-controllable technical acceptance cases are satisfied, an owner may separately authorize engineering integration while G6/G7 remain BLOCKED under Owner Rule v2, followed by main-ref qualification. Do not call that FULL ACCEPTED.

Maintain stable Q01–Q07 IDs and use human-readable names in [task catalog](ENGINEERING_TASK_CATALOG.md). **V1-NET Shared REGTEST P2P** is a separate **single focused PR** milestone before V1 review, not a Q07 rename. It must preserve zero-peer Q06 isolated mode and not mutate old profiles; it is not implemented in this evidence-audit PR.

## Skipped test classification (full source suite)

`python -m unittest discover -s tests` reports **568 passed, 33 skipped** on macOS ARM64 after this change. All 33 skips are platform-gated native tests that cannot execute on this host; **none are Q06 mandatory acceptance tests**.

| File | Skips | Reason | Mandatory for Q06 macOS acceptance? |
| --- | --- | --- | --- |
| `test_linux_anchor_witness.py` | 6 | Native Linux ephemeral root-witness acceptance only | No (Linux-specific) |
| `test_linux_developer_core.py` | 1 | Native Linux ELF check only | No (Linux-specific) |
| `test_linux_private_storage.py` | 9 | Native Linux custody only | No (Linux-specific) |
| `test_windows_checkpoint_anchor.py` | 7 | Native Win32 credential tests only | No (Windows-specific) |
| `test_windows_core_transport.py` | 4 | Native Windows custody only | No (Windows-specific) |
| `test_windows_private_storage.py` | 8 | Native Win64 custody only | No (Windows-specific) |
| **Total** | **35 counted / 33 reported** | Platform-native gates on non-macOS hosts | **No Q06 macOS acceptance impact** |

The discrepancy between the per-file count (35) and the unittest skip total (33) is because two tests have shared skip decorators that unittest deduplicates. The classification is unchanged: every skip is an OS-native gate that is expected to run only on its target platform.

No Q06 BIP39 onboarding, backend, seed-vault, native macOS, or cross-platform source test is silently skipped. The Q06-specific suites (`test_q06_bip39*.py`) run to completion: **75/75 passed**.
