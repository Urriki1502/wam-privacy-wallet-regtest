# A-02: publish the declared macOS rollback instructions

Baseline PR108 `f642682fa2731a5334facff8515b84d9605aa0dd` and PR109 `2e15a5eaa33e55322e7548edd41a0660f5046c06` build the R06 instructions and include their digest in `RELEASE_CANDIDATE_MANIFEST.json` and `SHA256SUMS.txt`, but the macOS upload allowlist omits the file. The pre-upload R04 inventory audit passes on the build directory; the distributed archive is incomplete.

Independent reproduction used the actual authenticated GitHub artifact ZIP, not a fabricated package:

| Source | Run / artifact | Outer archive SHA-256 |
|---|---|---|
| PR108 f642682 | 39446866899 / 12277761174 | `e0dc7e007b4161658724d15d705ca0361bed6b155bb4f773b80ea715f34c09ed` |
| PR109 2e15a5e | 39520236577 / 12311530473 | `a556481a739619810121fa450f2c26fad04cd67fa085f8113a034621c807154d` |

For both archives, read `package-output/RELEASE_CANDIDATE_MANIFEST.json`; every declared member matches except absent `package-output/ISSUE45_R06_RELEASE_ROLLBACK.md`. The declared document SHA-256 is `22baa9a40105b7a3bd75bef3590a1fd8de0aa5ba202202304f8e20868d40838c`. Embedded official v0.1.11 daemon/CLI hashes still match their independent pins. Windows and both Linux package inventories are complete. This is a distribution correctness blocker, not evidence of changed Core binaries.

The fix adds the one missing public instruction file to the existing upload allowlist. Runtime, cryptography, signatures, wallet data, build gates, manifest generation and public privacy audit are unchanged. No extra workflow/job or broad upload glob is introduced.

Validation must inspect the newly downloaded exact-head artifact after native/frozen CI: authenticate outer API digest, check source/checkout identity, compare every manifest member and SHA256SUMS entry, and independently hash embedded Core bytes. Green CI before publication alone cannot close A-02. Exact repaired-artifact evidence belongs to the acceptance checkpoint; physical and DEV review remain pending. No automatic merge.
