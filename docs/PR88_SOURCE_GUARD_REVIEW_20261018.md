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

## Follow-up: Git replacement is also mutable metadata

**The first proposal below is superseded; do not integrate it unchanged.**
A further actual disposable-Git test confirms a sixth bypass on PR88 and on
the first candidate: `git replace` leaves `rev-parse HEAD` pinned while
`ls-tree PINNED_WSP_COMMIT` follows the replacement commit. The modified
scanner bytes then match the substituted tree. This requires no broken Git
object hashes, so the original Git-object-store caveat alone is insufficient.
No WSP import/Core/keys/anchors were used; fixtures and replacement refs were
restored. [PR88 result](evidence/issue45/PR88_08F4686_GIT_REPLACE_PROBE.json),
[first-candidate failure](evidence/issue45/PR88_08F4686_V1_GIT_REPLACE_PROBE.json),
[disposable reproducer](evidence/issue45/PR88_08F4686_GIT_REPLACE_REPRO.py).
The reproducer requires the same explicit disposable marker as the other tests.

[Revised exact-base proposal](evidence/issue45/PR88_08F4686_SOURCE_GUARD_V2.patch.txt)
adds `git --no-replace-objects` to the pinned tree query.
[V2 scope, exact hash and actual apply check](evidence/issue45/PR88_08F4686_V2_SCOPE_AND_APPLY.json).
Actual candidate guard SHA256:
`1f2066ef5343ed74927fbe9904eef7ea647aaf71df3b708303768f929a2ce387`.
[V2 primary](evidence/issue45/PR88_08F4686_V2_SOURCE_PROBE.json),
[V2 filesystem](evidence/issue45/PR88_08F4686_V2_EXTRA_PROBE.json),
[V2 replacement](evidence/issue45/PR88_08F4686_V2_GIT_REPLACE_PROBE.json):
**14/14 expected behavioral results** and all **12 existing exact88 contracts**
PASS, native Mac only. Actual exact-base apply/check/bytes also PASS.
This is still review-only, with the same bytecode/import-hook/host/import-race
and missing native3OS/Core/frozen qualification limits. No independent branch
or runtime has been changed. The original 11-case evidence below is preserved
as historical evidence; it was never a complete security qualification.

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

## Live refresh — exact PR88 HEAD `eb5033381c5c0b00af1e44d07815cd4592c46ab7`

Refreshed from GitHub at 2026-10-18 18:05 UTC. PR88 remains Draft, based on
`b32b8db7ae956bc6fca58c29e6f16696dac9a6b0`. Its ten exact-head check runs are
nine `SUCCESS` and `developer-core` `SKIPPED`; in particular the macOS signed
Core/WSP/Qt and frozen `.app/.dmg` checks are successful. The earlier macOS
`StopIteration` result above belongs to old head `08f4686`, not this head; the
current PR changes the ordering so dirty worktree refusal happens before the
pinned-tree subprocess call. Skipped developer-Core is not a pass.

I reran the public native-Mac disposable-clone probes against the isolated
snapshot of exact head `eb5033381c5c0b00af1e44d07815cd4592c46ab7`, guard SHA256
`0c6d650b90273f26553ac94fd3b67198d3a032e949daba757e449603d835f4fc`, WSP pin
`ac55f13423620252bdbf848c7e8a280c3b84721e`. Receipts are
[primary](evidence/issue45/PR88_EB503_SOURCE_PROBE.json),
[filesystem](evidence/issue45/PR88_EB503_EXTRA_PROBE.json), and
[Git replacement](evidence/issue45/PR88_EB503_GIT_REPLACE_PROBE.json). Clean
pinned controls pass; ordinary untracked `.py`/`.so` are rejected. **Six
adversarial checks are accepted and fail the required denial:** ignored `.so`,
tracked scanner modified under `assume-unchanged`, the same under
`skip-worktree`, tracked source hardlink, symlinked source parent, and modified
scanner substituted by `git replace`. Git replace demonstrates that pinning
`rev-parse HEAD` alone does not make the tree query immutable. These checks did
not import WSP, execute an injected module, start Core, or access keys/anchors;
they are source-guard evidence, not wallet E2E or proof of funds/signature loss.

The prior V2 patch and 14-case/12-contract results target old base `08f4686`;
they remain review-only historical evidence and are **not** a fix or
qualification for current `eb503338`. PR88's maintainer still owns K-07. The
appropriate next action is a coordinated correction on that existing PR, then
rerun exact-head adversarial tests and required native/Core/frozen gates across
platforms. No duplicate implementation, branch edit, or merge was performed.

## Exact-current-base correction candidate — `eb503338`

A fresh patch was generated from the exact PR88 `eb5033381c5c0b00af1e44d07815cd4592c46ab7` source and K-07 tests, not the earlier #67 checkout or obsolete `08f4686` base. It keeps the early dirty-worktree refusal, requests the literal pinned commit tree with `git --no-replace-objects`, binds each native Python file to the Git blob using existing stable-file helpers, rejects ignored executable/native files, symlinks and hardlinks, and checks the installed source path. It also checks standard `.pyc` caches without executing them: cache source must map to a pinned blob, header/version/metadata must match, and its code-object fields must equal recompilation of the pinned source. The proposed K-07 fixture uses real blob-form tree rows and asserts the pinned no-replacement command; it adds an altered-bytecode refusal case.

The exact-base proposal and receipts are
[patch](evidence/issue45/PR88_EB503_SOURCE_GUARD_CANDIDATE.patch),
[scope/results](evidence/issue45/PR88_EB503_CANDIDATE_REVIEW.json),
[primary probes](evidence/issue45/PR88_EB503_CANDIDATE_PRIMARY.json),
[filesystem probes](evidence/issue45/PR88_EB503_CANDIDATE_FILESYSTEM.json), and
[Git-replacement probe](evidence/issue45/PR88_EB503_CANDIDATE_GIT_REPLACE.json).
Candidate guard SHA256 is `89dc2b33f4300f23a25574fe13a2b9f82b42f43ba5efbed4e313c1297b475938`; patch SHA256 is `e6c3ba4426843213cb31db109f45f7c65e820593e2addfb4abf9d566a33dd5cd`. Patch dry-run/application to an isolated snapshot of exact `eb503338` succeeded and resulting bytes matched the tested candidate. Exact-PR88 K-07 source contracts: 12 PASS; exact-PR88 general contracts: 12 PASS. Native macOS disposable-clone probes deny all six previously accepted adversarial cases, while standard unmodified caches and clean controls pass. The altered `.pyc` test constructs bytes only; it never imports or executes them.

This remains a proposal, not an implementation or qualification: no independent branch was modified, no Core/WSP module was imported, and no real-Core E2E, frozen binary, Windows/Linux, same-user hostile process, import-hook, or validation-to-import race guarantee is claimed. The existing PR88 maintainer owns integration and must rerun all affected source, signed-Core, frozen and native platform gates on the resulting exact head. K-07 stays HOLD until then.
