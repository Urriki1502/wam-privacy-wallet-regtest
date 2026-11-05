# Linux glibc baseline

The qualified Ubuntu 24.04 desktop package at functional pin
`56ea36186bf5a3410c75dda63b885f084de83610` bundles
`libpython3.12.so.1.0` with a `GLIBC_2.38` symbol version.
The package launches on Ubuntu 24.04 (glibc 2.39). It does not
launch on Ubuntu 22.04 (glibc 2.35). DEV WAM confirmed that split.

Minimum for the current packages: **glibc >= 2.38**.
Supported build and runtime baseline: **Ubuntu 24.04 x86_64**.
Ubuntu 22.04 is not supported. WSL2 process start is not physical
desktop GUI acceptance.

The pinned PySide6 6.12.0 x86_64 wheel is
`manylinux_2_34` (glibc 2.34). That wheel tag is not the 2.38
requirement. The requirement comes from the CPython that the
Ubuntu 24.04 builder freezes into the package.

Rebuilding on Ubuntu 22.04 is a separate future experiment. It is
feasible only if that builder uses a CPython 3.12 with no
`GLIBC_2.38` symbol and then passes the existing Linux gates on
both 22.04 and 24.04. This remediation does not claim that result
and does not change the runner.
