"""Actual owned Core proof; guard subprocess/hash entry after HTTP session opens."""
import argparse,importlib.util,json,subprocess,sys
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch
from wam_regtest.json_rpc import ManagedReadRpc,RpcError
from wam_regtest import json_rpc
from wam_regtest.core_process import OwnedCoreBinding
from wam_regtest.owned_rpc_probe import probe_owned_reads


def main():
 p=argparse.ArgumentParser()
 for name in ('core','wsp-source','output'):p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--confirm-disposable-regtest',action='store_true');a=p.parse_args()
 if not a.confirm_disposable_regtest or sys.platform!='darwin':raise ValueError('RPC_FIXTURE_SCOPE_DENIED')
 spec=importlib.util.spec_from_file_location('owned_core_fixture',Path(__file__).with_name('owner_acceptance.py'));d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
 owned=[]
 with d.isolated_chain(a.core.resolve(),a.wsp_source.resolve(),process_observer=owned.append) as (data,_,receipt):
  binding=OwnedCoreBinding(owned[0],a.core.resolve(),data)
  native_proof=probe_owned_reads(owned[0],a.core.resolve(),data,102)
  with ManagedReadRpc(a.core.resolve(),data,authorized_readonly=True,binding=binding) as client:
   with patch('subprocess.run',side_effect=AssertionError('RPC_SPAWN_FORBIDDEN')),patch('wam_regtest.core_process.verified_core_paths',side_effect=AssertionError('RPC_REHASH_FORBIDDEN')):
    for _ in range(8):assert client.call('getblockcount')==102
    assert client.call('getblockchaininfo')['chain']=='regtest'
    before=client._identifier
    try:client.call('stop')
    except RpcError as error:assert error.args==('RPC_READ_SCOPE_DENIED',)
    else:raise ValueError('RPC_WRITE_ACCEPTED')
    assert client._identifier==before and repr(client)=='<ManagedReadRpc redacted>'
  bad=ManagedReadRpc(a.core.resolve(),data,authorized_readonly=True,binding=binding)
  try:
   bad._auth='Basic aW52YWxpZDppbnZhbGlk'
   try:bad.call('getblockcount')
   except RpcError as error:assert error.args==('RPC_AUTHENTICATION_DENIED',)
   else:raise ValueError('RPC_INVALID_AUTH_ACCEPTED')
  finally:bad.close()
  proof={'native_process_proof':native_proof,'task_ids':['T-01','T-02','T-03','T-04'],'scope':'initial read-only managed-session component; not complete P0 acceptance',
   'source_sha':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
   'module_sha256':sha256(Path(json_rpc.__file__).read_bytes()).hexdigest(),'platform':receipt['platform'],
   'core_sha256':receipt['wamd_sha256'],'wam_cli_sha256':receipt['wam_cli_sha256'],
   'real_authenticated_http_regtest':True,'genesis_verified':True,'repeated_reads':8,
   'subprocess_and_rehash_forbidden_after_session_open':True,'write_denied_before_wire':True,
   'genuine_core_invalid_auth_denied':True,'synthetic_rpc':False,'owner_data_accessed':False,
   'scanner_gui_integrated':False,'owned_pid_image_and_established_socket_verified_before_auth':True,'hardened_loader_attestation_qualified':False,
   'frozen_feature_qualified':False,'physical_accepted':False,'mainnet_allowed':False,'production_qualified':False}
 with a.output.open('x') as f:json.dump(proof,f,indent=2);f.write('\n')
 print('ISSUE45_MACOS_REAL_CORE_AUTHENTICATED_HTTP_READ_COMPONENT_PASS')

if __name__=='__main__':main()
