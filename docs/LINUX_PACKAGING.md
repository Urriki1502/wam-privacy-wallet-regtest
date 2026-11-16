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

# Experimental Linux frozen wallet packages

Current packages require glibc >= 2.38 and Ubuntu 24.04. Ubuntu 22.04 is not supported. Details: `docs/LINUX_GLIBC_BASELINE.md`.

Two native Ubuntu24.04 x86_64 PyInstaller onedir tarballs: `wam-regtest-headless`
(no Qt/shiboken modules or libraries) and `wam-regtest-desktop` (existing Fusion
Qt/xcb). Each includes Python, the pinned WSP source corpus/native crypto, exact
qualified developer Core bytes and the owner's original PNG. No download or
system Python is used by the frozen wallet. These are not signed official Core
releases, general Linux-distribution packages, AppImages, or Final releases.

Core manifest approval remains independent: the operator supplies
`--manifest-sha256 e77a5745263b8fdbcffdb282af22800b6f7805f033c09f00738e997150a0f806`
and `--anchor-socket /absolute/admin-provisioned/anchor.sock` plus
`--confirm-experimental-developer-regtest`. Core/WSP paths are fixed to bundled
resources; external overrides are denied. The CLI accepts `--recover-backup`
for latest same-host anchored backup recovery. Desktop accepts `--gui`; launch
without arguments prompts for trust inputs and explicit disposable-chain consent.
Headless needs an interactive private terminal for secrets.

An administrator must independently review/provision the root witness. The
archive includes its public standalone source and policy for review only. The
app never invokes sudo, modifies services or installs privileged code. Preserving
that independent witness state is essential to same-host recovery/anti-rollback.

The exact system loader/libraries are verified against the approved Core
manifest, with sanitized Core child environments. Ubuntu24.04 dependencies
include binutils, libevent and libsqlite3; desktop also needs native xcb/EGL and
fonts. An upgraded/different library closure refuses rather than silently
trusting new bytes. Cross-distribution relocation and fd-to-loader binding remain
unqualified; no embedded library-trust weakening was added for PyInstaller.

Source headless and Qt real-Core jobs must pass before frozen jobs. Packaging
then invokes each FINAL bootloader with real disposable Core, native WSP signing,
independent root witness, SQLite and recovery gates. Headless retains reorg1/12/100,
stale signer/broadcast and uncertain reservation gates; desktop retains actual
native default-Cancel approvals/workers/payment/change/lock/recovery/fresh-chain
Qt gates. Negative tests remain supplementary. No package is published before
its executable acceptance succeeds.

`LINUX_PACKAGE_MANIFEST.json` binds source PR SHA, actual checkout/merge SHA,
WSP pin, independent Core manifest/hash pair, every regular bundle member,
relative internal symlinks, archive and E2E receipt SHA256, dependency versions
and explicit limitations. `SHA256SUMS.txt` covers all public top-level outputs.
The tarball preserves PyInstaller's relative internal library links; custody and
Core members remain regular single-link files. Builds are reproducible recipes
with recorded dependencies, not a claim of byte-identical toolchains/archives.

Artifacts are developer candidates. Native desktop/OS theme/operator testing,
root/whole-host rollback, power-loss durability, portable backup migration,
release signing and production custody remain unqualified.
