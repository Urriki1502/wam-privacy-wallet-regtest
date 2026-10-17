"""Explicit disposable v0.1.11 Core startup acceptance; no existing datadir."""
import argparse,json,subprocess
from datetime import datetime,timezone
from pathlib import Path
from wam_regtest.startup_probe import prove_startup
from wam_regtest.core import verified_core_paths

p=argparse.ArgumentParser()
p.add_argument('--core',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--confirm-disposable-regtest',action='store_true')
a=p.parse_args()
if not a.confirm_disposable_regtest:raise ValueError('STARTUP_FIXTURE_CONSENT_REQUIRED')
head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
core=a.core.resolve();_,_,receipt=verified_core_paths(core)
proof=prove_startup(core)
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==head
proof.update(source_head_sha=head,checkout_sha=head,tested_utc=datetime.now(timezone.utc).isoformat(),
    platform=receipt['platform'],wamd_sha256=receipt['wamd_sha256'],wam_cli_sha256=receipt['wam_cli_sha256'],
    core_version='v0.1.11',owner_data_accessed=False)
with a.output.open('x') as output:json.dump(proof,output,indent=2);output.write('\n')
print('REAL_CORE_OWNED_STARTUP_COLLISION_AND_PREAUTH_PASS')
