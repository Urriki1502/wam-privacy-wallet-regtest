# A-04: verify native WSP source before execution, bypass mutable bytecode

Affected source: PR111 `b8d215fe591a09e6011459ba8908058c7175e652` and earlier. A-01 authenticates source-file bytes but explicitly permits ordinary interpreter caches. Independent actual-Git/CPython reproduction shows this limitation is material to native executable-code trust: a timestamp-valid `__pycache__/scanner.cpython-312.pyc` containing an extra harmless public assignment executes after `_pinned_source` accepts unchanged pinned `.py` files and clean Git. No Core, private keys, native anchors or transactions were accessed. See the public baseline receipt in `docs/evidence/acceptance/A04_BASELINE_CACHE.json`.

Severity: high conditional native WSP execution integrity when an external WSP cache is mutable; not a proven remote exploit or theft of owner keys. Merely documenting cache exclusion is insufficient to claim the native runtime actually executes only the pinned WSP implementation. Native scripts may also import WSP before their later explicit pin check.

## Small source-only execution boundary

The trusted wallet package installs one finder scoped strictly to `wam_sp` on native Python startup. A normal filesystem source loader is required. Before any WSP module body executes, reuse the original literal-pin/closure/hash checks, read stable native file bytes, compare their blob with the literal non-replaced pinned Git object and compile those bytes with Python's standard module flags. Existing bytecode is neither read, parsed, executed, deleted nor rewritten. No WSP/crypto implementation changes, dependency additions, native helper or signing bypass.

A WSP package already imported through an unverified loader is refused before entering wallet APIs; its past execution cannot be attested retroactively. Start a fresh qualified application process. Existing source/identity/custody/reservation gates remain. Arbitrary namespace/native/bytecode-only WSP replacement loaders are refused.

Frozen apps retain their existing separate authenticated build/source/PYZ closure; they do not acquire a system-Git dependency. The source import hook is skipped for actual frozen startup. Original pinned WSP code, signed Core binaries, native crypto wheels and exact transaction approvals are unchanged.

## Validation and residual trust

- Five real pinned-Git/subprocess regressions: clean import, timestamp-valid cache poison ignored without deletion, changed source refused before its harmless marker executes, unverified pre-import refusal, and bytecode-only/source-absent refusal.
- Local full native suite617 tests:582 PASS/35 platform skips, exit0. Original28 BIP352 vectors also PASS with the new guard installed before WSP imports.
- Independent disposable actual-WSP cache probe: clean and poisoned-cache cases both execute authentic source; public injected cache marker remains absent after the fix. The source and cache files are not modified by the guard.
- Exact-head macOS/Windows/Linux native Core, custody, Qt and final frozen regressions plus downloaded-artifact inspection are required; source tests are not Core E2E.

Trusted application/Python/stdlib, Git executable/configuration, dependency installation and OS remain assumptions. This is not a host-malware sandbox, attestation of arbitrary earlier Python execution, live module-attribute immutability or vendor signing of a modified frozen archive. The finder authenticates source bytes supplied to compilation; no claim that checks alone protect an already compromised interpreter. Independent security review remains pending. REGTEST/disposable only; no automatic merge or owner data/anchors/miners/upstream edits.
