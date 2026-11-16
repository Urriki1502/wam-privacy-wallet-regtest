# v0.1.13 candidate policy — 2026-11-05

The new candidate uses independently authenticated official signed v0.1.13
Core and a **separate** `linux_official_core.py` policy, with immutable archive
and member pins plus reviewed Ubuntu24.04 root-owned loader/library identity.
Current approved loader-manifest SHA256:
`4052c4a75dee853f5a27c2fb1869aee841a075ed8d6187b90a9d1c06a88cf3c2`.
The signature does not authorize wallet spending: independent root witness,
native ownership, private storage, leases, checkpoint CAS and consent remain
mandatory. Legacy CLI option names such as `--linux-developer-manifest` are
compatibility spellings; only the new official manifest is accepted by this
candidate's runtime. No old developer manifest silently becomes official.

Fresh disposable v0.1.13 profiles only; old profiles and historical developer
artifacts remain intact and fail closed. Frozen Ubuntu24.04/glibc >=2.38 remains
the supported baseline; Ubuntu22.04 UNSUPPORTED. Final qualification is still
PENDING until exact-source native/frozen receipts exist. See
[provenance](WAM_CORE_V013_PROVENANCE.md) and
[migration design](WAM_CORE_V013_COMPATIBILITY_AND_MIGRATION.md).

## Historical developer policy (preserved)

# Linux custody foundation and anchor HOLD

Native Linux x86_64 storage uses owner0700 directories, owner0600 regular
single-link files, descriptor-relative ancestor traversal and O_NOFOLLOW,
POSIX access/default ACL denial, bounded reads and before/after inode checks.
No permissions are repaired. A ciphertext stage is fsynced, create-only linked,
unlinked and its directory fsynced. A failed durability update may leave a
conservative final orphan; retry never replaces it. Unsupported ACL inspection,
unsafe ancestors, symlinks, hardlinks, FIFOs or modes deny. Local Linux
filesystem qualification is required; network filesystems and hardware
power-loss durability are unqualified. Same-UID/root malware is not covered.

WSP encryption remains the unchanged pinned WAMSP02 AES-GCM/scrypt envelope:
N32768/r8/p1,16-byte salt,12-byte nonce,32-byte derived key, authenticated
network/purpose and fresh randomness. These are the existing REGTEST research
parameters, not a new production password-hardening claim. Do not silently
increase/change their format or restore old backups under another platform.

LinuxWalletLease provides same-wallet flock contention across processes and
vault directories, exact-object/thread reentry and crash release. It provides
mutual exclusion, not monotonic freshness. No Qt, desktop keyring, shell
password argument, secret environment or new cryptographic implementation is
required by these primitives.

**These primitives alone do not enable Linux WalletSession or spending.** A software
file journal controlled by the wallet user, a passphrase alone or a lease cannot
qualify a trusted rollback anchor. require_trusted_anchor_for_spending refuses.
custody.py rejects Linux without the explicit approved Core/root-witness runtime
policy; macOS/Windows invariants remain unchanged.

Next reviewed policy candidate is an independent root-owned monotonic witness
with Unix SO_PEERCRED authentication, CAS generation/digest advancement,
create-only/fsync persistence and a lease held through signing/broadcast.
Only public generation/digest may reach the witness. No secret/keyring or
signature operation belongs in it. Without a qualified witness endpoint,
spending must fail closed. An optional TPM-backed policy can be evaluated
separately. No root service is installed or claimed qualified by this unit.

Native contracts test actual WSP encryption, filesystem/ACL behavior and
process leases. Fault-injected fsync contracts are supplementary, not power-loss
proof or real Core E2E. Headless/Qt wallet and portable recovery remain HOLD.
