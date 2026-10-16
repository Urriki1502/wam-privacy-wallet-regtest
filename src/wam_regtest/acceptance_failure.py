"""Opted-in acceptance diagnostics: reviewed file/line only, never exception text."""
from pathlib import Path

REVIEWED=frozenset(('mining_probe.py','mining_account.py','linux_qt_probe.py',
    'linux_headless_probe.py','linux_headless.py','wallet_probe.py','wallet_session.py',
    'vault.py','core.py','json_rpc.py','core_process.py','linux_anchor_witness.py',
    'linux_private_storage.py','linux_core_transport.py','reopen_probe.py',
    'windows_core_transport.py','windows_private_storage.py','http_session_probe.py','rpc_contention_probe.py'))


def failure_site(error):
    sites=[];tb=error.__traceback__
    while tb is not None:
        name=Path(tb.tb_frame.f_code.co_filename).name
        if name in REVIEWED and 1<=tb.tb_lineno<=10000:sites.append(name+':'+str(tb.tb_lineno))
        tb=tb.tb_next
    return '>'.join(sites[-4:]) or 'UNCLASSIFIED_REVIEWED_SITE'
