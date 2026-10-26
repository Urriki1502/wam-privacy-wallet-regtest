"""Q03 acceptance measurement inside genuine native/final-frozen fixtures only."""
import json
from .telemetry import snapshot


def measure_repeated_snapshots(session):
    # The caller has already warmed this disposable session against genuine
    # pinned REGTEST Core. Do not reset process-wide counters or change timers.
    before=snapshot()
    for _ in range(5):
        session.snapshot()
    after=snapshot()
    delta={key:after[key]-before.get(key,0) for key in after}
    if any(delta[key]!=0 for key in ('verified_core_paths','cli_spawn',
            'http_connection_create','http_socket_connect','wallet_session_rpc_client_create')):
        raise ValueError('Q03_REPEATED_READ_REUSE_DENIED')
    if delta['http_request']<5:
        raise ValueError('Q03_REAL_HTTP_READS_REQUIRED')
    result={'cycles':5,'delta':delta,'status':'Q03_REPEATED_READ_REUSE_PASS'}
    print('Q03_REUSE_PASS '+json.dumps(result,sort_keys=True),flush=True)
    return result
