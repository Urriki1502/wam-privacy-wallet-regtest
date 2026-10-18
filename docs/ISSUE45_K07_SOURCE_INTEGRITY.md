# Issue #45 — K-07: Native source/frozen WSP custody parity (P0 review fix)

**One Draft PR stacked on K-06 #87.** Do not conflate this P0 integrity gate with K-09's explicit operator checkpoint-crash recovery or K-08 portable-restoration UX.

## DEV WAM verified defect

Earlier source `_pinned_source` accepted the pinned Git `HEAD` but called `git status --untracked-files=no`, so an extra untracked Python module in `src/wam_sp` could pass. Frozen `_verify_frozen_source` already enforced an exact manifest of all `*.py` files. A plugin/release change must not be able to load unreviewed wallet source.

## K-07 implementation

- Retain immutable WSP Git commit `ac55f13423620252bdbf848c7e8a280c3b84721e`, exact editable-import origin and existing frozen manifest verification.
- Upgrade source worktree inspection to **include untracked files**, and separately compare the exact set of Python files to Git `ls-tree -r --name-only -z HEAD -- src/wam_sp`. Deny ignored `*.py` even if `.gitignore` hides it from `git status`. Deny missing/extra or symlinked `.py` members, missing source base and dirty HEAD.
- Only `*.py` is compared for exact closure, aligning with frozen source behavior; harmless generated `__pycache__/*.pyc` is not treated as a Python source file. Existing clean content verification for tracked members stays Git-owned. Source tree closure still **does not qualify signed binaries**: platform custody, node/GUI binary signature and native vault anchor proof remain separate.
- Added targeted positive/negative unit contracts for untracked `.py`, ignored helper `.py`, dirty tracked code, symlinked source, missing tracked file, fake Git manifest, and pycache. These are **test fixtures**, not a synthetic pass for real Core.
- Existing pinned WSP 28/28 vectors, native Mac/Windows/Linux source and frozen GUI/headless Core E2E must all run on exact commit HEAD. No mainnet, foreign package or source, unsigned Core, debug fallback or new RPC writes.

## Critical checkpoint recovery deferred to K-09

DEV WAM also identified crash residue `snapshot-(N+1).enc` published before native anchor advancement. **Do not auto-delete** under K-07. A separately reviewed K-09 explicit owner recovery flow must prove genuine native custody+checkpoint and preserve signed/uncertain reservation semantics with crash simulation, and perform native protected quarantine/discard only with consent. No manual deletion instructions and no rollback-anchor bypass.

**Not yet release-approved:** physical OS tests, independent DEV/Codex acceptance and clean-machine backup restoring. Source guard is a necessary P0 integrity boundary, not a blanket wallet readiness claim.
