# Experimental Linux developer Core policy v1

User-authorized scope15 October2026: source-built genuine WAM on native Linux
x86_64, disposable REGTEST only. Published v0.1.11 Linux has an executable
GNU_STACK and is refused. It must never be relabeled or patched into a signed
release. Existing macOS/Windows signed intake and independent pins stay intact.

Reviewed source identities are constants in linux_developer_core.py: WAM
82a1487fd86f7021b1b9fc1524d267fca126f7d4 (GNU_STACK fix and ELF guard),
Bitcoin32efe850438ef22e2de39e562af557872a402c31, RandomX
102f8acf90a7649ada410de5499a7ec62e49e1da. The official fetch-upstream patcher
applies the WAM transformations. Application code does not edit upstream source.
Build uses its native configure/make recipe with no host service installation,
no mainnet process and no release-signing claim. Compiler uses-O2-g0, RandomX
x86-64 baseline; developer staged copies are stripped before hashes are recorded.

The manifest records final node and CLI hashes independently, ELF64 architecture,
exact GNU_STACK RW, system interpreter path/hash, and resolved loader/library
identities. Missing/duplicate/executable stack, writable executable segment,
custom interpreter, RPATH/RUNPATH, unresolved or non-system-owned library deny.
Runtime authorization requires BOTH explicit developer REGTEST consent and an
operator-supplied independently reviewed manifest SHA256. A self-written receipt
or source commit string alone cannot authorize an executable. The CI build trust
boundary is its reviewed pinned build job; its immediate self-test is build
acceptance, not independent release-signature authentication.

Dynamic library drift requires a new reviewed manifest/build. Readelf and ldd
are native binutils/glibc tools; ldd is used only after static ELF and explicit
developer trust checks, with no inherited LD_* environment. Same-user/root
malware, build-host compromise, fd-to-loader races, toolchain reproducibility
and production process binding remain unqualified. Build receipts do not claim
byte-identical rebuilds or an official signed v0.1.11 replacement.

First native gate is101 actual blocks and deterministic process/datadir cleanup.
It does not qualify scanner, wallet signing, custody, desktop/headless package or
portable recovery. These remain blocked until their platform-native real gates
pass. All wallet reservation, review, anchor and WSP gates remain mandatory.
