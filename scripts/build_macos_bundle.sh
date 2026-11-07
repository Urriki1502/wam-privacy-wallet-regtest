#!/usr/bin/env bash
# Native macOS ARM64 only. Existing CI verifies GPG-signed official Core,
# immutable WSP source and actual Core/Qt E2E before this build is allowed.
set -euo pipefail
umask 077
# Distributed wallet bytes use the positive allowlist. The legacy frozen probe
# build is explicitly separate and must never stand in for production E2E.
case "${1:-}" in
  "") exec python -I scripts/build_macos_production.py ;;
  --qualification-only) shift ;;
esac
case "${1:-}" in
  "") export WAM_BUILD_SCOPE=full ;;
  --ui-layout-focused) export WAM_BUILD_SCOPE=ui-layout-focused ;;
  --v1-net-focused) export WAM_BUILD_SCOPE=v1-net-focused ;;
  *) exit 64 ;;
esac
test "$#" -le 1

test "$(uname -s)" = Darwin
test "$(uname -m)" = arm64
test "$(git -C wsp-upstream rev-parse HEAD)" = ac55f13423620252bdbf848c7e8a280c3b84721e
CORE_DIR="${WAM_MACOS_CORE_DIR:-$(pwd)/core}"
BUILD_ROOT="${WAM_MACOS_OUTPUT_ROOT:-$(pwd)}"
layout_args=(--core "$CORE_DIR")
if [ -n "${WAM_MACOS_OUTPUT_ROOT:-}" ]; then layout_args+=(--output "$BUILD_ROOT"); fi
python -I -m wam_regtest.macos_build_layout "${layout_args[@]}"
export WAM_MACOS_CORE_DIR="$CORE_DIR"
export WAM_MACOS_PACKAGE_DIR="$BUILD_ROOT/package-output"
mkdir -p bundle-input
SOURCE_STAGE=$(mktemp -d "$(pwd)/bundle-input/build-XXXXXX")
mkdir "$SOURCE_STAGE/spec" "$SOURCE_STAGE/runs"
export WAM_MACOS_RUN_ROOT="$SOURCE_STAGE/runs"
echo "MACOS_APP_SOURCE_STAGE=$SOURCE_STAGE"
python -I -m wam_regtest.build_provenance capture --stamp "$SOURCE_STAGE/wallet-source.json"
(cd wsp-upstream && env -u WAM_SOURCE_HEAD python -I -m wam_regtest.build_provenance capture --stamp "$SOURCE_STAGE/wsp-source.json")
python -I -m wam_regtest.package_manifest \
  --source-root "$(pwd)/wsp-upstream" \
  --output "$SOURCE_STAGE/wsp-source"

python -I -m wam_regtest.q05_package_provenance --stamp "$SOURCE_STAGE/wallet-source.json" \
  --output "$SOURCE_STAGE/Q05_BUILD_SOURCE.json"
python -I -m wam_regtest.distribution_notices --output "$SOURCE_STAGE/third-party-notices" --qt

echo "MACOS_APP_STAGE=PYINSTALLER_START"
python -I -m PyInstaller --noconfirm --clean --onedir --windowed \
  --distpath "$BUILD_ROOT/dist" --workpath "$BUILD_ROOT/build" --specpath "$SOURCE_STAGE/spec" \
  --name "WAM Privacy Wallet REGTEST" \
  --osx-bundle-identifier "org.wamcoin.privacywallet.regtest" \
  --icon "$(pwd)/assets/wam-wallet.icns" \
  --add-data "$(pwd)/assets/wam-coin-logo.png:branding" \
  --paths "$(pwd)/src" \
  --add-data "$SOURCE_STAGE/Q05_BUILD_SOURCE.json:." \
  --collect-submodules wam_regtest \
  --collect-submodules wam_sp \
  --copy-metadata coincurve \
  --hidden-import coincurve._cffi_backend \
  --add-data "$CORE_DIR/wamd:core" \
  --add-data "$CORE_DIR/wam-cli:core" \
  --add-data "$CORE_DIR/receipt.json:core" \
  --add-data "$SOURCE_STAGE/wsp-source:wsp-source" \
  --add-data "$SOURCE_STAGE/third-party-notices:third-party-notices" \
  src/wam_regtest/package_entry.py

echo "MACOS_APP_STAGE=PYINSTALLER_COMPLETED"
APP="$BUILD_ROOT/dist/WAM Privacy Wallet REGTEST.app"
# On macOS, PyInstaller re-codesigns --add-binary Mach-O executables,
# changing publisher-signed SHA-256. These binaries MUST be unmodified DATA,
# then made executable in-place; validate both hashes against ORIGINALS.
export WAM_BUNDLE_APP="$APP"
python -I - <<'PY'
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
    source = Path(os.environ["WAM_MACOS_CORE_DIR"]) / name
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
python -I - <<'PY'
from hashlib import sha256
from pathlib import Path
import os
for name in ("wamd", "wam-cli"):
    files = [p for p in Path(os.environ["WAM_BUNDLE_APP"]).rglob(name)
             if p.is_file() and not p.is_symlink()]
    if len(files) != 1:
        raise SystemExit("MACOS_BUNDLE_CORE_SHAPE_AFTER_CODESIGN_DENIED")
    if sha256(files[0].read_bytes()).hexdigest() != sha256((Path(os.environ["WAM_MACOS_CORE_DIR"]) / name).read_bytes()).hexdigest():
        raise SystemExit("MACOS_BUNDLE_CODESIGN_MODIFIED_CORE_DENIED")
print("MACOS_APP_STAGE=OUTER_APP_SIGNED_CORE_HASH_STILL_PASS", flush=True)
PY
python -I scripts/audit_wallet_security.py --root "$(pwd)" --core "$CORE_DIR" \
  --app "$APP" --output "$WAM_MACOS_PACKAGE_DIR/INDEPENDENT-WALLET-SECURITY.json"
BIN="$APP/Contents/MacOS/WAM Privacy Wallet REGTEST"
test -d "$APP"
test -x "$BIN"

# Validation MUST invoke the final frozen application, not an editable checkout.
export QT_QPA_PLATFORM=offscreen
export WAM_FROZEN_BIN="$BIN"
python -I - <<'PY'
import os
import subprocess
import sys
from pathlib import Path
import shutil, tempfile
from wam_regtest.macos_build_layout import frozen_environment
binary = os.environ["WAM_FROZEN_BIN"]
out=Path(os.environ['WAM_MACOS_PACKAGE_DIR'])
runs=Path(os.environ['WAM_MACOS_RUN_ROOT'])
clean_env=frozen_environment(os.environ)
ui_only = os.environ.get("WAM_BUILD_SCOPE") == "ui-layout-focused"
focused = os.environ.get("WAM_BUILD_SCOPE") in ("v1-net-focused", "ui-layout-focused")
print("MACOS_APP_STAGE=FROZEN_BUNDLE_SELF_CHECK_START", flush=True)
try:
    subprocess.run([binary, "--check-bundle"], env=clean_env, cwd=runs, timeout=45, check=True)
except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
    sys.exit("MACOS_FROZEN_BUNDLE_CHECK_DENIED")
print("MACOS_APP_STAGE=FROZEN_BUNDLE_SELF_CHECK_PASS", flush=True)
if not focused:
    print("MACOS_APP_STAGE=FROZEN_REAL_CORE_BIP352_QT_START", flush=True)
    try:
        clean=Path(tempfile.mkdtemp(prefix='frozen-gui-',dir=runs))
        subprocess.run([binary, "--ci-real-core-gui"], cwd=clean, env=clean_env, timeout=240, check=True)
        for name in ('real-regtest-gui-preview.png','real-regtest-wallet-preview.png','real-regtest-security-preview.png'):
            shutil.copyfile(clean/name,out/name)
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
        sys.exit("MACOS_FROZEN_REAL_CORE_GUI_DENIED")
    print("MACOS_APP_STAGE=FROZEN_REAL_CORE_BIP352_QT_PASS", flush=True)
# Q01 also needs the actual native window-system runtime, independently of
# offscreen rendering. This existing CI mode retains full custody/Core gates.
from pathlib import Path
import shutil, tempfile
from contextlib import nullcontext
from json import loads
cocoa = frozen_environment(os.environ,'cocoa')
if not focused:
    with nullcontext(tempfile.mkdtemp(prefix='wam-q01-mac-frozen-cwd-',dir=runs)) as clean:
        subprocess.run([str(Path(binary).resolve()), '--ci-real-core-wallet-cocoa'],
                       cwd=clean, env=cocoa, timeout=600, check=True)
        # Copy public fixture evidence only, never any runtime/vault/datadir.
        review = Path(clean)
        public = out/'cocoa-evidence'; public.mkdir()
        shutil.copytree(review/'fusion-ui-review', public/'fusion-ui-review', dirs_exist_ok=True)
        for name in ('real-regtest-wallet-preview.png', 'real-regtest-security-preview.png'):
            shutil.copyfile(review/name, public/name)
    print("MACOS_APP_STAGE=FROZEN_NATIVE_COCOA_REAL_CORE_PASS", flush=True)
    print("MACOS_APP_STAGE=FROZEN_Q04_EXTERNAL_MINER_START", flush=True)
    with nullcontext(tempfile.mkdtemp(prefix='wam-q04-mac-frozen-',dir=runs)) as clean:
        q04_env = frozen_environment(os.environ)
        subprocess.run([str(Path(binary).resolve()), '--ci-q04-external-miner'],
                       cwd=clean, env=q04_env, timeout=600, check=True)
        shutil.copyfile(Path(clean)/'q04-frozen-evidence.json',out/'q04-frozen-evidence.json')
    print("MACOS_APP_STAGE=FROZEN_Q04_EXTERNAL_MINER_PASS", flush=True)
    # Reuse this SAME signed-Core + frozen-app job for the actual Q06 create /
    # reopen / fresh BIP39 restore + native Cocoa receive view. No new CI job,
    # synthetic RPC, background miner or developer-managed node is introduced.
    print("MACOS_APP_STAGE=FROZEN_Q06_BIP39_OWNER_READONLY_START", flush=True)
    with nullcontext(tempfile.mkdtemp(prefix='wam-q06-mac-frozen-',dir=runs)) as clean:
        subprocess.run([str(Path(binary).resolve()), '--ci-q06-bip39-readonly'],
                       cwd=clean, env=cocoa, timeout=420, check=True)
        report = Path(clean)/'q06-frozen-readonly-evidence.json'
        from json import loads
        data = loads(report.read_text())
        assert (data['status']=='Q06_NATIVE_BIP39_12_READONLY_OWNER_GUI_PASS'
                and data['Q06_BIP39_disposable_fresh_restore_same_receive'] is True
                and data['Q06_native_Qt_receive_bound'] is True
                and data['Q06_native_Qt_funded_balance_bound'] is True
                and type(data['Q06_actual_onchain_BIP39_received_atoms']) is int
                and data['Q06_actual_onchain_BIP39_received_atoms'] > 0
                and data['Q06_original_core_clean_shutdown'] is True
                and data['Q06_Sign_or_Broadcast_executed'] is False)
        shutil.copyfile(report,out/'q06-frozen-readonly-evidence.json')
    print("MACOS_APP_STAGE=FROZEN_Q06_BIP39_OWNER_READONLY_PASS", flush=True)
if ui_only:
    # UI-only candidate: actual final Cocoa executable, no wallet/Core runtime.
    for name, scale in (("native", None), ("scale-1x", "0.5")):
        clean = Path(tempfile.mkdtemp(prefix='ui-layout-', dir=runs))
        ui_env = dict(cocoa)
        if scale is not None:
            ui_env['QT_SCALE_FACTOR'] = scale
        subprocess.run([str(Path(binary).resolve()), '--ci-ui-layout'],
                       cwd=clean, env=ui_env, timeout=120, check=True)
        report = loads((clean/'ui-layout-evidence.json').read_text())
        assert report['status'] == 'UI_LAYOUT_PASS' and report['frozen'] is True
        assert report['qt_platform'] == 'cocoa' and report['backend_or_core_started'] is False
        public = out/('ui-layout-' + name)
        shutil.copytree(clean/'ui-layout-review', public)
        shutil.copyfile(clean/'ui-layout-evidence.json', public/'evidence.json')
    print("MACOS_APP_STAGE=FROZEN_NATIVE_UI_LAYOUT_PASS_NO_CORE_EXECUTED", flush=True)
else:
    # Use the exact same packaged app and immutable Core/WSP source for Q06 Send.
    # This is a disposable REGTEST qualification, not a mainnet or release grant.
    print("MACOS_APP_STAGE=FROZEN_Q06_BIP39_SPEND_START", flush=True)
    spend_env = dict(cocoa)
    spend_env["WAM_Q06_CI_SPEND_QUALIFY"] = "1"
    # Keep signed/uncertain test state even if this outer builder fails. Only
    # public receipts/screenshots are copied to package-output; custody remains
    # private under the canonical workspace's generated bundle-input directory.
    with nullcontext(tempfile.mkdtemp(prefix='q06-frozen-', dir=runs)) as clean:
        subprocess.run([str(Path(binary).resolve()), '--ci-q06-bip39-spend'],
                       cwd=clean, env=spend_env, timeout=600, check=True)
        report=Path(clean)/'q06-frozen-spend-evidence.json'
        data=loads(report.read_text())
        assert (data["status"]=="Q06_NATIVE_BIP39_SEND_CONFIRM_REOPEN_PASS"
                and data["mainnet_allowed"] is False
                and data["q06_bip39_spend_confirmed"] is True
                and data["q06_bip39_same_owner_reopen_reserved"] is True
                and data["q06_bip39_same_chain_seed_history_recovery"] is True
                and data["fresh_same_chain_profile_full_history_recovered"] is True
                and data["q06_post_reopen_txid_readonly_reconciliation"] is True
                and data["q06_bip39_fresh_mnemonic_full_history_recovery"] is False)
        shutil.copyfile(report,out/'q06-frozen-spend-evidence.json')
        shutil.copytree(Path(clean)/'fusion-ui-review',
                        out/'q06-ui-review')
    print("MACOS_APP_STAGE=FROZEN_Q06_BIP39_SPEND_PASS", flush=True)
    print("MACOS_APP_STAGE=FROZEN_V1_NET_START", flush=True)
    with nullcontext(tempfile.mkdtemp(prefix='shared-frozen-',dir=runs)) as clean:
        subprocess.run([str(Path(binary).resolve()),'--ci-v1-net-shared-regtest'],
                       cwd=clean,env=cocoa,timeout=900,check=True)
        report=Path(clean)/'shared-network-evidence.json'
        shared=loads(report.read_text())
        isolated=loads((out/'q06-frozen-spend-evidence.json').read_text())
        assert shared['source_sha']==isolated['source_sha']
        assert all(shared['cases'][f'V{i}']=='PASS' for i in range(1,17))
        assert shared['cases']['V17']=='PASS' and shared['reorg']['custody_fail_closed'] is True
        assert shared['reorg']['explicit_gui_reconciliation'] is True and shared['reorg']['post_recovery_same_profile_restart'] is True
        assert shared['cases']['V19']=='BLOCKED' and shared['two_physical_computers'] is False
        shared['cases']['V18']='PASS'
        shared['isolated_regression_receipt']='q06-frozen-spend-evidence.json'
        (out/'v1-net-frozen-evidence.json').write_text(__import__('json').dumps(shared,indent=2)+'\n')
        lab=Path(shared['retained_lab'])
        for image in lab.glob('node-*.png'):
            shutil.copyfile(image,out/image.name)
    print("MACOS_APP_STAGE=FROZEN_V1_NET_LOCAL_PASS_TWO_HOST_BLOCKED", flush=True)
PY
if [ "$WAM_BUILD_SCOPE" = full ]; then
  python -I scripts/qualify_q05_frozen.py --executable "$BIN" \
    --output "$WAM_MACOS_PACKAGE_DIR/q05-frozen-evidence.json"
  test -s "$WAM_MACOS_PACKAGE_DIR/real-regtest-gui-preview.png"
  test -s "$WAM_MACOS_PACKAGE_DIR/real-regtest-wallet-preview.png"
  test -s "$WAM_MACOS_PACKAGE_DIR/real-regtest-security-preview.png"

fi

echo "MACOS_APP_STAGE=PACKAGED_CHECKS_PASS_SCOPE_$WAM_BUILD_SCOPE"
python -I -m wam_regtest.build_provenance verify --stamp "$SOURCE_STAGE/wallet-source.json" \
  --receipt "$WAM_MACOS_PACKAGE_DIR/BUILD_SOURCE_RECEIPT.json"
(cd wsp-upstream && env -u WAM_SOURCE_HEAD python -I -m wam_regtest.build_provenance verify --stamp "$SOURCE_STAGE/wsp-source.json")
# Preserve macOS bundle metadata/resource forks in the downloadable ZIP.
ditto -c -k --sequesterRsrc --keepParent "$APP" \
  "$WAM_MACOS_PACKAGE_DIR/WAM-Privacy-Wallet-REGTEST-macOS-ARM64.app.zip"

# The DMG is an unnotarized developer preview. Do not claim Developer ID.
echo "MACOS_APP_STAGE=DMG_CREATE_START"
# Retry ONLY transient macOS diskimages "Resource busy", max three
# attempts. Each attempt uses private staging. Verify with hdiutil before
# atomic final publication; never detach unrelated volumes or bypass E2E.
python -I scripts/create_verified_dmg.py \
  --app "$APP" \
  --output "$WAM_MACOS_PACKAGE_DIR/WAM-Privacy-Wallet-REGTEST-macOS-ARM64.dmg"
echo "MACOS_APP_STAGE=DMG_VERIFIED"

python -I - <<'PY'
from hashlib import sha256
from pathlib import Path
import json
import os
package=Path(os.environ['WAM_MACOS_PACKAGE_DIR'])
core=Path(os.environ['WAM_MACOS_CORE_DIR'])
out = {}
for name in ("WAM-Privacy-Wallet-REGTEST-macOS-ARM64.app.zip",
             "WAM-Privacy-Wallet-REGTEST-macOS-ARM64.dmg"):
    p = package / name
    if not p.is_file() or p.stat().st_size <= 0:
        raise SystemExit("MACOS_PACKAGE_ARTIFACT_MISSING")
    out[name] = {
        "sha256": sha256(p.read_bytes()).hexdigest(),
        "size_bytes": p.stat().st_size,
    }
assert len(out) == 2
(package/"SHA256SUMS.json").write_text(
    json.dumps({
        "status": "UNNOTARIZED_REAL_REGTEST_MACOS_ARM64_PREVIEW",
        "source": "signed WAM Core v0.1.13 + pinned WSP-1",
        "source_commit": __import__("subprocess").check_output(["git", "rev-parse", "HEAD"],text=True).strip(),
        "independent_contract_receipt_sha256": sha256((package/'INDEPENDENT-WALLET-SECURITY.json').read_bytes()).hexdigest(),
        "original_brand_sha256": sha256(Path("assets/wam-coin-original.png").read_bytes()).hexdigest(),
        "logo_brand_sha256": sha256(Path("assets/wam-coin-logo.png").read_bytes()).hexdigest(),
        "bundle_icon_sha256": sha256(Path("assets/wam-wallet.icns").read_bytes()).hexdigest(),
        "wamd_sha256": sha256((core/'wamd').read_bytes()).hexdigest(),
        "wam_cli_sha256": sha256((core/'wam-cli').read_bytes()).hexdigest(),
        "real_core_packaged_e2e": __import__("os").environ["WAM_BUILD_SCOPE"] != "ui-layout-focused",
        "native_ui_layout_e2e_pass": __import__("os").environ["WAM_BUILD_SCOPE"] == "ui-layout-focused",
        "qualification_scope": __import__("os").environ["WAM_BUILD_SCOPE"],
        "full_exact_commit_Q01_Q06_qualified": __import__("os").environ["WAM_BUILD_SCOPE"] == "full",
        "q01_external_working_directory": True,
        "q01_developer_python_path_removed": True,
        "mainnet_allowed": False,
        "files": out,
    }, indent=2, sort_keys=True) + "\n",
)
from wam_regtest.release_candidate import write_candidate_manifest
write_candidate_manifest(package,'macos-arm64',{
    'wamd':sha256((core/'wamd').read_bytes()).hexdigest(),
    'wam-cli':sha256((core/'wam-cli').read_bytes()).hexdigest()},
    qualification_scope=__import__('os').environ['WAM_BUILD_SCOPE'])
print("MACOS_ARM64_PACKAGED_APP_DMG_PASS_SCOPE_" + __import__("os").environ["WAM_BUILD_SCOPE"])
PY
