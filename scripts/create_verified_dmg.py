"""Fail-closed macOS DMG publication with bounded Resource-busy retry.

A transient hdiutil "create failed - Resource busy" must not turn a successful
signed-Core + WSP + frozen-Qt E2E into an unreliable release pipeline.
Never detach arbitrary system volumes, skip verification, or publish partial DMG.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import tempfile
import time


class DmgBuildError(RuntimeError):
    pass


def create_verified_dmg(
    app: Path,
    output: Path,
    *,
    runner=subprocess.run,
    sleeper=time.sleep,
) -> int:
    if (not isinstance(app, Path) or not isinstance(output, Path)
            or not app.is_absolute() or not output.is_absolute()
            or not app.is_dir() or app.is_symlink()
            or not output.parent.is_dir() or output.is_symlink()
            or output.suffix != ".dmg"
            or not app.name.endswith(".app")):
        raise DmgBuildError("DMG_INPUT_SCOPE_DENIED")

    with tempfile.TemporaryDirectory(prefix=".wam-dmg-build-", dir=output.parent) as temp:
        staging = Path(temp)
        for attempt in range(1, 4):
            candidate = staging / ("attempt-" + str(attempt) + ".dmg")
            print("DMG_CREATE_ATTEMPT=" + str(attempt), flush=True)
            cmd = [
                "hdiutil", "create", "-volname", "WAM Privacy Wallet REGTEST",
                "-srcfolder", str(app), "-format", "UDZO", str(candidate),
            ]
            try:
                result = runner(cmd, capture_output=True, text=True, timeout=120, check=False)
            except (subprocess.TimeoutExpired, OSError):
                raise DmgBuildError("DMG_CREATE_PROCESS_DENIED") from None

            if result.returncode != 0:
                message = (result.stdout or "") + "\n" + (result.stderr or "")
                if "resource busy" in message.lower() and attempt < 3:
                    print("DMG_CREATE_RESOURCE_BUSY_RETRY", flush=True)
                    candidate.unlink(missing_ok=True)  # Only our own staging file.
                    sleeper(2 * attempt)
                    continue
                if "resource busy" in message.lower():
                    raise DmgBuildError("DMG_CREATE_RESOURCE_BUSY_EXHAUSTED")
                raise DmgBuildError("DMG_CREATE_NONTRANSIENT_FAILURE")

            if not candidate.is_file() or candidate.stat().st_size < 4096:
                raise DmgBuildError("DMG_CREATE_OUTPUT_INVALID")

            try:
                verified = runner(
                    ["hdiutil", "verify", str(candidate)],
                    capture_output=True, text=True, timeout=120, check=False,
                )
            except (subprocess.TimeoutExpired, OSError):
                raise DmgBuildError("DMG_VERIFY_PROCESS_DENIED") from None
            if verified.returncode != 0:
                raise DmgBuildError("DMG_VERIFY_FAILED")

            # Publish only a fully verified image. Existing artifact is left
            # untouched on any failure. The caller selected the exact output.
            os.replace(candidate, output)
            print("DMG_VERIFIED_AND_PUBLISHED", flush=True)
            return attempt

    raise DmgBuildError("DMG_CREATE_EXHAUSTED")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        create_verified_dmg(args.app.absolute(), args.output.absolute())
    except DmgBuildError as error:
        parser.exit(2, str(error) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
