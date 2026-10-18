# Independent K-07 review — pinned source bytes and native file custody

18 October 2026 UTC. Reviewed independent Draft [PR88](https://github.com/Urriki1502/wam-privacy-wallet-regtest/pull/88)
at `08f46867aefe2572c4809a23e92de01cbf6ac439`, stacked on PR87
`b32b8db7ae956bc6fca58c29e6f16696dac9a6b0`. Its branch was not checked out,
modified, rebased, merged or pushed here. Existing PR67 contains public review
material only; this does not start another K-07 implementation or PR.

**Confirmed source-integrity defects block K-07 P0 acceptance.** Changing
`git status` to include untracked files fixes the original ordinary injection,
but neither Git status nor an exact set of Python filenames authenticates the
bytes that Python will import. Reproductions use a disposable no-hardlink clone
of the pinned WSP checkout, real Git/index flags and native Mac filesystem
operations. No WSP module, injected code, native extension, Core, key or anchor
was executed. These are source-guard tests, not blockchain E2E or proof of
unauthorized signing/funds loss. WSP upstream is unchanged.

## Exact-head findings and evidence

[Public summary and file hashes](evidence/issue45/PR88_08F4686_REVIEW_SUMMARY.json),
[seven primary cases](evidence/issue45/PR88_08F4686_SOURCE_GUARD_PROBE.json),
[four native filesystem cases](evidence/issue45/PR88_08F4686_EXTRA_SOURCE_PROBE.json).
Guard SHA256: `d6c011d3875d305cec7304a923760491e8a6838d792f4348c8c04cedf9bb818b`.

| Case | Actual PR88 result | Required result |
| --- | --- | --- |
| Clean checkout, restored checkout, normal interpreter caches (4 controls) | Allowed | Allowed |
| Ordinary untracked `.py` and inert `.so` (2 cases) | Denied | Denied |
| Modified tracked `scanner.py` with `assume-unchanged` | **Allowed — FAIL** | Denied |
| Modified tracked `scanner.py` with `skip-worktree` | **Allowed — FAIL** | Denied |
| Inert ignored `.so` inside `wam_sp` | **Allowed — FAIL** | Denied |
| Tracked source hardlinked outside package | **Allowed — FAIL** | Denied under native custody policy |
| Symlinked `src` parent, hidden using index flags | **Allowed — FAIL** | Denied under native custody policy |

1. **P1, tracked-byte authenticity:** [lines 104–131](https://github.com/Urriki1502/wam-privacy-wallet-regtest/blob/08f46867aefe2572c4809a23e92de01cbf6ac439/src/wam_regtest/wsp_live.py#L104)
   check status and names only. Git index flags conceal an altered tracked file;
   its name and HEAD remain correct. Compare actual native bytes to blob IDs
   from the literal pinned commit, independently of status/index metadata.
2. **P1, ignored executable closure:** [lines 122–130](https://github.com/Urriki1502/wam-privacy-wallet-regtest/blob/08f46867aefe2572c4809a23e92de01cbf6ac439/src/wam_regtest/wsp_live.py#L122)
   enumerate only `*.py`. Git ignores can hide additional native executable
   modules. The fixture is deliberately inert; no loader exploit is claimed.
3. **P1, file custody:** [lines 119–130](https://github.com/Urriki1502/wam-privacy-wallet-regtest/blob/08f46867aefe2572c4809a23e92de01cbf6ac439/src/wam_regtest/wsp_live.py#L119)
   reject leaf symlinks, but not a linked source parent or extra hardlink.
   Reuse the existing stable native file checks and validate directories.
4. **CI regression, confirmed:** [macOS run39130521611](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/39130521611/job/117684561407)
   fails before real E2E: 358 tests, one error, 34 platform skips. The existing
   dirty-scanner contract provides two subprocess results; the newly inserted
   tree query consumes a third before the dirty result is rejected, raising
   `StopIteration`. Preserve fail-fast dirty rejection; do not weaken the test.
   macOS frozen is SKIPPED, not PASS. Other jobs have separate exact-head status
   in the summary; Linux developer-Core SKIP is not qualification.

## Concrete proposal, isolated and not integrated

[Exact-base patch](evidence/issue45/PR88_08F4686_SOURCE_GUARD_PROPOSAL.patch.txt),
[scope/hashes](evidence/issue45/PR88_08F4686_PROPOSAL_SCOPE.json),
[apply verification](evidence/issue45/PR88_08F4686_PATCH_APPLY_CHECK.json).
Candidate guard SHA256:
`50ecd3c1e080c4bbe4256200d809aece38a46ee59fc6f9d1604f7663c4d06ff5`.

The review-only candidate retains the pin/origin/status gates and dirty early
exit, reads mode/blob identity from the pinned tree, reuses existing
`build_provenance._file`/`_blob` for bounded stable native-byte checking,
rejects linked/reparse directories, hardlinked source and extra executable
suffixes, and bounds the filesystem inventory. CRLF normalization can only
match the pinned blob; Windows behavior still needs native validation.
Standard `__pycache__` is permitted as before. This is **not** bytecode,
import-hook, Git-object-store or hostile same-user/OS attestation. Validation
followed by a later import also retains a race boundary; do not claim complete
K-07/R-05 or production closure from this proposal.

Actual native Mac results: [7 primary](evidence/issue45/PR88_08F4686_PROPOSAL_SOURCE_PROBE.json)
plus [4 filesystem cases](evidence/issue45/PR88_08F4686_PROPOSAL_EXTRA_PROBE.json)
all have the required result. The 12 existing exact-PR88 `test_contracts.py`
contracts also PASS, exit0, including the failing CI dirty-scanner case.
`git apply --check`, real application to an isolated exact snapshot and
byte-for-byte comparison with the tested candidate PASS. No independent
branch or PR67 runtime was patched. No proposal Core E2E, native Windows/Linux,
frozen application or physical PASS is claimed. Existing K-07 mock tree
fixtures must be updated for blob/mode output without relaxing assertions.

## Reproduce safely

Use Python 3.12 and the project's existing dependencies. Export PR88's `src`
into a new output directory. Clone the pinned WSP dependency with
`git clone --local --no-hardlinks --no-checkout`, then detach at
`ac55f13423620252bdbf848c7e8a280c3b84721e`. Never pass the installed dependency
or any owner wallet directory to the mutation scripts. Explicitly create
`.git/WAM_PUBLIC_DISPOSABLE_PROBE` in that **disposable clone**, containing
`DISPOSABLE_PUBLIC_SOURCE_PROBE_ONLY` followed by a newline. Both scripts refuse
without this marker and restore their fixture bytes/index flags/links in
`finally` blocks. Interrupted fixtures must be discarded, not adopted as trusted
dependencies. `PYTHONPATH` must list the disposable WSP `src` followed by the
isolated reviewed application `src`, then ordinary project dependencies.

Run [primary script](evidence/issue45/PR88_08F4686_SOURCE_REPRO.py) and
[filesystem script](evidence/issue45/PR88_08F4686_EXTRA_REPRO.py), each with three
arguments: absolute disposable clone, new JSON output, tested source SHA label.
Scripts record actual guard hashes, execute no `wam_sp` import, and let
unexpected exceptions fail instead of treating them as security denials.
Compare the receipts against the table; collection alone is not a PASS.
Normal caches in the filesystem fixture were generated by standard Python
`compileall` before the test. No native-extension payload is executable.

## Frozen comparison and disposition

Separately, the actual previously qualified PR67 `791b58d` Mac executable
SHA256 `65233367bde9f8a96ea7f219babe6e5911b4e2e7d5b1fdcc8647d501c62a223d`
from [artifact12130806102](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/39110707484/artifacts/12130806102)
was copied into a new disposable application. Actual `--check-bundle` allowed
the unaltered copy (exit0), denied an extra source `.py` (exit2,
`WSP_FROZEN_SOURCE_CLOSURE_DENIED`), and allowed the restored copy (exit0).
[Frozen receipt](evidence/issue45/PR67_791B58D_FROZEN_CLOSURE_PROBE.json).
No Core/Keychain was started, original app unchanged. This proves that one
existing frozen refusal, **not PR88 frozen qualification or full parity**.
791b58d's previous 10/10 CI, four inspected artifacts and local real-Core Cocoa
wallet E2E remain historical exact-SHA evidence, not qualification of this doc
commit or any independent stack.

**Next actor:** the existing independently active PR88 maintainer. Coordinate
the correction there, retain new K01–K06 features and all security gates, fix
the exact-head macOS failure, then run adversarial and genuine Core/WSP native
and frozen checks on all three OS. No duplicate K07 PR, silent rebase or merge.
The earlier [modal authority finding](PR81_MODAL_REVIEW_20261018.md) still needs
coordinated independent-stack integration. Full integrated P0/T/Q/V1 release
remains **HOLD**; physical Finder/OS appearance/retina/camera/sleep-wake and
authorized clean-host checks remain PENDING_OPERATOR. REGTEST/disposable only;
v0.1.12 candidate-only; Core Update Manager and BDB conversion remain deferred P1.
