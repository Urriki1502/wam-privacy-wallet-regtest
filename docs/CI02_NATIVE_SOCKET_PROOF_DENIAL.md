# CI02 — keep Linux native socket OS failures inside the denial contract

Parent: CI01 Draft115 `9cbd59d6a72a4a72e4de4dcece8e50fe1c1462ff`.
This is a separate evidence-backed availability/error-classification defect,
not an A06 correction or a reason to weaken native process/socket proof.

## Genuine failure

[Linux nativeQt job119561395128](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/39698325450/job/119561395128)
passed48native widget contracts, then genuine Core startup failed:

```
LINUX_E2E_FAILURE_KIND=PermissionError
LINUX_E2E_FAILURE_SITE=linux_headless.py:133>core.py:226>core_process.py:179>core_process.py:58
```

The failure occurs while enumerating `/proc/<owned-child>/fd`. Its raw OS
exception bypasses `_ready`'s existing CoreBindingError path, which separately
checks whether an actual exited child has a verified private bind-failure log.
The precise kernel/lifetime reason for that particular PermissionError is
unestablished; no access-policy or confidentiality bypass was demonstrated.

## Minimal correction and invariant

Convert OS errors from the Linux fd-directory and TCP-table inspection to
fixed `RPC_NATIVE_SOCKET_PROOF_DENIED`. A missing, inaccessible or uncertain
socket proof never becomes ownership. Kernel inode/endpoint/image checks are
unchanged, as are all existing startup budgets and retry restrictions.

An alive/unverified child still denies before constructing an authenticated
RPC client. Only the unchanged positive child-exit/private-bind-collision
classification permits an existing pre-wallet disposable startup retry. No
RPC response is fabricated, no ownership gate is skipped, and no wallet,
signature, reservation or broadcast retry is added.

## Verification

- Actual prior native Core failure above is preserved independently of A06.
- Supplemental baseline error-injection contract reproduces the raw exception.
  A separate local sandbox bind refusal is recorded as an environment limit,
  not this product defect.
- Local contracts after correction:8PASS/1nativeLinux-only SKIP; no Core PASS
  is inferred. Native Linux test creates an ordinary disposable non-dumpable
  Python child and exercises real `/proc` denial; this is kernel evidence,
  not blockchain E2E.
- Live-child negative test requires zero authenticated-client construction.
- Genuine Core startup/collision, native three-OS and final frozen regressions
  remain required on the exact new runtime SHA. Until actual jobs and artifacts
  are inspected they remain PENDING; mocks cannot qualify them.

PR114 and its A06 FAIL artifacts remain unchanged. A06 and aggregate release
gates must still FAIL. This correction does not fix Core persistence, reindex,
re-mine after a crash, change Core/WSP pins, alter root witness/ACL/Keychain,
delete owner data or authorize release. No upstream Core edits or auto-merge.
