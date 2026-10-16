"""Developer-only genuine Core fixture; never accepts an external .dat path.

Databases stay inside the owned disposable chain and are destroyed on exit.
Only public boolean/category evidence is exported. macOS proof first; this is
not cross-OS import qualification or an operational import entrypoint.
"""
import argparse
from dataclasses import asdict
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys
from wam_regtest.core import _read_cli, verified_core_paths, CoreSmokeError
from wam_regtest.v1_contracts import CoreWalletObservation, core_descriptor_identity, require_unique_core_identity, WalletContractError


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--core',type=Path,required=True)
    parser.add_argument('--wsp-source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--confirm-disposable-regtest',action='store_true')
    a=parser.parse_args()
    if not a.confirm_disposable_regtest or sys.platform!='darwin':
        raise ValueError('V1_NATIVE_FIXTURE_SCOPE_DENIED')
    core,source=a.core.resolve(),a.wsp_source.resolve()
    spec=importlib.util.spec_from_file_location('owned_audit_fixture',Path(__file__).with_name('owner_acceptance.py'))
    driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
    _,cli,receipt=verified_core_paths(core)
    with driver.isolated_chain(core,source) as (data,_,_):
        prefix=[str(cli),f'-datadir={data}']
        def call(method,*params,wallet=None):
            return _read_cli(prefix+([] if wallet is None else ['-rpcwallet='+wallet])+[method,*map(str,params)],timeout=90)
        chain=call('getblockchaininfo')['chain'];genesis=call('getblockhash',0)
        info=call('getwalletinfo',wallet='test')
        before=CoreWalletObservation.from_rpc(chain=chain,genesis=genesis,wallet_info=info,balances=call('getbalances',wallet='test'))
        address=call('getnewaddress',wallet='test')
        assert address.startswith('wamrt1')
        assert len(call('generatetoaddress',101,address))==101
        before=CoreWalletObservation.from_rpc(chain=chain,genesis=genesis,wallet_info=info,balances=call('getbalances',wallet='test'))
        assert before.trusted_atoms>0 and before.immature_atoms>0
        backup=data/'synthetic-core-backup.dat'
        call('backupwallet',backup,wallet='test')
        raw=backup.read_bytes();assert raw[:16]==b'SQLite format 3\x00'
        digest=sha256(raw).digest();del raw
        identity=core_descriptor_identity(call('listdescriptors','false',wallet='test'))
        call('restorewallet','v1-duplicate',backup)
        duplicate=core_descriptor_identity(call('listdescriptors','false',wallet='v1-duplicate'))
        assert duplicate==identity
        try:require_unique_core_identity(duplicate,{identity})
        except WalletContractError:duplicate_denied=True
        else:raise ValueError('V1_DUPLICATE_APPLICATION_ACCOUNT_ACCEPTED')
        assert call('getaddressinfo',address,wallet='v1-duplicate')['ismine'] is True
        call('unloadwallet','v1-duplicate')
        call('unloadwallet','test')
        call('restorewallet','v1-restored',backup)
        restored_info=call('getwalletinfo',wallet='v1-restored')
        restored=CoreWalletObservation.from_rpc(chain=chain,genesis=genesis,wallet_info=restored_info,balances=call('getbalances',wallet='v1-restored'))
        assert core_descriptor_identity(call('listdescriptors','false',wallet='v1-restored'))==identity
        assert restored==before and call('getaddressinfo',address,wallet='v1-restored')['ismine'] is True
        assert sha256(backup.read_bytes()).digest()==digest
        proof={'platform':receipt['platform'],'network':'regtest','core_sha256':receipt['wamd_sha256'],
               'sqlite_header':True,'native_descriptor_metadata':True,'source_file_unchanged':True,
               'native_backupwallet_restorewallet':True,'core_allows_duplicate_key_wallets':True,'application_descriptor_identity_duplicate_denied':duplicate_denied,
               'original_receive_address_still_owned':True,'balance_categories_preserved':asdict(restored),
               'source_is_owned_generated_fixture':True,'external_file_accepted':False,'synthetic_rpc':False,
               'cross_os_interchange_qualified':False,'production_qualified':False,'mainnet_allowed':False}
    with a.output.open('x') as f:json.dump(proof,f,indent=2);f.write('\n')
    print('V1_MACOS_NATIVE_CORE_SQLITE_FIXTURE_PASS')

if __name__=='__main__':main()
