"""Reproducible WSP source corpus manifest for self-contained macOS REGTEST app.

Executed only in macOS GitHub packaging job after the immutable WSP git
checkout is confirmed. The full reviewed source is preserved and rehashed
at launch, without importing system Python or running git in Finder.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from .wsp_live import PINNED_WSP_COMMIT


class PackageSourceError(ValueError):
    pass


def stage_pinned_wsp(source: Path, destination: Path) -> dict:
    if (not source.is_absolute() or not destination.is_absolute()
            or destination.exists() or destination.is_symlink()):
        raise PackageSourceError("BUNDLE_WSP_SCOPE_DENIED")
    try:
        result = subprocess.run(
            ["git", "-C", str(source), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True, timeout=10,
        )
        if result.stdout.strip() != PINNED_WSP_COMMIT:
            raise PackageSourceError("BUNDLE_WSP_PIN_DENIED")
        dirty = subprocess.run(
            ["git", "-C", str(source), "status", "--porcelain", "--untracked-files=no"],
            capture_output=True, text=True, check=True, timeout=10,
        )
        if dirty.stdout.strip():
            raise PackageSourceError("BUNDLE_WSP_WORKTREE_DENIED")
        source_pkg = source / "src" / "wam_sp"
        paths = sorted(source_pkg.rglob("*.py"))
        if not 2 <= len(paths) <= 200:
            raise PackageSourceError("BUNDLE_WSP_CLOSURE_DENIED")
        destination.mkdir(mode=0o700, parents=True)
        digest = {}
        for path in paths:
            if path.is_symlink() or not path.is_file():
                raise PackageSourceError("BUNDLE_WSP_MEMBER_DENIED")
            rel = path.relative_to(source).as_posix()
            target = destination / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            data = path.read_bytes()
            target.write_bytes(data)
            digest[rel] = hashlib.sha256(data).hexdigest()
        record = {
            "source_commit": PINNED_WSP_COMMIT,
            "files": digest,
        }
        (destination / "SOURCE_SHA256.json").write_text(
            json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
        )
        return record
    except PackageSourceError:
        raise
    except (OSError, subprocess.SubprocessError, ValueError):
        raise PackageSourceError("BUNDLE_WSP_STAGE_DENIED") from None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = stage_pinned_wsp(
            args.source_root.expanduser().resolve(),
            args.output.expanduser().absolute(),
        )
    except PackageSourceError as exc:
        parser.exit(2, str(exc) + "\n")
    print(f"BUNDLED_PINNED_WSP_SOURCE_PASS file_count={len(result['files'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
