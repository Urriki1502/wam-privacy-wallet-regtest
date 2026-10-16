"""Opted-in disposable acceptance only; never an interactive startup probe.

The negative endpoint is a byte collector, not a synthetic Core RPC server.
It must receive NO HTTP bytes. Positive results come only from genuine Core.
"""
import socket
import threading
from .core_process import OwnedCoreBinding
from .json_rpc import ManagedReadRpc, RpcError, _BoundConnection


def probe_owned_reads(process, core, directory, height):
    binding = OwnedCoreBinding(process, core, directory)
    with ManagedReadRpc(core, directory, authorized_readonly=True, binding=binding) as client:
        info=client.call('getnetworkinfo')
        rpc_profile={k:info[k] for k in ('version','subversion','protocolversion')}
        for _ in range(8):
            if client.call('getblockcount') != height:
                raise ValueError('RPC_PROBE_HEIGHT_DENIED')
        before = client._identifier
        try:
            client.call('stop')
        except RpcError as error:
            if error.args != ('RPC_READ_SCOPE_DENIED',): raise
        else: raise ValueError('RPC_PROBE_WRITE_ACCEPTED')
        if client._identifier != before: raise ValueError('RPC_PROBE_WRITE_SENT')
    with ManagedReadRpc(core, directory, authorized_readonly=True, binding=binding) as client:
        client._auth = 'Basic aW52YWxpZDppbnZhbGlk'
        try:
            client.call('getblockcount')
        except RpcError as error:
            if error.args != ('RPC_AUTHENTICATION_DENIED',): raise
        else: raise ValueError('RPC_PROBE_INVALID_AUTH_ACCEPTED')
    received = []; failures = []
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(('127.0.0.1', 0)); listener.listen(1); listener.settimeout(5)
        def collect():
            try:
                with listener.accept()[0] as peer:
                    peer.settimeout(5); received.append(peer.recv(8192))
            except Exception: failures.append(True)
        thread = threading.Thread(target=collect, daemon=True); thread.start()
        connection = _BoundConnection(listener.getsockname()[1], 5, binding)
        try:
            try:
                connection.request('POST', '/', b'{}', {'Authorization': 'Basic PUBLIC_TEST_CANARY'})
            except RpcError as error:
                if error.args != ('RPC_ENDPOINT_OWNER_DENIED',): raise
            else: raise ValueError('RPC_PROBE_WRONG_PROCESS_ACCEPTED')
        finally:
            connection.close(); thread.join(6)
        if thread.is_alive() or failures or received != [b'']:
            raise ValueError('RPC_PROBE_PREAUTH_LEAK_OR_CLEANUP_DENIED')
    return {
        'status': 'REAL_CORE_OWNED_HTTP_READ_COMPONENT_PASS',
        'rpc_compatibility_profile': rpc_profile,
        'repeated_authenticated_reads': 8, 'height': height,
        'process_image_and_established_socket_before_auth': True,
        'wrong_process_endpoint_denied_before_any_http_bytes': True,
        'genuine_core_invalid_auth_denied': True, 'write_denied_before_wire': True,
        'synthetic_core_rpc': False, 'scanner_gui_transport_integrated': False,
        'hardened_loader_attestation_qualified': False, 'mainnet_allowed': False,
    }
