"""Disposable copied-binary replacement tests; never mutate original Core.

No mutated executable is launched. CLI bytes are restored before fixture
cleanup, and only the owned daemon is stopped. No wallet database is published.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from wam_regtest.core import verified_core_paths, _read_cli
from wam_regtest.core_process import OwnedCoreBinding
from wam_regtest.json_rpc import ManagedReadRpc, RpcError


def refused(client, codes):
    try: client.call('getblockcount')
    except RpcError as error:
        if error.args[0] not in codes or not client._closed:
            raise ValueError('EXEC_PROBE_NOT_QUARANTINED') from None
        return error.args[0]
    raise ValueError('EXEC_PROBE_CHANGED_PROCESS_ACCEPTED')


def main():
    parser=argparse.ArgumentParser()
    for name in ('core','wsp-source','output'): parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--confirm-disposable-regtest',action='store_true');args=parser.parse_args()
    if not args.confirm_disposable_regtest or sys.platform!='darwin':raise ValueError('EXEC_FIXTURE_SCOPE_DENIED')
    core=args.core.resolve();source=args.wsp_source.resolve()
    node,cli,receipt=verified_core_paths(core)
    spec=importlib.util.spec_from_file_location('owned_fixture',Path(__file__).with_name('owner_acceptance.py'))
    fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
    with tempfile.TemporaryDirectory(prefix='wam-exec-copy-') as temp:
        stage=Path(temp).resolve()/'core';stage.mkdir(mode=0o700)
        for original in (node,cli,core/'receipt.json'):shutil.copy2(original,stage/original.name)
        owned=[]
        with fixture.isolated_chain(stage,source,process_observer=owned.append) as (data,_,_):
            def open_client():
                return ManagedReadRpc(stage,data,authorized_readonly=True,
                    binding=OwnedCoreBinding(owned[0],stage,data))
            copied_cli=stage/cli.name;original_cli=copied_cli.read_bytes()
            with open_client() as client:
                try:
                    with copied_cli.open('ab') as out:out.write(b'PUBLIC_TAMPER_TEST')
                    cli_denial=refused(client,{'RPC_EXECUTABLE_CHANGED'})
                finally:copied_cli.write_bytes(original_cli)
            # New binary bytes cannot inherit an authenticated session, even
            # when replacement is an exact copy of the independently pinned file.
            copied_node=stage/node.name;detached=stage/(node.name+'.detached')
            with open_client() as client:
                copied_node.rename(detached)
                try:
                    shutil.copy2(node,copied_node)
                    node_denial=refused(client,{'RPC_EXECUTABLE_CHANGED','RPC_PROCESS_IMAGE_DENIED'})
                finally:
                    if copied_node.exists():copied_node.unlink()
                    detached.rename(copied_node)
            with open_client() as client:
                assert client.call('getblockcount')==102
                _read_cli([str(copied_cli),f'-datadir={data}','stop']);owned[0].wait(timeout=20)
                exit_denial=refused(client,{'RPC_OWNED_PROCESS_EXITED'})
    # Independently rehash originals after all tests; never touched by mutations.
    _,_,after=verified_core_paths(core)
    assert after==receipt
    proof={'scope':'Mac copied-executable trust-session failure paths; not hardened loader qualification',
        'source_sha':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'executed_utc':datetime.now(timezone.utc).isoformat(),'platform':receipt['platform'],
        'core_sha256':receipt['wamd_sha256'],'wam_cli_sha256':receipt['wam_cli_sha256'],
        'wsp_source':'ac55f13423620252bdbf848c7e8a280c3b84721e',
        'module_sha256':{n:sha256(Path('src/wam_regtest',n).read_bytes()).hexdigest()
                         for n in ('core_process.py','json_rpc.py')},
        'copied_cli_tamper_denial':cli_denial,'copied_node_replacement_denial':node_denial,
        'owned_process_exit_denial':exit_denial,'refused_sessions_quarantined':True,
        'original_core_pair_unchanged':True,'mutated_executable_launched':False,
        'synthetic_rpc':False,'owner_data_accessed':False,'mainnet_allowed':False,
        'frozen_qualified':False,'physical_accepted':False}
    with args.output.open('x') as out:json.dump(proof,out,indent=2);out.write('\n')
    print('MACOS_REAL_CORE_COPIED_EXECUTABLE_FAILURE_PATHS_PASS')


if __name__=='__main__':main()
