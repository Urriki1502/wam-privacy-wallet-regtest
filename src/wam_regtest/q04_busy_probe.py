"""Disposable genuine-Core queue probe; never injects a Fusion busy response."""
import base64
from concurrent.futures import ThreadPoolExecutor
import http.client
import json
import time

from .external_core import ExternalAttachmentError
from .rpc_contention import BackoffPolicy, ContentionAwareRpc, RpcContentionError, ReadCoalescer


def probe_busy(fixture, *, gui=False):
    # The fixture operator holds an owned disposable node. Long-poll reads
    # occupy its single worker and bounded queue without modifying its chain.
    # Fusion continues using the public, independently attested attachment.
    if fixture._core_process.poll() is not None:
        raise RpcContentionError('Q04_BUSY_FIXTURE_EXITED')
    auth=base64.b64encode((fixture._datadir/'regtest'/'.cookie').read_bytes()).decode('ascii')
    def occupy():
        conn=http.client.HTTPConnection('127.0.0.1',fixture._rpc_port,timeout=20)
        try:
            conn.request('POST','/',json.dumps({'jsonrpc':'1.0','id':1,
                'method':'waitforblockheight','params':[1000000000,3000]}),
                {'Authorization':'Basic '+auth,'Content-Type':'application/json'})
            response=conn.getresponse();body=response.read(65536)
            if response.status==200:
                value=json.loads(body)
                if value.get('error') is not None:raise RpcContentionError('Q04_BUSY_LONGPOLL_DENIED')
            elif response.status!=503:raise RpcContentionError('Q04_BUSY_LOAD_DENIED')
        finally:conn.close()
    calls=[];busy=[]
    def read(method,params):
        calls.append(time.monotonic())
        try:return fixture.fusion_read(method,params)
        except ExternalAttachmentError as error:
            if error.args==('EXTERNAL_ATTACHMENT_RPC_NODE_BUSY',):busy.append(True)
            raise
    policy=BackoffPolicy(base_seconds=.1,max_seconds=.5,max_retries=3,jitter=.1)
    window=app=None
    if gui:
        from .desktop import qt_application
        from .external_core_gui import ExternalNodeWindow
        app=qt_application();window=ExternalNodeWindow(fixture._attachment)
        window.show();app.processEvents()
        rpc=window.rpc
        # Instrument the actual GUI wrapper; every call still reaches the
        # real attachment. No RPC result or busy exception is manufactured.
        rpc._read=read;rpc._policy=policy;rpc._coalescer=ReadCoalescer(1.0)
    else:rpc=ContentionAwareRpc(read,policy=policy,coalescer=ReadCoalescer(1.0))
    with ThreadPoolExecutor(max_workers=6) as pool:
        pending=[pool.submit(occupy) for _ in range(6)]
        time.sleep(.5)
        try:
            rpc.read('getblockcount',[])
            raise RpcContentionError('Q04_BUSY_NOT_OBSERVED')
        except RpcContentionError as error:
            if error.args!=('RPC_NODE_BUSY',):raise
        if len(busy)!=4 or len(calls)!=4:
            raise RpcContentionError('Q04_BUSY_RETRY_UNPROVEN')
        intervals=[b-a for a,b in zip(calls,calls[1:])]
        for i,delay in enumerate(intervals):
            if delay<min(policy.base_seconds*2**i,policy.max_seconds)*(1-policy.jitter):
                raise RpcContentionError('Q04_BUSY_BACKOFF_UNPROVEN')
        before=len(calls)
        try:rpc.read('getblockcount',[])
        except RpcContentionError as error:
            if error.args!=('RPC_NODE_BUSY',):raise
        else:raise RpcContentionError('Q04_BUSY_COALESCE_UNPROVEN')
        if len(calls)!=before or not rpc.status()['busy']:
            raise RpcContentionError('Q04_BUSY_COALESCE_UNPROVEN')
        if window is not None:
            for _ in range(3):
                window.request_sync();app.processEvents()
            if (len(calls)!=before or window.worker is not None
                    or window.status_label.text()!='Node busy · retrying after cooldown'
                    or window.height_label.text()!='Height: unverified'):
                raise RpcContentionError('Q04_BUSY_GUI_COALESCE_UNPROVEN')
        for future in pending:future.result(timeout=20)
    rpc.reset()
    height=rpc.read('getblockcount',[])
    if window is not None:
        window.request_sync();deadline=time.monotonic()+20
        while window.worker is not None and time.monotonic()<deadline:
            app.processEvents();time.sleep(.01)
        if window.worker is not None:
            window.worker.wait(30000);app.processEvents()
            raise RpcContentionError('Q04_BUSY_GUI_RECOVERY_TIMEOUT')
        if window.status_label.text()!='Verified REGTEST · Read only':
            raise RpcContentionError('Q04_BUSY_GUI_RECOVERY_UNPROVEN')
    # No write is sent to Core, even while the contention wrapper is present.
    attempts=len(calls)
    try:rpc.read('sendrawtransaction',['deadbeef'])
    except ExternalAttachmentError as error:
        if error.args!=('EXTERNAL_ATTACHMENT_READ_SCOPE_DENIED',):raise
    else:raise RpcContentionError('Q04_BUSY_WRITE_NOT_DENIED')
    if len(calls)!=attempts+1:raise RpcContentionError('Q04_BUSY_WRITE_RETRIED')
    if window is not None:
        window.close();app.processEvents()
        if fixture._core_process.poll() is not None:
            raise RpcContentionError('Q04_BUSY_GUI_CLOSE_STOPPED_CORE')
    return {'gui_coalescing': 'PASS' if gui else 'NOT_APPLICABLE_NO_QT',
        'status':'Q04_GENUINE_BUSY_PATH_PASS','synthetic_busy':False,
        'attachment_http_503_count':len(busy),'read_attempts':4,
        'retry_intervals_seconds':intervals,'coalesced_read_calls':0,
        'recovered_height':height,'write_boundary_attempts':1,'write_retried':False,
        'fresh_socket_process_attestation_per_attempt':True}
