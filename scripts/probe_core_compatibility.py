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
import platform
from datetime import datetime, timezone

from wam_regtest.q02_probe import _Node
from wam_regtest.rpc_scope import identity, reauthenticate_owned, unregister
from wam_regtest.wsp_live import _pinned_source, REGTEST_GENESIS
from wam_regtest.bip39_12 import PROFILE


def _p2pkh_script_from_base58(text):
    """Independent stdlib base58check decode; pinned regtest PUBKEY_ADDRESS=65."""
    alphabet='123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    value=0
    for c in text:value=value*58+alphabet.index(c)
    raw=value.to_bytes(25,'big')
    if (len(text)-len(text.lstrip('1'))) or sha256(sha256(raw[:21]).digest()).digest()[:4]!=raw[21:]:
        raise ValueError('TREASURY_BASE58_DENIED')
    if raw[0]!=65:
        raise ValueError('TREASURY_VERSION_DENIED')
    # The pinned regtest comment claims a zero-hash160 burn; the literal is a
    # real key hash. Record the discrepancy, never assume unspendability.
    return b'\x76\xa9\x14'+raw[1:21]+b'\x88\xac'


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
    result['public_mining_script_pubkey']=p2wpkh(scalar).hex()
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
        # Q11 ownership: treasury output must be the regtest burn script decoded
        # independently from the pinned chainparams literal, never our miner.
        treasury_script=_p2pkh_script_from_base58('TQkMCz4r2oWuFjAu8mAeGYDMuz4BNkmofz')
        result['treasury_script_pubkey']=treasury_script.hex()
        result['treasury_hash160_is_zero_burn']=treasury_script[3:23]==bytes(20)
        result['upstream_regtest_comment_claims_zero_hash160_burn']=True
        def split(height):
            tx=node.call('getblock',node.call('getblockhash',str(height)),'2')['tx'][0]
            assert 'coinbase' in tx['vin'][0]
            paid={}
            for o in tx['vout']:
                value=Decimal(str(o['value']))*100_000_000
                assert value==int(value)
                if int(value):paid[o['scriptPubKey']['hex']]=paid.get(o['scriptPubKey']['hex'],0)+int(value)
            return paid
        node.call('generatetoaddress','50',address,timeout=120)  # Height 151, regtest halving 150.
        boundary=[]
        for height,total in ((1,5_000_000_000),(150,5_000_000_000),(151,2_500_000_000)):
            paid=split(height)
            treasury=total*5//100
            assert paid=={p2wpkh(scalar).hex():total-treasury,treasury_script.hex():treasury},(height,paid)
            boundary.append({'height':height,'total_atoms':total,'miner_atoms':total-treasury,
                             'treasury_atoms':treasury,'miner_owned':True,'treasury_owned_by_miner':False})
        result['regtest_subsidy_treasury_boundary']=boundary
        # Integer maturity accounting for the public fixture miner coinbases,
        # oracle from Core gettxout depth only (Core wallet balance RPC is not
        # in the finite allowlist, so Core-wallet spendability is NOT observed).
        tip=node.call('getblockcount');mature=immature=0;rows=[]
        for height in (1,50,51,52,100,150,151):
            tx=node.call('getblock',node.call('getblockhash',str(height)),'2')['tx'][0]
            mine_out=[o for o in tx['vout'] if o['scriptPubKey']['hex']==p2wpkh(scalar).hex()][0]
            coin=node.call('gettxout',tx['txid'],str(mine_out['n']),'true')
            depth=coin['confirmations'];assert depth==tip-height+1 and coin['coinbase'] is True
            value=Decimal(str(coin['value']))*100_000_000;assert value==int(value)
            remaining=max(0,101-depth)
            mature+=int(value) if remaining==0 else 0;immature+=int(value) if remaining else 0
            rows.append({'height':height,'depth':depth,'atoms':int(value),'blocks_remaining':remaining})
        assert tip==151 and [r['depth'] for r in rows]==[151,102,101,100,52,2,1]
        assert [r['blocks_remaining'] for r in rows]==[0,0,0,1,49,99,100]
        assert mature==3*4_750_000_000 and immature==3*4_750_000_000+2_375_000_000
        result['maturity_accounting_oracle']={'tip':tip,'rows':rows,'mature_atoms':mature,'immature_atoms':immature,
            'fusion_bip352_balance_includes_coinbase':False,'reason':'WSP Scanner skips coinbase; BIP352 cannot pay coinbase'}
        # Q13 genuine Core parser (via allowlisted generatetoaddress): positive
        # v1 bech32m, Core-wallet encoder vector, and malformed-but-wamrt1 negatives.
        from wam_sp.codec import ALPHABET, bits as codec_bits, expand, polymod
        result['parser_stage']='POSITIVE_V1_AND_CORE_WALLET'
        before=node.call('getblockcount')
        # Public BIP341 generator x-coordinate as a v1 witness program (fixture only).
        taproot=encode('wamrt',bytes.fromhex('79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798'),version=1)
        node.call('generatetoaddress','1',taproot,timeout=60)
        node.call('createwallet','test');core_address=node.call('-rpcwallet=test','getnewaddress')
        assert re.fullmatch('wamrt1q[023456789acdefghjklmnpqrstuvwxyz]{38}',core_address)
        data=[ALPHABET.index(c) for c in core_address[len('wamrt1'):]]
        assert polymod(expand('wamrt')+data)==1 and data[0]==0  # BIP173 bech32, witness v0.
        program=bytes(codec_bits(data[1:-6],5,8,False));assert len(program)==20
        assert encode('wamrt',program,version=0,bech32m=False)==core_address
        node.call('generatetoaddress','1',core_address,timeout=60)
        assert node.call('getblockcount')==before+2
        negatives={}
        flip=lambda s:s[:-1]+('q' if s[-1]!='q' else 'p')
        for name,candidate in [('bad_checksum',flip(address)),
                               ('v0_with_bech32m_checksum',encode('wamrt',hash160(key.public),version=0,bech32m=True)),
                               ('v1_with_bech32_checksum',encode('wamrt',bytes(32),version=1,bech32m=False)),
                               ('v0_21_byte_program',encode('wamrt',bytes(21),version=0,bech32m=False))]:
            result['parser_stage']='NEGATIVE_'+name
            try:node.call('generatetoaddress','1',candidate,timeout=60)
            except Exception:
                negatives[name]='CORE_REJECTED'
                # By design any Core RPC error latches the owned scope fault.
                # Explicit fresh attestation of the SAME original process only.
                assert identity(node.directory).faulted is True
                reauthenticate_owned(node.directory,authorized=True)
                assert identity(node.directory).faulted is False
            else:negatives[name]='CORE_ACCEPTED'
        assert node.call('getblockcount')==before+2
        result['parser_stage']='DONE'
        assert set(negatives.values())=={'CORE_REJECTED'},negatives
        result['core_address_parser']={'v1_bech32m_accepted':True,'core_wallet_bech32_vector':core_address,
            'wsp_codec_roundtrip_of_core_encoder':True,'negatives':negatives,
            'wrong_network_not_sent_to_core':'Fusion route() regex admits only lowercase wamrt1',
            'core_rejection_latches_owned_scope_fault':True,'explicit_reauthentication_per_rejection':True}
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
                context=identity(node.directory)
                if context is not None and context.faulted:
                    # Explicit fresh attestation of the SAME original Popen, only to
                    # reach authenticated shutdown; never a wallet or write grant.
                    reauthenticate_owned(node.directory,authorized=True)
                    result['shutdown_after_explicit_reauthentication']=True
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
    subprocess.run(['git','diff','--quiet','HEAD','--'],cwd=root,check=True)
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()!=head:
        raise ValueError('CORE_COMPATIBILITY_SOURCE_CHANGED')
    after,_=verify_python_tree(root,tree,tree)
    if after!=digests:raise ValueError('CORE_COMPATIBILITY_SOURCE_CHANGED')
    result['source_sha']=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    result['literal_python_unchanged_across_probe']=True
    result['wsp_source_commit']='ac55f13423620252bdbf848c7e8a280c3b84721e'
    result['host']={'os':platform.system(),'arch':platform.machine()}
    result['literal_committed_python_sha256']=digests
    result['source_gate_scope']='research-only literal Python; not final frozen attestation'
    result['timestamp_utc']=datetime.now(timezone.utc).isoformat()
    with args.report.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(result['status'])
    if result['status']!='PASS_SCOPED_CORE_OBSERVATIONS':raise SystemExit(1)


if __name__=='__main__':main()
