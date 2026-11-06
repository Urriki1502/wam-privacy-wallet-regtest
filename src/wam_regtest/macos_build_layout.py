"""Create-only macOS build paths; no wallet or source-checkout copying."""
import argparse
from pathlib import Path


def _plain_absolute(path):
    if (not path.is_absolute() or any(c in str(path) for c in ('\n','\r'))
            or '..' in path.parts):
        raise ValueError('MACOS_BUILD_PATH_DENIED')
    for part in (path,*path.parents):
        if part.is_symlink():raise ValueError('MACOS_BUILD_PATH_DENIED')


def prepare(root,core,output=None):
    from .core import verified_core_paths
    for path in (root,core):_plain_absolute(path)
    if core!=root/'core' and not core.is_relative_to(root/'bundle-input'):
        raise ValueError('MACOS_BUILD_CORE_SCOPE_DENIED')
    verified_core_paths(core)
    target=root if output is None else output
    _plain_absolute(target)
    if output is not None:
        if (not output.is_relative_to(root/'bundle-input')
                or output==root/'bundle-input' or output.exists()):
            raise ValueError('MACOS_BUILD_NEW_OUTPUT_REQUIRED')
    # Refuse before PyInstaller --clean/--noconfirm can overwrite evidence.
    for name in ('build','dist','package-output'):
        path=target/name
        if path.is_symlink() or path.exists() and (not path.is_dir() or any(path.iterdir())):
            raise ValueError('MACOS_BUILD_EXISTING_OUTPUT_DENIED')
    if output is not None:output.mkdir(mode=0o700)
    for name in ('build','dist','package-output'):
        (target/name).mkdir(mode=0o700,exist_ok=True)
    return target


def frozen_environment(environment,platform='offscreen'):
    result={k:v for k,v in environment.items()
            if k not in ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV')
            and not k.startswith(('DYLD_','QT_','QML_','WAM_MACOS_'))}
    result.update(PATH='/usr/bin:/bin:/usr/sbin:/sbin',QT_QPA_PLATFORM=platform)
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--core',type=Path,required=True)
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    prepare(Path.cwd(),a.core,a.output)
    print('MACOS_CREATE_ONLY_BUILD_LAYOUT_PASS')


if __name__=='__main__':main()
