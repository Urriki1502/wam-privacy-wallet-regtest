# PR67 native Qt destruction regression

Inspected parent c05c3ef46c0a004146626809c8ac626d2f736870, 17 October 2026.
macOS run39020800563, Windows39020800581 and Linux39020800548 native Qt
all failed after successful widget assertions; frozen dependents were skipped.
These are FAIL, not PASS.

The same five managed widget tests reproduced exit139 on this Mac ARM64,
PySide6 6.12.0, with offscreen native Qt. The OS native fault frames were
QObject::~QObject → QWidget::~QWidget → QPushButtonWrapper::~QPushButtonWrapper
→ PySide::destructionVisitor → PySide::destroyQCoreApplication → shutdown.

ResponsiveRow deferred adding its children to its layout until resizeEvent.
Unshown windows consequently retained independent top-level panels, including
Hero and its connected QPushButtons. Deleting the window did not invalidate
these children. PySide's application-wide destruction visitor can visit a child
before its parent; deleting the parent then revisits stale native pointers.
This is an incomplete native ownership tree, not evidence of Core failure or
a second QApplication instance. Upstream implementation inspected:
https://github.com/pyside/pyside-setup/blob/6.12/sources/pyside6/libpyside/pyside.cpp
(destroyQCoreApplication/destructionVisitor).

The fix establishes the layout/parent tree immediately, then reuses the same
arrangement on resize. Application shutdown, synchronous window deletion, all
existing tests, exit codes and security gates remain enabled. No version pin or
supervisor/wallet authority changed.

Regression coverage in the existing three-OS managed widget suite checks:

- Native ancestry before first show, including Receive QR and overview Hero.
- An actual QThread blocks window close until finished; deferred thread deletion,
  stopped timers and disconnected appearance callback after accepted close.
- A separate native process creates/destroys twelve hidden/shown windows, resizes,
  asserts every captured child invalidated, explicitly destroys QApplication,
  verifies its singleton is gone, repeats shutdown safely and exits normally.
  This is widget lifetime evidence, not mock blockchain acceptance.

Local modified-parent verification: targeted8 tests PASS and process exit0;
full209 tests,175PASS/34platformSKIP and process exit0. Actual v0.1.11/Core
supervisor probe --qt-e2e separately passed clean same-tip restart, daemon crash
restart, simultaneous-owner refusal, independent-client disconnect and actual
Fusion window close/reopen while the dedicated supervisor/Core remained alive.
No WSP wallet continuity or frozen Q05 qualification is inferred from that probe.
Exact committed-head CI, frozen binaries and physical acceptance remain pending
until independently inspected. Local logs: outputs/pr67-qt-20261017.
