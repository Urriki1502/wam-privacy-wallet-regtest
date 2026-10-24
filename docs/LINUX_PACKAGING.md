# Experimental Linux frozen wallet packages

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
