# A06 — native fresh-write Core crash continuity gate

Parent: Draft113 `ac0273c8438204b40e86fdfb66deda49201f854b`.
This audit branch changes only acceptance scripts, CI wiring and this document.
The parent runtime, main, RC1, upstream Core and WSP remain unchanged.

## Reproduced acceptance failure

On the official signed macOS ARM64 v0.1.11 pair, an isolated fresh101-block
REGTEST chain reports height0 after confirmed owned Core SIGKILL and one
authenticated Start. Earlier independent native observations lasted30seconds.
The complete16MiB block file retains its SHA-256/inode, but genuine Core CLI
returns error−5/Block not found for the formerly known tip header. No file
deletion, new datadir, key theft or permanent block-file loss was established.
The exact upstream index/persistence/recovery cause remains unestablished.

A separate clean101-block-prefix/fresh103-block-tip funded Cocoa/WSP test
proves wallet rollback safety: orphaned balance/history removed, original
identity and both broadcast/signed reservations preserved, native anchor9→10,
new Prepare refused, no automatic broadcast. That scoped safety PASS does not
resolve the fresh-write Core continuity FAIL. A clean-stop positive control
is deliberately not substituted for the new gate.

## Native gate

`scripts/issue45_a06_fresh_crash.py`:

1. Captures/verifies clean source and declared source-head/checkout identity.
2. Uses existing exact Core/CLI provenance and WSP pin. Linux requires the
   existing independent native CI root witness and reviewed developer manifest.
3. Creates an entirely new protected disposable root, with native NTFS DACL
   on Windows. It never selects or attaches to an existing owner node/wallet.
4. Mines101public REGTEST blocks, records real tip/header and complete block
   file hashes. No wallet, secret key, native wallet anchor or signature.
5. Verifies native child image/RPC ownership, kills only its own Popen and
   waits for confirmed nonzero exit. No clean stop precedes the crash.
6. Sends the first authenticated Start without a status-refresh workaround.
   Samples the genuine restarted Core for up to10seconds, checking exact tip.
7. Records disk/RPC/identity observations without raw stderr, tokens, config,
   credentials, private paths, logs, mnemonics or wallet data.
8. Verifies owned-process shutdown before deleting only its fixture. An
   uncertain live child leaves the private datadir intact and receipt ERROR.
9. Rechecks source/Core provenance, publishes a create-only receipt, then
   exits1 for continuity FAIL or diagnostic ERROR. PASS requires cleanup too.

The bounded observation is not an assertion of permanent data loss. No
reindex, anchor reset, automatic resend/re-mining or version replacement is
attempted. The test does not establish a supported recovery contract.

## CI and evidence semantics

Existing macOS and Windows native jobs execute after their original signed
Core intake. Linux native Qt executes a separate interpreter using the same
already-provisioned CI witness; it does not rebind the parent Linux policy or
install a new helper. Every job publishes only its A06 JSON with `always()`;
a failed continuity receipt keeps the native job red. No existing assertion
is removed, relaxed, mocked or marked continue-on-error.

Changing Linux workflow publication also triggers that workflow's existing
broad immutable-Core build-input scope. The actual wallet job still selects
its previously reviewed pinned developer artifact; a fresh build job alone
does not change that selection or provide official signed Linux provenance.

Expected macOS continuity FAIL is not a regression fix or qualification PASS.
Windows/Linux outcomes are PENDING until actual exact-head receipts are
downloaded and inspected. Downstream jobs skipped after a native failure are
PENDING, never PASS. Parent113's successful native/frozen checks and published
artifacts retain their original exact source identity; this audit branch is
not a replacement qualified release candidate. Frozen/physical/DEV A06
acceptance remains separately pending. There is no upstream Core patch.

## Reproduce

Hold the common engineering lease first. On a clean source checkout with
the existing native dependencies and verified Core/WSP directories:

```sh
python scripts/issue45_a06_fresh_crash.py --core-dir core --wsp-source wsp-upstream --confirm-disposable-regtest --output a06-core-crash-evidence.json
```

For Linux additionally pass the exact reviewed developer manifest via
`--linux-developer-manifest` and the already authorized independent fixture
socket via `--linux-root-witness`. This script never provisions that service.
An occupied output path is refused. Do not delete owner data or protected
wallet state to rerun a diagnostic. Independent DEV review must establish the
exact-version persistence and safe recovery contract before a runtime fix.
