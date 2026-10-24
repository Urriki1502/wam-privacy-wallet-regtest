# Q17 Windows frozen toolbar clipping — focused acceptance repair

Base Draft122 `522b36e6e10c47f97f36e9cd3a6bab6eb8fef50e`, not the independent
K-09 Draft90 child. One Q17 branch/Draft; no automatic merge. REGTEST only,
unchanged Core v0.1.11 and WSP `ac55f13423620252bdbf848c7e8a280c3b84721e`.

## Original evidence and measured cause

Windows run39910990610 artifact12485287440 contains the actual failing image
`ui-scale-1.25/fusion-ui-review/q05-managed-frozen-read.png`. Original API ZIP
SHA256 `551da5b71d0b0a35b7a3ea274c3b97c04b58271e8af75c599c42955bec653861`.
The downloaded bytes were reused and independently reverified against the live
API; the original FAIL is retained, never relabeled PASS.

The shell uses one horizontal row, and managed Core adds two visible actions.
SOURCE measurement of the unchanged baseline at820x600: toolbar556px wide,
layout minimum721px. The title received58x21 although its natural width91 and
wrapped height42 were required; Core actions received96px against143/144px
natural widths. This local Qt measurement is not Windows-native evidence.
Windows rendering evidence comes from the original frozen artifact and the
new exact-head native/frozen receipts, not platform emulation.

The repair uses Qt height-for-width and natural item sizes, wrapping before
compression. It reserves complete row heights, centers controls vertically and
keeps wide-layout title/action alignment. Hidden delegated actions keep their
original handlers. No DPI-specific offsets, reduced font sizes, hidden warnings,
authority/signing/custody changes or K-09 changes.

## New evidence contract

The existing real Q05 GUI child explicitly captures six states: initial locked,
Core-verified locked, verified original read and spending views, unavailable
owned Core, and authenticated runtime recovery-required refusal after genuine
GUI termination. Each state is measured at1280x800 and supported minimum820x600,
in existing Light/Dark styles. Actual geometry and device ratio are recorded;
requested sizes are never substituted for OS-observed geometry.

Assertions inspect style content rectangles, font metrics/natural sizes, full
control bounds, overlap, essential status/warning text, scrollable actions and
navigation. Every image has a SHA256 tied to the actual executable and source.
The Windows builder keeps100% screenshots as well as125%/150%; all three full
genuine Core/WSP frozen suites remain mandatory. No extra workflow is added.

The platform aggregate independently requires every native/frozen geometry
receipt and actual image hash/dimensions, alongside unchanged A06/Q05 gates.
Missing, stale or malformed evidence fails. Geometry JSON cannot approve its
own visual rendering: `visual_approval=PENDING_REVIEW` remains explicit.
Actual screenshots must be separately inspected before a scoped visual PASS.
Only fixed public control geometry is retained on failure, never fixture files,
password dialogs, seeds or arbitrary exception arguments.

Local Qt contracts are SOURCE supplements, not Windows or real-Core PASS.
Exact-head CI, actual artifact inspection and the Draft description determine
current status. No acceptance is inherited from the base after runtime changes.
Full Q17/V1, ordinary managed onboarding, physical device/OS-appearance checks
and independent DEV/security review remain pending even if this clipping scope
qualifies. Do not begin Q06/Q07/Q12/Q16 automatically after this task.
