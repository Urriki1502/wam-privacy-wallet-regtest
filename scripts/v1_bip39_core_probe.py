"""Real Core -> BIP39-derived native WSP -> SQLite restart, no mnemonic output."""
import argparse
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys
from wam_regtest.bip39_wallet import Bip39RegtestKeys,generate_phrase
from wam_regtest.wallet_session import WalletCoreCli
from wam_regtest.core import verified_core_paths
from wam_regtest.wsp_live import _public_fixture_payment


def main():
    p=argparse.ArgumentParser()
    for name in ('core','wsp-source','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--confirm-disposable-regtest',action='store_true');a=p.parse_args()
    if not a.confirm_disposable_regtest or sys.platform!='darwin':raise ValueError('BIP39_NATIVE_FIXTURE_SCOPE_DENIED')
    core,source=a.core.resolve(),a.wsp_source.resolve()
    spec=importlib.util.spec_from_file_location('owned_audit_fixture',Path(__file__).with_name('owner_acceptance.py'))
    driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
    from wam_sp.scanner import Scanner
    from wam_regtest import bip39_wallet
    _,cli,receipt=verified_core_paths(core)
    with driver.isolated_chain(core,source) as (data,mining,_):
        phrase=generate_phrase(24,authorized_disposable=True)
        with Bip39RegtestKeys(phrase,source=source,authorized_disposable=True) as keys,Bip39RegtestKeys(phrase,source=source,authorized_disposable=True) as restored:
            assert keys.public_metadata()==restored.public_metadata()
            account=keys.scan_account();rpc=WalletCoreCli(cli,data);rpc.attest()
            txid,atoms,height=_public_fixture_payment(rpc,account,mining,funding_height=2,expected_before_height=102)
            scans=[]
            try:
                for name,ring in [('original',keys),('restored',restored)]:
                    scanner=Scanner(data/(name+'.sqlite'),(ring.scan_account(),));scans.append(scanner)
                    scanner.sync(rpc);coins=scanner.coins()
                    assert len(coins)==1 and coins[0]['txid']==txid and coins[0]['atoms']==atoms
                before=scans[0].coins();scans[0].close();scans.pop(0)
                reopened=Scanner(data/'original.sqlite',(keys.scan_account(),));scans.append(reopened)
                assert reopened.sync(rpc).blocks==0 and reopened.coins()==before
                proof={'platform':receipt['platform'],'profile':keys.public_metadata()['profile'],
                       'engine_source_sha256':sha256(Path(bip39_wallet.__file__).read_bytes()).hexdigest(),
                       'network':'regtest','full_bip39_seed_bytes':64,'same_restored_native_receive_code':True,
                       'real_core_native_wsp_bip352_payment_confirmed':True,'confirmed_atoms':atoms,
                       'observed_height':height,'independent_original_restored_scanners_agree':True,
                       'sqlite_restart_no_rescan_required':True,'core_sha256':receipt['wamd_sha256'],
                       'synthetic_rpc':False,'mnemonic_exported':False,'database_exported':False,
                       'persistent_custody_integrated':False,'signing_integrated':False,
                       'frozen_feature_qualified':False,'mainnet_allowed':False,'production_qualified':False}
            finally:
                for scanner in scans:scanner.close()
    with a.output.open('x') as f:json.dump(proof,f,indent=2);f.write('\n')
    print('V1_MACOS_BIP39_NATIVE_CORE_WSP_SQLITE_RECEIVE_PASS')

if __name__=='__main__':main()
