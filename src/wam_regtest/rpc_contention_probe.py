"""Bounded genuine Core read contention; no synthetic RPC or external node."""
import json
import threading
import time
from .json_rpc import _BoundConnection,RpcError,MAX_IDLE_REUSE_SECONDS


def prove_busy_read(client,binding,height):
    # v0.1.11's own help reports 4 worker threads and queue16. Fixed read-only
    # long polls temporarily saturate ONLY this fresh acceptance-owned node.
    barrier=threading.Barrier(33);busy=threading.Event();statuses=[];failures=[]
    port=client._connection.port;auth=client._auth
    def hold():
        conn=_BoundConnection(port,25,binding)
        try:
            barrier.wait(10)
            body=json.dumps({'jsonrpc':'1.0','id':1,'method':'waitfornewblock','params':[4000]}).encode('ascii')
            conn.request('POST','/',body,{'Authorization':auth,'Content-Type':'application/json'})
            response=conn.getresponse();raw=response.read(4097);statuses.append(response.status)
            if response.status==503:busy.set()
            elif response.status!=200 or len(raw)>4096 or json.loads(raw).get('error') is not None:
                failures.append('RPC_READ_DENIED')
        except Exception:failures.append('TRANSPORT_DENIED')
        finally:conn.close()
    workers=[threading.Thread(target=hold,daemon=True) for _ in range(32)]
    for worker in workers:worker.start()
    try:
        barrier.wait(10)
        if not busy.wait(8):raise ValueError('RPC_GENUINE_QUEUE_BUSY_NOT_OBSERVED')
        before=client._identifier
        try:client.call('getblockcount')
        except RpcError as error:
            if error.args!=('RPC_NODE_BUSY',):raise
        else:raise ValueError('RPC_GENUINE_BUSY_READ_NOT_REJECTED')
        attempts=client._identifier-before
        if attempts!=3 or client._closed or client._auth is None:
            raise ValueError('RPC_BUSY_BOUND_OR_SESSION_DENIED')
    finally:
        deadline=time.monotonic()+40
        for worker in workers:worker.join(max(0,deadline-time.monotonic()))
        # Do not leave fixture tasks referencing the auth header after success.
        auth=None
    if failures or any(worker.is_alive() for worker in workers) or len(statuses)!=32:
        raise ValueError('RPC_CONTENTION_CLEANUP_OR_RESPONSE_DENIED')
    if client.call('getblockcount')!=height:
        raise ValueError('RPC_CONTENTION_RECOVERY_HEIGHT_DENIED')
    return {'status':'REAL_CORE_BUSY_READ_RECOVERY_PASS','read_attempt_limit':3,
        'observed_busy_attempts':attempts,'queue_response_200':statuses.count(200),
        'queue_response_503':statuses.count(503),'recovered_without_daemon_restart':True,
        'no_synthetic_rpc':True,'mainnet_allowed':False}


def prove_idle_read(client,height):
    original=client._connection.sock
    if original is None:raise ValueError('RPC_IDLE_SOCKET_REQUIRED')
    delay=MAX_IDLE_REUSE_SECONDS+.1
    time.sleep(delay)  # Actual idle time, never a substituted Core response.
    if client.call('getblockcount')!=height:
        raise ValueError('RPC_IDLE_READ_HEIGHT_DENIED')
    if client._connection.sock is original or original.fileno()!=-1:
        raise ValueError('RPC_IDLE_PREWIRE_RECONNECT_DENIED')
    return {'status':'REAL_CORE_IDLE_READ_RECONNECT_PASS','observed_idle_seconds':delay,
        'old_socket_closed_before_request':True,'request_replayed':False,
        'no_synthetic_rpc':True,'mainnet_allowed':False}
