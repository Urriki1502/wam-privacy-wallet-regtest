#!/usr/bin/env bash
# Native macOS ARM64 only. Existing CI verifies GPG-signed official Core,
# immutable WSP source and actual Core/Qt E2E before this build is allowed.
set -euo pipefail
umask 077

test "$(uname -s)" = Darwin
test "$(uname -m)" = arm64
test "$(git -C wsp-upstream rev-parse HEAD)" = ac55f13423620252bdbf848c7e8a280c3b84721e
test -x core/wamd
test -x core/wam-cli
test -f core/receipt.json
mkdir -p bundle-input package-output
SOURCE_STAGE=$(mktemp -d "$(pwd)/bundle-input/build-XXXXXX")
trap 'rm -rf "$SOURCE_STAGE"' EXIT
python -m wam_regtest.package_manifest \
  --source-root "$(pwd)/wsp-upstream" \
  --output "$SOURCE_STAGE/wsp-source"

echo "MACOS_APP_STAGE=PYINSTALLER_START"
python -m PyInstaller --noconfirm --clean --onedir --windowed \
  --name "WAM Privacy Wallet REGTEST" \
  --osx-bundle-identifier "org.wamcoin.privacywallet.regtest" \
  --paths "$(pwd)/src" \
  --collect-submodules wam_regtest \
  --collect-submodules wam_sp \
  --hidden-import coincurve._cffi_backend \
  --add-data "$(pwd)/core/wamd:core" \
  --add-data "$(pwd)/core/wam-cli:core" \
  --add-data "$(pwd)/core/receipt.json:core" \
  --add-data "$SOURCE_STAGE/wsp-source:wsp-source" \
  src/wam_regtest/package_entry.py

echo "MACOS_APP_STAGE=PYINSTALLER_COMPLETED"
APP="dist/WAM Privacy Wallet REGTEST.app"
# On macOS, PyInstaller re-codesigns --add-binary Mach-O executables,
# changing publisher-signed SHA-256. These binaries MUST be unmodified DATA,
# then made executable in-place; validate both hashes against ORIGINALS.
export WAM_BUNDLE_APP="$APP"
python - <<'PY'
from hashlib import sha256
import os
from pathlib import Path
app = Path(os.environ["WAM_BUNDLE_APP"])
for name in ("wamd", "wam-cli"):
    candidates = [p for p in app.rglob(name)
                  if p.is_file() and not p.is_symlink()]
    if len(candidates) != 1:
        raise SystemExit("MACOS_BUNDLE_CORE_MEMBER_SHAPE_DENIED")
    target = candidates[0]
    source = Path("core") / name
    if sha256(target.read_bytes()).hexdigest() != sha256(source.read_bytes()).hexdigest():
        # PyInstaller re-signs Mach-O even when staged as data. Restore the
        # verbatim official release member AFTER PyInstaller finishes.
        # The final application cannot run until exact SHA-256 matches again.
        import shutil
        shutil.copyfile(source, target)
    if sha256(target.read_bytes()).hexdigest() != sha256(source.read_bytes()).hexdigest():
        raise SystemExit("MACOS_BUNDLE_CORE_SIGNED_HASH_DENIED")
    target.chmod(0o700)
    if not os.access(target, os.X_OK):
        raise SystemExit("MACOS_BUNDLE_CORE_EXEC_MODE_DENIED")
print("MACOS_APP_STAGE=UNMODIFIED_SIGNED_CORE_SHA256_PASS", flush=True)
PY
# Update outer ad-hoc app resources signature only. The original WAM Core
# Mach-O SHA-256 MUST remain byte-for-byte identical to upstream after signing.
codesign --force --sign - --timestamp=none "$APP"
python - <<'PY'
from hashlib import sha256
from pathlib import Path
for name in ("wamd", "wam-cli"):
    files = [p for p in Path("dist/WAM Privacy Wallet REGTEST.app").rglob(name)
             if p.is_file() and not p.is_symlink()]
    if len(files) != 1:
        raise SystemExit("MACOS_BUNDLE_CORE_SHAPE_AFTER_CODESIGN_DENIED")
    if sha256(files[0].read_bytes()).hexdigest() != sha256((Path("core") / name).read_bytes()).hexdigest():
        raise SystemExit("MACOS_BUNDLE_CODESIGN_MODIFIED_CORE_DENIED")
print("MACOS_APP_STAGE=OUTER_APP_SIGNED_CORE_HASH_STILL_PASS", flush=True)
PY
BIN="$APP/Contents/MacOS/WAM Privacy Wallet REGTEST"
test -d "$APP"
test -x "$BIN"

# Validation MUST invoke the final frozen application, not an editable checkout.
export QT_QPA_PLATFORM=offscreen
export WAM_FROZEN_BIN="$BIN"
python - <<'PY'
import os
import subprocess
import sys
binary = os.environ["WAM_FROZEN_BIN"]
print("MACOS_APP_STAGE=FROZEN_BUNDLE_SELF_CHECK_START", flush=True)
try:
    subprocess.run([binary, "--check-bundle"], timeout=45, check=True)
except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
    sys.exit("MACOS_FROZEN_BUNDLE_CHECK_DENIED")
print("MACOS_APP_STAGE=FROZEN_BUNDLE_SELF_CHECK_PASS", flush=True)
print("MACOS_APP_STAGE=FROZEN_REAL_CORE_BIP352_QT_START", flush=True)
try:
    subprocess.run([binary, "--ci-real-core-gui"], timeout=240, check=True)
except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
    sys.exit("MACOS_FROZEN_REAL_CORE_GUI_DENIED")
print("MACOS_APP_STAGE=FROZEN_REAL_CORE_BIP352_QT_PASS", flush=True)
PY
test -s real-regtest-gui-preview.png

echo "MACOS_APP_STAGE=PACKAGED_REAL_CORE_GUI_PASS"
# Preserve macOS bundle metadata/resource forks in the downloadable ZIP.
ditto -c -k --sequesterRsrc --keepParent "$APP" \
  "package-output/WAM-Privacy-Wallet-REGTEST-macOS-ARM64.app.zip"

# The DMG is an unnotarized developer preview. Do not claim Developer ID.
echo "MACOS_APP_STAGE=DMG_CREATE_START"
hdiutil create -volname "WAM Privacy Wallet REGTEST" \
  -srcfolder "$APP" -format UDZO -ov \
  "package-output/WAM-Privacy-Wallet-REGTEST-macOS-ARM64.dmg"
hdiutil verify "package-output/WAM-Privacy-Wallet-REGTEST-macOS-ARM64.dmg"
echo "MACOS_APP_STAGE=DMG_VERIFIED"

python - <<'PY'
from hashlib import sha256
from pathlib import Path
import json
out = {}
for name in ("WAM-Privacy-Wallet-REGTEST-macOS-ARM64.app.zip",
             "WAM-Privacy-Wallet-REGTEST-macOS-ARM64.dmg"):
    p = Path("package-output") / name
    if not p.is_file() or p.stat().st_size <= 0:
        raise SystemExit("MACOS_PACKAGE_ARTIFACT_MISSING")
    out[name] = {
        "sha256": sha256(p.read_bytes()).hexdigest(),
        "size_bytes": p.stat().st_size,
    }
assert len(out) == 2
Path("package-output/SHA256SUMS.json").write_text(
    json.dumps({
        "status": "UNNOTARIZED_REAL_REGTEST_MACOS_ARM64_PREVIEW",
        "source": "signed WAM Core v0.1.11 + pinned WSP-1",
        "real_core_packaged_e2e": True,
        "mainnet_allowed": False,
        "files": out,
    }, indent=2, sort_keys=True) + "\n",
)
print("MACOS_ARM64_REAL_CORE_BIP352_PACKAGED_APP_DMG_E2E_PASS")
PY
