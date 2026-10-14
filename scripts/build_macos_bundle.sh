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
python -m wam_regtest.package_manifest \
  --source-root "$(pwd)/wsp-upstream" \
  --output "$(pwd)/bundle-input/wsp-source"

echo "MACOS_APP_STAGE=PYINSTALLER_START"
python -m PyInstaller --noconfirm --clean --onedir --windowed \
  --name "WAM Privacy Wallet REGTEST" \
  --osx-bundle-identifier "org.wamcoin.privacywallet.regtest" \
  --paths "$(pwd)/src" \
  --collect-submodules wam_regtest \
  --collect-submodules wam_sp \
  --add-binary "$(pwd)/core/wamd:core" \
  --add-binary "$(pwd)/core/wam-cli:core" \
  --add-data "$(pwd)/core/receipt.json:core" \
  --add-data "$(pwd)/bundle-input/wsp-source:wsp-source" \
  src/wam_regtest/package_entry.py

echo "MACOS_APP_STAGE=PYINSTALLER_COMPLETED"
APP="dist/WAM Privacy Wallet REGTEST.app"
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
for p in sorted(Path("package-output").iterdir()):
    if p.is_file():
        out[p.name] = {
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
