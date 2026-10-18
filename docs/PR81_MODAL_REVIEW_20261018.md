# Independent stack review — modal authority regression

18 October 2026 UTC, read-only audit of PR81 exact HEAD
`da0b27d341dc9b24317b5687ec5fb5a09c801d19` (all ten CI checks SUCCESS).
Earlier PR74 `1d715c9941ea7e571135131e23e8ad1bf6d21e2d` also reproduces it.
Neither branch was checked out, changed, rebased, merged or pushed by this
review. `git archive` snapshots in a separate output directory were tested.

**Confirmed P1 GUI lifecycle/authority defect, blocking affected P0 Q05/Q17
acceptance.** Native Qt event loops continue delivering timers inside modal
`QInputDialog`/`QMessageBox` calls. The independently developed GUI lacks PR67's
modal exclusion and the post-dialog state recheck. The resulting worker
creation is proven; unauthorized cryptographic signing, native anchor bypass,
fund loss and a native crash are NOT demonstrated by these UNIT tests.

## Reproduction evidence

[Public receipt](evidence/issue45/PR81_DA0B27D_MODAL_AUDIT.json).
The exact source snapshot plus existing PR67 modal regression stimulus gives
three behavioral test failures, zero errors, native exit1. Expanded authority
loss cases FAIL for all four Verify / View / Create / Open Spend paths. Real Qt
nested event loops deliver a public authority-loss event; workers and dialog
answers are explicitly test fixtures. No Core reply, blockchain, real key,
wallet or anchor is used. This is supplemental UNIT evidence, never real E2E.
Current PR67 source86bc912 passes its three original modal controls, exit0.

Concrete current source locations:

- [Worker start and verify dialog](https://github.com/Urriki1502/wam-privacy-wallet-regtest/blob/da0b27d341dc9b24317b5687ec5fb5a09c801d19/src/wam_regtest/managed_gui.py#L231): `_execute` can create a status worker during the password nested loop; a later wallet worker can replace the one `_worker` reference.
- [Spending approval/password](https://github.com/Urriki1502/wam-privacy-wallet-regtest/blob/da0b27d341dc9b24317b5687ec5fb5a09c801d19/src/wam_regtest/managed_gui.py#L287): after the dialog changes GUI authentication to false, `_ManagedSpendSessionWorker` is still constructed and started. Downstream Core/custody validation remains an independent barrier.
- [Create and view](https://github.com/Urriki1502/wam-privacy-wallet-regtest/blob/da0b27d341dc9b24317b5687ec5fb5a09c801d19/src/wam_regtest/managed_gui.py#L362): equivalent missing recheck after native dialogs.
- [Stop confirmation](https://github.com/Urriki1502/wam-privacy-wallet-regtest/blob/da0b27d341dc9b24317b5687ec5fb5a09c801d19/src/wam_regtest/managed_gui.py#L557): a background worker is created even while the modal confirmation is pending/canceled.

Portable [four-path reproducer](evidence/issue45/PR81_DA0B27D_MODAL_REPRO.py):

```sh
# Use the project's existing native Python/PySide dependencies. Do not run Core.
# An existing clean checkout can export an isolated reviewed source snapshot.
audit_root="$(mktemp -d /tmp/wam-modal-reviewed.XXXXXXXX)"
git archive da0b27d341dc9b24317b5687ec5fb5a09c801d19 src assets | tar -x -C "$audit_root"
PYTHONPATH="$audit_root/src" QT_QPA_PLATFORM=offscreen python docs/evidence/issue45/PR81_DA0B27D_MODAL_REPRO.py
```

Expected on that head: four failed subcases and exit1. Public test-only password
and empty temporary profile paths are intentional; no native vault is opened.
The source snapshot is created in a new temporary directory; preserve it for review.
The historical three-control stimulus can be retrieved verbatim from
`86bc912:tests/test_fusion_managed_gui.py`; run its three `test_*dialog*`/stop
modal cases with the same isolated PYTHONPATH and native teardown.

## Concrete patch proposal — NOT applied or qualified

[Single-file patch](evidence/issue45/PR81_DA0B27D_MODAL_PROPOSAL.patch), exact
base GUI SHA256 `e7cba6ed79af87724ae028db088103188ff8dd2340bc32cd0f5d405522f5bb08`.
Reuses PR67's existing `try/finally` modal exclusion, blocks timer/lifecycle and
window close while approval is pending, rechecks current authority/resources
before each worker is created, and covers the independently added dialogs.
No approval is removed, worker terminated, uncertain operation retried, anchor
reset or reservation released. No RPC/crypto/custody capability is expanded.

`git apply --check` passes against the exact isolated base. Review candidate
passes three original modal tests plus the four-path authority test (four
methods total, seven behavioral cases), all native Qt processes exit0. This is
macOS ARM64/offscreen UNIT evidence only. No claim that the proposed code has
passed genuine Core, Windows/Linux native, frozen or physical acceptance.

**Next actor:** maintainer of the independent active stack. Review and integrate
the correction in the appropriate EXISTING named T PR, retaining all new
features and approvals, then run exact-head native/Core/frozen regressions on
all three OS. Do not create a duplicate PR or silently merge/rebase the stack.
This chat remains restricted to its existing PR67 branch; only public review
material/checkpoint was committed here. Until coordinated integration, no
integrated T05/Q05 or wallet V1 completion is asserted. T-01→T-09 owner order
and Core Update Manager P1 deferral remain in force.
