"""Bounded public-fixture Core observations; no wallet/descriptor import.

Reuses original-Popen RPC custody and existing finite method allowlist. Coinbase
admission is measured separately from wallet mature-balance policy. Never retries
financial operations, signals processes or attaches to existing data directories.
"""
from decimal import Decimal
from hashlib import sha256
import argparse
import json
from pathlib import Path
import subprocess
import re
from datetime import datetime, timezone

from wam_regtest.q02_probe import _Node
from wam_regtest.rpc_scope import identity, unregister
from wam_regtest.wsp_live import _pinned_source, REGTEST_GENESIS
from wam_regtest.bip39_12 import PROFILE


def probe(core, source):
    _pinned_source(source)
    from wam_sp.hd import ExtendedPrivate, HARDENED
    from wam_sp.core import Input, pub, hash160
    from wam_sp.codec import encode
    from wam_sp.transaction import p2wpkh, signed_single_input
    from hashlib import pbkdf2_hmac
    # Published BIP84 mnemonic only. Never accept arbitrary seed/user inputs.
    seed=pbkdf2_hmac('sha512',('abandon '*11+'about').encode(),b'mnemonic',2048)
    key=ExtendedPrivate.master(seed).derive((84|HARDENED,1|HARDENED,HARDENED,0,0))
    scalar=int.from_bytes(key.secret,'big')
    address=encode('wamrt',hash160(key.public),bech32m=False)
    node=_Node(core)
    # Preserve this NEW private fixture on success/failure, never erase evidence.
    node.temp._finalizer.detach()
    result={'status':'INCOMPLETE','synthetic_rpc':False,'frozen':False,
            'core_member_sha256':{p.name:sha256(p.read_bytes()).hexdigest() for p in (node.node,node.cli)},
            'new_fixture_only':True,'fixture_directory':str(node.directory),
            'mainnet_allowed':False,'runtime_profile_unchanged':PROFILE,
            'mining_address_public_fixture':address,'owner_shutdown_verified':False}
    try:
        node.start();context=identity(node.directory)
        assert context.binding.process is node.proc
        assert node.call('getblockhash','0')==REGTEST_GENESIS
        info=node.call('getnetworkinfo')
        assert (info['version'],info['subversion'],info['protocolversion'])==(113,'/WAM:0.1.13/',70016)
        result['core_identity']={k:info[k] for k in ('version','subversion','protocolversion')}
        blocks=node.call('generatetoaddress','99',address,timeout=120)
        first=node.call('getblock',blocks[0],'2')['tx'][0]
        outs=[o for o in first['vout'] if o['scriptPubKey']['hex']==p2wpkh(scalar).hex()]
        assert len(outs)==1
        out=outs[0];atoms=Decimal(str(out['value']))*100_000_000
        assert atoms==int(atoms) and atoms==4_750_000_000
        result['height1_miner_atoms']=int(atoms)
        result['height1_coinbase_total_atoms']=int(sum(Decimal(str(o['value'])) for o in first['vout'])*100_000_000)
        assert result['height1_coinbase_total_atoms']==5_000_000_000
        txin=Input(first['txid'],out['n'],p2wpkh(scalar),witness=(b'\x30',key.public),secret=scalar)
        raw=signed_single_input(txin,int(atoms),((int(atoms)-10_000,p2wpkh(31)),),scalar)
        observations=[]
        for depth in (99,100,101):
            if depth!=99:node.call('generatetoaddress','1',address,timeout=120)
            coin=node.call('gettxout',first['txid'],str(out['n']),'true')
            assert coin['confirmations']==depth and coin['coinbase'] is True
            admission=node.call('testmempoolaccept',json.dumps([raw],separators=(',',':')))[0]
            # Raw tx/keys/credentials/node logs are deliberately never receipts.
            observations.append({'depth':depth,'wallet_formula_blocks_remaining':max(0,101-depth),
                                 'next_block_mempool_allowed':admission['allowed'],
                                 'premature_coinbase':admission.get('reject-reason')=='bad-txns-premature-spend-of-coinbase'})
        assert observations[0]['next_block_mempool_allowed'] is False
        assert observations[2]['next_block_mempool_allowed'] is True
        assert node.call('getrawmempool')==[]  # Admission tests did not submit.
        result['maturity_observations']=observations
        result['wallet_balance_rpc_executed']=False
        result['core_validateaddress_executed']=False  # Not in current RPC scope.
        result['no_broadcast']=True
        result['status']='PASS_SCOPED_CORE_OBSERVATIONS'
    except Exception as error:
        result['status']='FAIL_SCOPED_CORE_OBSERVATIONS'
        result['error_class']=type(error).__name__
        result['fixed_error_code']=(error.args[0] if len(error.args)==1
            and type(error.args[0]) is str and re.fullmatch('[A-Z0-9_]{1,100}',error.args[0])
            else 'CORE_COMPATIBILITY_OBSERVATION_FAILED')
    finally:
        if node.proc is not None and node.proc.poll() is None:
            # Authenticated shutdown of this original Popen only. No kill fallback.
            try:
                node.call('stop',timeout=5)
                node.proc.wait(timeout=20)
            except Exception:
                result['status']='BLOCKED_ORIGINAL_OWNER_SHUTDOWN_UNVERIFIED'
                result['retained_original_process_pid']=node.proc.pid
        if node.proc is not None and node.proc.poll() is not None:
            result['owner_shutdown_verified']=True
            unregister(node.directory)
    return result


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--core-dir',type=Path,required=True)
    ap.add_argument('--wsp-source',type=Path,required=True)
    ap.add_argument('--report',type=Path,required=True)
    ap.add_argument('--confirm-disposable-regtest',action='store_true');args=ap.parse_args()
    if not args.confirm_disposable_regtest or args.report.exists():
        ap.error('new report and explicit disposable REGTEST consent required')
    # This research probe does not weaken/call itself the final frozen source
    # gate. Check literal committed Python inputs; separately retain owner docs.
    from wam_regtest.probe_source import _tree, verify_python_tree
    root=Path(__file__).resolve().parents[1]
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    subprocess.run(['git','diff','--quiet','HEAD','--'],cwd=root,check=True)
    tree=_tree(root,head);digests,normalized=verify_python_tree(root,tree,tree)
    result=probe(args.core_dir.resolve(strict=True),args.wsp_source.resolve(strict=True))
    result['source_sha']=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    result['literal_committed_python_sha256']=digests
    result['source_gate_scope']='research-only literal Python; not final frozen attestation'
    result['timestamp_utc']=datetime.now(timezone.utc).isoformat()
    with args.report.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(result['status'])
    if result['status']!='PASS_SCOPED_CORE_OBSERVATIONS':raise SystemExit(1)


if __name__=='__main__':main()
