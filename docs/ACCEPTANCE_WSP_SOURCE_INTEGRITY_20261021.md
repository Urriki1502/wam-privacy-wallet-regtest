# Acceptance finding A-01 — pinned WSP source bytes

Candidate reviewed: PR108 `f642682fa2731a5334facff8515b84d9605aa0dd`.
Requirement: K-07 / Q15 / R-05. Classification: **VERIFIED_P0_DEFECT**,
high source-integrity impact under the configured immutable-source boundary.

## Reproduction and impact

On native macOS, using a disposable clone of the actual pinned WSP commit
`ac55f13423620252bdbf848c7e8a280c3b84721e`, `_pinned_source` accepts:

- Changed tracked `scanner.py` hidden with either `assume-unchanged` or
  `skip-worktree` while Git status is clean and HEAD remains pinned.
- An inert ignored native extension inside `src/wam_sp`.
- Changed tracked source accompanied by a Git replacement commit; HEAD still
  reports the expected SHA while the tree query follows mutable replacement refs.

The guard checks status and Python filenames, but does not compare the bytes
that Python will import with the literal pinned commit's blobs. A local source
alteration can therefore pass the mandatory provenance gate. This reproduction
does **not** establish unauthorized signatures, funds loss, arbitrary remote
code execution, or a bypass of final frozen package checks. No injected WSP
module, Core process, wallet, key or native anchor was used by these probes.
Public receipts: `evidence/acceptance/A01_BASELINE_SOURCE.json` and
`evidence/acceptance/A01_BASELINE_GIT_REPLACE.json`.

PR88's latest head `eb5033381c5c0b00af1e44d07815cd4592c46ab7` has the same
vulnerable guard. Its newer commits synchronize the separate descriptor marker
fix, not this byte-verification proposal. This narrowly scoped remediation is
based on the current integrated candidate; PR88 and other active branches are
preserved. The implementation reuses the previously reviewed proposal recorded
on PR67; it does not fork WSP or replace any cryptography.

## Smallest safe remediation

Keep the pin, import-origin and fail-fast dirty-worktree checks. Read mode/blob
IDs from the literal pinned commit using `git --no-replace-objects ls-tree`.
Compare stable native file bytes through the existing build-provenance reader;
only an exact blob or CRLF-to-LF equivalent can match. Refuse linked/reparse
source directories, hardlinked source, unexpected native executable modules
and legacy loose bytecode. Bound file counts and total source bytes. Existing
frozen guard, Core pins, signer, reservations and OS anchors remain unchanged.

## Verification and limits

- Run `test_v1_k07*.py`: includes actual disposable Git/index/replacement refs,
  ignored modules and native filesystem links, plus existing refusal contracts.
- Run the native source suite and exact-source 3-OS Core/frozen workflows.
- Repeat the disposable actual-WSP probes: clean source must pass and every
  altered source/ignored extension/replacement case must be refused.
- Genuine Core/WSP receive, sign, broadcast, recovery and reorg tests stay
  mandatory. These source-guard tests cannot replace them.

Ordinary interpreter `__pycache__` remains permitted. Bytecode/import hooks,
compromised Git/OS, same-user malware and validation-to-import races are not
fully attested. Native/frozen/physical/independent review remain separate
qualification layers; this fix does not close all K-07 or Issue45 gates.
