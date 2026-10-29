"""Build-to-receipt linkage, not a new signing or custody authority.

The outer builder verifies unchanged tracked source before/after PyInstaller
and hashes every final artifact. This bundled stamp identifies those inputs;
it does not assert protection against a compromised build host or same user.
"""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys

NAME='Q05_BUILD_SOURCE.json'


def stage(snapshot,destination):
    from .build_provenance import public_receipt
    value=public_receipt(snapshot,source_head=os.environ.get('WAM_SOURCE_HEAD'),
        dispatch=os.environ.get('GITHUB_EVENT_NAME')=='workflow_dispatch')
    with destination.open('x') as out:json.dump(value,out,sort_keys=True);out.write('\n')
    return value


def validate(value):
    if (type(value) is not dict or value.get('schema')!='wam-build-source/v1'
            or any(type(value.get(k)) is not str or not re.fullmatch('[0-9a-f]{40}',value[k])
                for k in ('source_head_sha','checkout_sha'))
            or type(value.get('native_source_inventory_sha256')) is not str
            or not re.fullmatch('[0-9a-f]{64}',value['native_source_inventory_sha256'])
            or value.get('tracked_source_matches_head') is not True
            or value.get('source_unchanged_across_build') is not True):
        raise ValueError('Q05_FROZEN_SOURCE_STAMP_DENIED')
    return value


def read():
    if not getattr(sys,'frozen',False) or not hasattr(sys,'_MEIPASS'):
        raise ValueError('Q05_FROZEN_RUNTIME_REQUIRED')
    base=Path(sys._MEIPASS)
    # PyInstaller relocates macOS data to Resources; read the regular member,
    # not its Frameworks alias. Do not follow an arbitrary external file link.
    path=(base.parent/'Resources'/NAME if sys.platform=='darwin'
        and base.name=='Frameworks' and base.parent.name=='Contents' else base/NAME)
    if not path.is_file() or path.is_symlink() or not 1<=path.stat().st_size<=65536:
        raise ValueError('Q05_FROZEN_SOURCE_STAMP_DENIED')
    raw=path.read_bytes();v=validate(json.loads(raw))
    executable=Path(sys.executable)
    return {'candidate_source_sha':v['source_head_sha'],'checkout_sha':v['checkout_sha'],
        'build_source_inventory_sha256':v['native_source_inventory_sha256'],
        'bundled_source_stamp_sha256':sha256(raw).hexdigest(),
        'frozen_executable_sha256':sha256(executable.read_bytes()).hexdigest(),
        'outer_artifact_manifest_required':True,'same_uid_host_tamper_proof':False}


def main():
    p=argparse.ArgumentParser();p.add_argument('--stamp',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    stage(json.loads(a.stamp.read_text()),a.output)


if __name__=='__main__':main()
