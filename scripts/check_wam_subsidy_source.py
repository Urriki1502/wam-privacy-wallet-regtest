"""Native SOURCE-contract only; never a substitute for genuine Core E2E.

Compile unchanged pinned upstream functions against explicitly documented type/
parameter shims. No node is built/modified, no network/mainnet is started.
"""
import argparse
from datetime import datetime,timezone
from hashlib import sha1,sha256
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

PINS={'wam-params.h':'d798155e1964adbdb3ccc48b44dd48fcde3b1602',
      'consensus/subsidy.cpp':'5659e868f191f2c497950d690829f0369aa912d1',
      'consensus/subsidy.h':'43e2e8c11a58b1b56141c63de470acb4743544ad'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    root=Path(__file__).resolve().parents[1];tests=root/'tests/source_contract';base=tests/'v0.1.11/wam'
    for name,expected in PINS.items():
        raw=(base/name).read_bytes()
        if sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()!=expected:
            raise ValueError('UPSTREAM_SUBSIDY_SOURCE_PIN_DENIED')
    compiler=next((found for n in ('c++','g++','clang++') if (found:=shutil.which(n))),None)
    if compiler is None:raise ValueError('NATIVE_CXX_SOURCE_CONTRACT_PENDING_COMPILER_REQUIRED')
    with tempfile.TemporaryDirectory(prefix='wam-source-contract-') as directory:
        exe=Path(directory)/('vectors.exe' if sys.platform=='win32' else 'vectors')
        command=[compiler,'-std=c++17','-O2','-I'+str(tests/'v0.1.11'),'-I'+str(tests/'shims'),
                 str(base/'consensus/subsidy.cpp'),str(tests/'check.cpp'),'-o',str(exe)]
        if sys.platform=='win32' and 'clang' not in Path(compiler).name:command+=['-static-libstdc++','-static-libgcc']
        built=subprocess.run(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
        if built.returncode:
            # Public compiler diagnostics only; no wallet/config/secret inputs.
            sys.stderr.write(built.stderr.decode('utf8',errors='replace')[:8000]);raise ValueError('NATIVE_SOURCE_COMPILE_DENIED')
        done=subprocess.run([str(exe)],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
        if done.returncode or not 1<=len(done.stdout)<=16384:raise ValueError('NATIVE_SUBSIDY_CONTRACT_DENIED')
        record=json.loads(done.stdout)
    record.update(upstream_tag='v0.1.11',upstream_blobs=PINS,
        source_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        tested_utc=datetime.now(timezone.utc).isoformat(),os=platform.system(),architecture=platform.machine(),
        compiler=Path(compiler).name,shims_are_not_core_consensus_validation=True,
        test_driver_sha256=sha256((tests/'check.cpp').read_bytes()).hexdigest(),mainnet_allowed=False,
        frozen_qualified=False,physical_accepted=False)
    with args.output.open('x') as out:json.dump(record,out,indent=2);out.write('\n')
    print('PINNED_WAM_SUBSIDY_SOURCE_CONTRACT_PASS_NOT_CORE_E2E')

if __name__=='__main__':main()
