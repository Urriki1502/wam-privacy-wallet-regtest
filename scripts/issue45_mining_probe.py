"""Explicit Core fixture acceptance; no external wallet/datadir input."""
import argparse,json,subprocess
from datetime import datetime,timezone
from pathlib import Path
from wam_regtest.mining_probe import probe_core_mining
p=argparse.ArgumentParser()
for n in ('core','wsp-source','output'):p.add_argument('--'+n,type=Path,required=True)
p.add_argument('--gui',action='store_true')
p.add_argument('--confirm-disposable-regtest',action='store_true');a=p.parse_args()
if not a.confirm_disposable_regtest:raise ValueError('MINING_EXPLICIT_CONSENT_REQUIRED')
proof=probe_core_mining(a.core.resolve(),a.wsp_source.resolve(),gui=a.gui)
proof.update(source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),tested_utc=datetime.now(timezone.utc).isoformat(),wsp_commit='ac55f13423620252bdbf848c7e8a280c3b84721e')
with a.output.open('x') as f:json.dump(proof,f,indent=2);f.write('\n')
print('REAL_CORE_REGTEST_MINING_ACCOUNT_MATURITY_PASS')
