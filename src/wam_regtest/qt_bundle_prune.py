"""Drop Qt shared libraries that no kept ELF needs.

libQt6Test stays: frozen Q06 spend imports PySide6.QtTest.
libXcursor and libxcb-cursor stay: they are the X11 cursor libraries.
"""
from pathlib import Path
import re
import subprocess


CANDIDATE_PREFIXES = (
    'libQt6Qml', 'libQt6Quick', 'libQt6Pdf', 'libQt6VirtualKeyboard',
)
KEPT_EVEN_IF_UNREFERENCED = ('libQt6Test', 'libXcursor', 'libxcb-cursor')


def is_prune_candidate(name):
    if name.startswith(KEPT_EVEN_IF_UNREFERENCED) or 'cursor' in name.lower():
        return False
    return name.startswith(CANDIDATE_PREFIXES)


def unreferenced_candidates(needed, candidates):
    """needed maps a filename to the sonames it lists. candidates are filenames."""
    reachable = set()
    pending = [name for name in needed if name not in candidates]
    while pending:
        current = pending.pop()
        for soname in needed.get(current, ()):
            if soname in candidates and soname not in reachable:
                reachable.add(soname)
                pending.append(soname)
    return set(candidates) - reachable


def _needed(path):
    header = path.read_bytes()[:4]
    if header != b'\x7fELF':
        return None
    dynamic = subprocess.check_output(
        ['/usr/bin/readelf', '-dW', str(path)],
        env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'}, timeout=15, text=True)
    return re.findall(r'\(NEEDED\).*\[([^\]]+)\]', dynamic)


def prune_unreferenced_qt(bundle):
    root = Path(bundle)
    needed = {}
    candidates = set()
    paths = {}
    for path in root.rglob('*'):
        if not path.is_file() or path.is_symlink():
            continue
        sonames = _needed(path)
        if sonames is None:
            continue
        needed[path.name] = sonames
        paths.setdefault(path.name, path)
        if is_prune_candidate(path.name):
            candidates.add(path.name)
    remove = unreferenced_candidates(needed, candidates)
    for name in sorted(remove):
        paths[name].unlink()
    return {'removed': tuple(sorted(remove)), 'kept_candidates': tuple(sorted(candidates - remove))}
