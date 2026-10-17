# Frozen source provenance guard — R03/R04 component

A correct Git HEAD alone cannot prove that PyInstaller consumed that source:
tracked files may be edited, assume-unchanged may hide edits, ignored modules can
be discovered, or the checkout may move during a long build. Preserve user work
and refuse packaging rather than silently label those bytes as the reviewed SHA.

All three existing builders now capture actual regular HEAD files independently
against Git blob identities, including staged/assume-unchanged negatives; refuse
source links/reparse metadata and extra importable modules (including ignored
files); fingerprint native content/file identity; recheck before frozen execution
and after its real E2E before publishing a public provenance receipt. Changes are
never deleted/reset. No extra workflow/job, executable Core pin or signing gate.

Windows source text CRLF may normalize ONLY to its exact Git blob. Original
pinned v0.1.11 source-contract C++ remains byte-exact and independently verified.
Binary assets cannot normalize. Each native receipt records its raw native-source
inventory digest. Head must be the actual checkout, or a direct parent of a
2-parent PR merge checkout; workflow_dispatch requires exact checkout equality.
Native source capture is bounded4096 files/128MiB per file/256MiB total.

BUILD_SOURCE_PROVENANCE.json is included in the existing package inventories and
SHA-256 manifests. It records source/checkout, file count and public inventory
digest, not host paths, inode IDs or private wallet/runtime data. Core, WSP and
native/frozen acceptance are still independent requirements. No wallet operation
uses this module; no per-RPC binary hash or Git subprocess is introduced.

This detects changed build-boundary source, NOT same-user host compromise,
mid-build malicious change/revert with spoofed metadata, dependency supply-chain
attestation, byte-for-byte reproducible binaries, publisher signing or notarization.
Clean-clone native CI remains required; all production/physical gates stay pending.

Supplemental disposable Git tests explicitly disable signing and hooks. They
exercise ordinary/staged/assume-unchanged edits, untracked/ignored modules,
source links, checkout changes and rewrite-to-original bytes, declared-head
mismatch, Windows text vs byte-pinned C++ rules. No synthetic blockchain PASS.
Source units181 total148PASS33platformSKIP; actual final three-OS frozen builds
remain pending until exact-head qualification. Core Update Manager deferred P1.
