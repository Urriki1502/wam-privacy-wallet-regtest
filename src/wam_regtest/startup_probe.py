"""Actual Core startup collisions; instrumentation never synthesizes RPC data."""
from contextlib import contextmanager, ExitStack
import socket
import sys
from pathlib import Path
from unittest.mock import patch
from . import owned_start
from .core import CoreSmokeError


def prove_startup(core):
    blockers=[];processes=[];directories=[];allocator=owned_start._reserved_ports
    def raw_bytes():
        received=0
        for server in blockers:
            server.settimeout(.05)
            while True:
                try:connection,_=server.accept()
                except socket.timeout:break
                with connection:
                    connection.settimeout(.1)
                    try:received+=len(connection.recv(65536))
                    except socket.timeout:pass
        return received

    def collisions(count):
        calls=[]
        @contextmanager
        def reserve():
            with allocator() as ports:
                calls.append(ports);yield ports
            if len(calls)<=count:
                server=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
                try:
                    if sys.platform=='win32':server.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
                    server.bind(('127.0.0.1',ports[0]));server.listen(8)
                except BaseException:server.close();raise
                blockers.append(server)
        return calls,reserve
    original_reap=owned_start._reap
    def observed_reap(process):
        if process is not None:
            processes.append(process);directories.append(Path(process.args[1][9:]))
        original_reap(process)
    guards=ExitStack()
    guards.enter_context(patch.object(owned_start,'_reap',observed_reap))
    guards.enter_context(patch('wam_regtest.core._read_cli',side_effect=AssertionError('STARTUP_CLI_FORBIDDEN')))
    try:
        calls,reserve=collisions(1)
        with patch.object(owned_start,'_reserved_ports',reserve):
            with owned_start.disposable_core(core,authorized=True) as running:
                assert running.attempts==2 and len(calls)==2
                assert running.read.call('getblockcount')==0
                assert running.read.attest()['chain']=='regtest'
        assert all(p.poll() is not None for p in processes)
        assert not any(p.exists() for p in directories)
        first_bytes=raw_bytes();assert first_bytes==0
        for server in blockers:server.close()
        blockers.clear()
        calls,reserve=collisions(99)
        with patch.object(owned_start,'_reserved_ports',reserve):
            try:
                with owned_start.disposable_core(core,authorized=True):raise AssertionError('COLLISION_ACCEPTED')
            except CoreSmokeError as error:
                assert error.args==('CORE_START_PORT_RETRIES_EXHAUSTED',)
        assert len(calls)==3 and raw_bytes()==0
        # A post-start failure is NOT a startup collision or reason to restart.
        calls,reserve=collisions(0)
        with patch.object(owned_start,'_reserved_ports',reserve):
            try:
                with owned_start.disposable_core(core,authorized=True) as running:
                    raise CoreSmokeError('PUBLIC_TEST_OPERATION_FAILURE')
            except CoreSmokeError as error:assert error.args==('PUBLIC_TEST_OPERATION_FAILURE',)
        assert len(calls)==1 and len(processes)==6 and all(p.poll() is not None for p in processes)
        assert not any(p.exists() for p in directories)
        return {'status':'REAL_CORE_OWNED_STARTUP_COLLISION_AND_PREAUTH_PASS',
            'one_collision_attempts':2,'exhaustion_attempts':3,
            'competing_listener_received_bytes':0,'post_start_failure_restarted':False,
            'owned_processes_reaped':True,'observed_processes_reaped':len(processes),
            'startup_without_cli':True,'temporary_datadirs_removed':True,
            'synthetic_rpc':False,'mainnet_allowed':False,'persistent_lifecycle_qualified':False}
    finally:
        for server in blockers:server.close()
        guards.close()
