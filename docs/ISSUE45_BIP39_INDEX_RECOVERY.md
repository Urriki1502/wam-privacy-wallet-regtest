# Q05 — typed BIP39 managed-wallet recovery qualification

Parent: Draft119, `3adb5a2fc7f2181dec8f3eb1de6cbe65be66a7e5`.
This is one acceptance-coverage task. No supervisor, recovery, RPC, crypto,
custody, approval or transaction state-machine policy changes.

The existing genuine `index_recovery_component` qualifies Core's original
101-block wallet and a legacy WSP32 native checkpoint. It does not create
BIP39 wallets or exchange managed IPC before closing the supervisor. Independent
Mac audit evidence covers those paths, but cannot qualify Windows or Linux.

`bip39_index_recovery_component` adds two fresh, isolated real-Core cases to the
existing native and final frozen acceptance invocations, including Linux
headless. The interactive application does not run these destructive tests.
Missing/failed proof is nonpassing. Existing no-reindex A06 and release aggregate
gates remain unchanged and mandatory; this component cannot waive their FAIL.

For each CSPRNG 12-word/no-passphrase and 24-word/test-passphrase wallet:

1. Create an owned private REGTEST Core and a separately typed BIP39 native vault
   through actual authenticated supervisor IPC. Independently derive the expected
   receive identity and compare all 64 seed bytes in memory, without emitting a
   seed, its digest, mnemonic, passphrase, password or private keys.
2. Confirm real BIP352 funding, produce a genuine pinned-WSP signature and retain
   its signed reservation. Fund a second independent coin and sign it. Drop the
   response only **after genuine Core accepts** its broadcast, producing a real
   uncertain reservation. Never retry the write or release either reservation.
3. Lock/close the wallet; capture original104 tip, full block-file hashes, native
   anchor, ciphertext hashes and scanner history. Verify native image ownership,
   kill/wait only that owned Core Popen, restart and observe index loss.
4. Close a supervisor that has served real IPC. Immediately invoke the unchanged
   explicit owned-only reindex with the exact original target. Require exact
   block bytes, protected profile and anchor/ciphertext to remain unchanged.
5. Restart again; load the original Core wallet if necessary, never recreate it.
   Reopen through real IPC and require original64-byte seed/type, wallet identity,
   receive identity, exact signed/uncertain rows and confirmed history. No reviewed
   or signed transaction object may reappear ready for automatic broadcast.

Mac tests select only a newly created disposable Keychain. Windows uses native
Credential Manager; Linux requires the existing independently provisioned root
witness and reviewed immutable developer Core policy. No helper is provisioned,
anchor reset or owner data accessed by this test. Unique test anchor records may
remain in native Windows/Linux stores; they are never reused as owner anchors.
Failed private fixtures are retained. Successful disposable directories/temporary
Mac Keychains are removed only after owned processes and IPC worker are reaped.

The probe is packaged by the existing collect-submodules build. Its frozen
receipt attests execution of these functions inside the actual final executable;
the independent frozen operator-entry test still checks the separate external
`--recover-owned-regtest-index` dispatch. Neither proves complete managed V1 GUI
startup/onboarding, cross-device recovery, physical usability or security review.

Original PR114 and all historical FAIL receipts remain immutable. In particular,
the separate1001-block partial-RPC observer still fails closed. A fresh diagnostic
at parent119 establishes `TimeoutError` while reading the Core HTTP response,
after warmup responses. It does not establish a consensus defect, justify an
automatic retry, qualify a partial-height interruption, or change the original
receipt. Recovery transport and per-request deadlines remain unchanged.

Exact-head CI and final artifact evidence must be inspected before claiming any
platform PASS. A source-only result never substitutes for a frozen result;
Windows/Linux and full V1 remain PENDING until their corresponding gates pass.
