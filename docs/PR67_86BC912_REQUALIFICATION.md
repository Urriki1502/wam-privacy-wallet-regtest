# PR67 — exact 86bc912 component requalification

Observed 18 October 2026 UTC. Qualified source
`86bc912f9411990cbc22b0316c470e9407a669b6`; CI merge
`d570211b48b2bfecfbf6b54da3960c2349d77208`, independently verified parents
`71a1e7b4336054bf0dabf3ca0ee6de174b462154` and that PR67 head.
Merge tree equals source-head tree. Runtime is unchanged from c21bbd1; this
head has its OWN completed ten-check CI and its OWN inspected packages.
This does not qualify a later documentation commit or an independent stack.

[All ten exact-head checks](evidence/issue45/PR67_86BC912_ALL_CI.json) completed
SUCCESS. [Native source inventory](evidence/issue45/PR67_86BC912_SOURCE_INVENTORY.json)
reproduces 338 tracked files from Git. Mac/Linux LF inventory is
`06f8a23fb772c4bc794a2626254957ae949c99894fdc4ccabcb34c5850baebdd`;
Windows CRLF inventory is
`293fb27786c1164c51dda504e5a845661a2f990c2cb2441d6326795862502a84`.
Windows conversion was independently reproduced with Git checkout filters,
including the pinned source-contract no-conversion attribute. This is source
bookkeeping, not host or dependency supply-chain attestation.

| Platform | Native/Core and final frozen CI component | Downloaded bytes | Physical |
| --- | --- | --- | --- |
| macOS ARM64 | PASS, [run39078900422](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/39078900422) | PASS, [receipt](evidence/issue45/PR67_86BC912_MAC_CI.json) | PENDING_OPERATOR |
| Windows x64 | PASS, [run39078900380](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/39078900380) | PASS,354 files,125/150%DPI [receipt](evidence/issue45/PR67_86BC912_WINDOWS_CI.json) | PENDING_OPERATOR |
| Linux x86_64 desktop | PASS, [run39078900420](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/39078900420) | PASS,454 files/25 internal links [receipt](evidence/issue45/PR67_86BC912_LINUX_DESKTOP.json) | PENDING_OPERATOR |
| Linux x86_64 headless | PASS, same Linux run; GUI fault roles N/A | PASS,193 files, [receipt](evidence/issue45/PR67_86BC912_LINUX_HEADLESS.json) | PENDING_OPERATOR |

All four outer API digests, inner payload/RC/file manifests, source identity,
architecture and independent Core pair pins were inspected against actual
bytes. Desktop receipts tie actual final supervisor/scanner/Qt processes and
explicit owned-Core kill/restart to the final executable hash; six pre-state
scope refusals, same height101/tip, expected kill -9POSIX/1Windows and verified
shutdown remain mandatory. Headless has no Qt-role acceptance claim.
Linux uses the separately reviewed developer Core; it is not an official
signed Linux release. Official signed v0.1.11 Mac/Windows members remain exact.
No v0.1.12 runtime approval, mainnet permission or upstream Core change.

## Actual downloads and checksums

| Artifact | Outer ZIP SHA256 | Inner payload SHA256 |
| --- | --- | --- |
| [Mac12117728245](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/39078900422/artifacts/12117728245) | `c6b6507dff9d247b525c1e35a91e16d9a8bd6347f07ca64179d3b5d724773eeb` | appZIP `872c1cf15e5a2d1202ea99fc499784f52104a79d42e5bc5f18be2e05326caaf4`; DMG `425137589ecde6886e075ed94f9eac262d4dfd1c0420ed985ab14da9f981a34e` |
| [Windows12118552689](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/39078900380/artifacts/12118552689) | `7f438b4a489dca08e7a0a42d03aadb3aa403a66dfaefc6935720c4490b41174f` | `dbc48981226047bc5627f74cf19c38ec33e9cef7d164e682e620e49fe979462d` |
| [Linux desktop12117953556](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/39078900420/artifacts/12117953556) | `7ae07be4aa5d47082ac8c19e152a6bc5f6c06e0c666f2d13e38c10194d6c9a7c` | `c43735e6d56570cfdc0caaeb1e68acf18cdd4761ce44de0f2bc7b9ef24788388` |
| [Linux headless12118281478](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/39078900420/artifacts/12118281478) | `c889a6099757f59642f06cc192abcee145a48db91bcf3aef491b26edb938f459` | `c7b9be1edfee8ad50899aee928f49cba582cbbc89586e657ab328df1b1f8eeed` |

## Local and integrated limitations

The actual downloaded Mac executable passed `--check-bundle`, exit0, after
safe archive inspection/extraction. [Local receipt](evidence/issue45/PR67_86BC912_MAC_LOCAL_PREFLIGHT.json).
Its earlier full Cocoa wallet invocation was interrupted: no final receipt or
exit status exists, so it is NOT local Cocoa PASS. No process from that exact
bundle remained at resume. Test fixtures were not adopted, retried or repaired.
Prior c21bbd1 Cocoa evidence stays historical; no Windows/Linux local execution
or physical Finder/focus/OS-settings/retina/camera usability is asserted.

All integrated T/Q/V1 gates remain PENDING. Core fault is on a quiescent stable
isolated chain, not power-loss or crash-during-Core-write proof. The independent
latest stack has a [confirmed modal regression and review-only patch](PR81_MODAL_REVIEW_20261018.md).
Green CI does not invalidate a separately reproduced negative-test failure.
No automatic merge or modification of independent branches.
