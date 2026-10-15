"""Cooperating repository-wide engineering lease; never wallet custody."""
import fcntl
import os
from pathlib import Path
import stat
import subprocess
import sys


def main():
    common = Path(subprocess.check_output(
        ['git', 'rev-parse', '--git-common-dir'], text=True).strip()).resolve()
    descriptor = os.open(common / 'wam-engineering.lock',
                         os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        info = os.fstat(descriptor)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600):
            raise ValueError('ENGINEERING_LOCK_METADATA_DENIED')
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('ENGINEERING_ACTIVE_REFUSED', flush=True)
            return 73
        print('ENGINEERING_LEASE_HELD', flush=True)
        if sys.argv[1:] == ['--hold']:
            # TTY EOF/crash or an explicit release closes the OS lease.
            try:
                input()
            except EOFError:
                pass
        elif sys.argv[1:]:
            return 2
        return 0
    finally:
        os.close(descriptor)


if __name__ == '__main__':
    raise SystemExit(main())
