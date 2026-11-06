"""Compile unchanged pinned upstream monetary functions in a type-stub harness.

Scoped deterministic source vectors only: NOT a Core rebuild, chain simulation,
or a proof of actual binary behavior at height400000. No consensus source edits.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess

PINS = {
    'subsidy.cpp':'b41b6da8b674519ee770cc8fd564e5b128335619863d3d335889783008eb54fe',
    'subsidy.h':'9f106a946d5789a40bd41ba07cb4c43938bd1460a3de076b4dadc44de6934a22',
    'wam-params.h':'d0e49ffe1693da9f462d94dc3e004c024ffd1f2d4ebdf9d48c31ae3c9851020d',
}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source-dir',type=Path,required=True)
    ap.add_argument('--output-dir',type=Path,required=True);args=ap.parse_args()
    for name,digest in PINS.items():
        p=args.source_dir/name
        if p.is_symlink() or sha256(p.read_bytes()).hexdigest()!=digest:
            raise ValueError('SUBSIDY_PINNED_SOURCE_REQUIRED')
    out=args.output_dir;out.mkdir(mode=0o700)
    inc=out/'include';(inc/'wam/consensus').mkdir(parents=True);(inc/'consensus').mkdir()
    for src,dst in [('subsidy.h','wam/consensus/subsidy.h'),('wam-params.h','wam/wam-params.h')]:
        shutil.copyfile(args.source_dir/src,inc/dst)
    (inc/'consensus/amount.h').write_text('#pragma once\n#include <cstdint>\nusing CAmount = int64_t;\n')
    (inc/'consensus/params.h').write_text('#pragma once\nnamespace Consensus { struct Params { int nSubsidyHalvingInterval; }; }\n')
    harness=out/'vectors.cpp'
    harness.write_text('''#include <wam/consensus/subsidy.h>
#include <consensus/params.h>
#include <iostream>
int main() {
    Consensus::Params params{200000};
    for (int height : {1,200000,200001,400000,400001,600000,600001}) {
        auto total=wam::GetBlockSubsidy(height,params);
        auto treasury=wam::GetDevFeeAmount(total,height);
        auto miner=wam::GetMinerSubsidy(total,height);
        std::cout<<height<<" "<<total<<" "<<treasury<<" "<<miner<<"\\n";
    }
}
''')
    executable=out/'vectors'
    subprocess.run(['clang++','-std=c++17','-I'+str(inc),str(args.source_dir/'subsidy.cpp'),str(harness),'-o',str(executable)],check=True)
    rows=[list(map(int,line.split())) for line in subprocess.check_output([str(executable)],text=True).splitlines()]
    expected=[[1,5000000000,250000000,4750000000],[200000,5000000000,250000000,4750000000],
              [200001,2500000000,125000000,2375000000],[400000,2500000000,125000000,2375000000],
              [400001,1250000000,0,1250000000],[600000,1250000000,0,1250000000],[600001,625000000,0,625000000]]
    assert rows==expected,'SUBSIDY_SOURCE_VECTOR_MISMATCH'
    receipt={'status':'PASS_SCOPED_UNCHANGED_UPSTREAM_SOURCE_VECTORS',
             'upstream_commit':'b3fb899ddb1ceab7e9b3b12ccd034ad1b4be8186',
             'source_pins_sha256':PINS,'minimal_type_stubs':True,
             'core_binary_executed':False,'columns':['height','total_atoms','treasury_atoms','miner_atoms'],
             'rows':rows,'harness_sha256':sha256(harness.read_bytes()).hexdigest()}
    with (out/'receipt.json').open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
    print(receipt['status'])


if __name__=='__main__':main()
