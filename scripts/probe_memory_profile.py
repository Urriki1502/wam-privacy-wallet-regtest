"""Q18 bounded memory profile on NEW disposable REGTEST fixtures (macOS ARM64).

Measurement only: never changes or evaluates the approved Q18 budget. Metrics
per process come from proc_pid_rusage(RUSAGE_INFO_V4): resident size, current
physical footprint and the kernel's lifetime-max physical footprint (catches
transients between samples). Stages: (A) Core alone, idle then across five
REGTEST RandomX key changes (epoch 64, lag 4: heights 68,132,196,260,324); (B) WSP scanner increment, re-sync and full rescan in this
Python process; (C) the real Fusion Q06 backend with a Cocoa window, concurrent
Core+Python samples, then quit and same-profile restart. No transaction stress,
no soak, no owner wallet, no mainnet.
"""
from hashlib import sha256, pbkdf2_hmac
import argparse, ctypes, json, os, platform, secrets, subprocess, tempfile, threading, time
from datetime import datetime, timezone
from pathlib import Path

USAGE_C = r'''#include <libproc.h>
#include <sys/resource.h>
#include <stdint.h>
int wam_lab_usage(int pid, uint64_t *values) {
    struct rusage_info_v4 info;
    int rc=proc_pid_rusage(pid,RUSAGE_INFO_V4,(rusage_info_t *)&info);
    if (rc) return rc;
    values[0]=info.ri_resident_size;
    values[1]=info.ri_phys_footprint;
    values[2]=info.ri_lifetime_max_phys_footprint;
    values[3]=info.ri_user_time+info.ri_system_time;
    return 0;
}
'''
MIB = 1024 * 1024


class Meter:
    def __init__(self, work):
        src = work / 'usage.c'; src.write_text(USAGE_C); lib = work / 'usage.dylib'
        subprocess.run(['clang', '-shared', '-O2', '-o', str(lib), str(src)], check=True)
        self.source_sha256 = sha256(USAGE_C.encode()).hexdigest()
        self.fn = ctypes.CDLL(str(lib)).wam_lab_usage
        self.fn.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_uint64)]; self.fn.restype = ctypes.c_int

    def __call__(self, pid):
        v = (ctypes.c_uint64 * 4)()
        if self.fn(pid, v): return None
        return dict(rss=v[0], footprint=v[1], lifetime_max_footprint=v[2], cpu_ns=v[3])


class Sampler:
    """Concurrent samples every 50 ms; records max simultaneous RSS/footprint sum."""
    def __init__(self, meter):
        self.meter = meter; self.pids = {}; self.max_sum = dict(rss=0, footprint=0); self.samples = 0
        self.stop = threading.Event(); self.thread = threading.Thread(target=self.run, daemon=True)

    def run(self):
        while not self.stop.wait(0.05):
            values = [self.meter(p) for p in list(self.pids.values())]
            values = [v for v in values if v]
            if values:
                self.samples += 1
                for k in ('rss', 'footprint'):
                    self.max_sum[k] = max(self.max_sum[k], sum(v[k] for v in values))


def mib(v): return round(v / MIB, 1)


def snap(meter, label, pids):
    row = {'stage': label}
    for name, pid in pids.items():
        m = meter(pid); row[name] = {k: (mib(x) if k != 'cpu_ns' else x) for k, x in m.items()} if m else None
    return row


def stage_core(meter, core, source, out):
    from wam_regtest.q02_probe import _Node
    from wam_regtest.rpc_scope import identity, reauthenticate_owned, unregister
    from wam_sp.hd import ExtendedPrivate, HARDENED
    from wam_sp.core import hash160, Input, send
    from wam_sp.codec import encode
    from wam_sp.transaction import p2wpkh, signed_single_input
    from wam_sp.scanner import Scanner
    from wam_regtest.bip39_12 import Bip39Regtest12Keys
    from wam_regtest.wallet_session import WalletCoreCli
    import tracemalloc
    seed = pbkdf2_hmac('sha512', ('abandon ' * 11 + 'about').encode(), b'mnemonic', 2048)
    miner = ExtendedPrivate.master(seed).derive((84 | HARDENED, 1 | HARDENED, HARDENED, 0, 0))
    secret = int.from_bytes(miner.secret, 'big'); script = p2wpkh(secret)
    address = encode('wamrt', hash160(miner.public), bech32m=False)
    node = _Node(core); node.temp._finalizer.detach()
    rows = []; result = {'fixture_directory': str(node.directory)}; keys = scanner = rpc = None
    me = os.getpid()
    try:
        node.start(); assert identity(node.directory).binding.process is node.proc
        time.sleep(3)
        rows.append(snap(meter, 'A0 core idle, height 0', {'core': node.proc.pid}))
        height = 0
        for target in [4, 64, 67, 68, 72, 128, 131, 132, 136, 196, 200, 260, 264, 324, 328]:
            node.call('generatetoaddress', str(target - height), address, timeout=120); height = target
            rows.append(snap(meter, 'A height %d' % height, {'core': node.proc.pid}))
        # Stage B: a few eligible BIP352 payments, then scanner memory in THIS process.
        keys = Bip39Regtest12Keys('abandon ' * 11 + 'about', source=source, authorized_disposable=True)
        receive = keys.public_metadata()['receive_code']
        for h in range(1, 6):
            block = node.call('getblock', node.call('getblockhash', str(h)), '2'); tx = block['tx'][0]
            out_ = [o for o in tx['vout'] if o['scriptPubKey']['hex'] == script.hex()][0]
            value = int(round(float(out_['value']) * 100_000_000))
            txin = Input(tx['txid'], out_['n'], script, witness=(b'\x30', miner.public), secret=secret)
            raw = signed_single_input(txin, value, ((value - 10_000, b'\x51\x20' + send([txin], [receive])[0]),), secret)
            node.call('sendrawtransaction', raw if isinstance(raw, str) else raw.hex())
        node.call('generatetoaddress', '1', address, timeout=120); height += 1
        rows.append(snap(meter, 'B before scanner', {'python': me, 'core': node.proc.pid}))
        work = Path(tempfile.mkdtemp(prefix='wam-q18-scan-', dir=node.root))
        tracemalloc.start()
        scanner = Scanner(work / 'scan.sqlite', keys.accounts()); rpc = WalletCoreCli(node.cli, node.directory)
        scanner.sync(rpc); scanner.assert_current()
        coins = len(scanner.coins()); peak = tracemalloc.get_traced_memory()[1]
        rows.append(snap(meter, 'B after full scan', {'python': me, 'core': node.proc.pid}))
        scanner.sync(rpc)
        rows.append(snap(meter, 'B after no-op re-sync', {'python': me}))
        scanner.close(); scanner = Scanner(work / 'rescan.sqlite', keys.accounts()); scanner.sync(rpc)
        rows.append(snap(meter, 'B after second full rescan (new store)', {'python': me}))
        result['scanner'] = dict(coins=coins, tracemalloc_peak_mib=mib(peak), height=height,
                                 sqlite_bytes=(work / 'scan.sqlite').stat().st_size)
        tracemalloc.stop(); scanner.close(); scanner = None
        rpc._transport.close() if getattr(rpc, '_transport', None) else None; rpc = None
        # _Node.start() is fresh-chain only by design; Core restart retention is
        # measured in stage C through the real supervisor on the same profile.
        result['core_restart_in_stage_a'] = 'NOT_MEASURED_FRESH_CHAIN_ONLY_FIXTURE'
        result['status'] = 'MEASURED'
    except Exception as error:
        result.update(status='FAIL_MEASUREMENT', error_class=type(error).__name__, error=str(error)[:200])
    finally:
        if scanner is not None: scanner.close()
        if keys is not None: keys.close()
        if node.proc is not None and node.proc.poll() is None:
            try:
                c = identity(node.directory)
                if c is not None and c.faulted: reauthenticate_owned(node.directory, authorized=True)
                node.call('stop', timeout=10); node.proc.wait(timeout=30)
            except Exception:
                result['retained_original_process_pid'] = node.proc.pid
        result['owner_shutdown_verified'] = node.proc is not None and node.proc.poll() is not None
        if result['owner_shutdown_verified']: unregister(node.directory)
    result['rows'] = rows
    return result


def stage_app(meter, core, source, out):
    from wam_regtest import custody
    from wam_regtest.wallet_executor import WalletExecutor
    from wam_regtest.bip39_owner_backend import Bip39ReadOnlyBackend
    from wam_regtest.q05_platforms import DarwinArm64Adapter
    from wam_regtest.desktop import qt_application
    from wam_regtest.bip39_fusion_gui import Bip39FusionWindow
    app = qt_application(); assert app.platformName() == 'cocoa'
    root = out / ('wam-fusion-core-' + secrets.token_hex(8)); custody.create_directory(root)
    password = b'public-phase4-q18-memory-disposable-only'
    me = os.getpid(); rows = []; result = {'profile': str(root)}; sampler = Sampler(meter)
    rows.append(snap(meter, 'C python before GUI', {'python': me}))
    adapter = DarwinArm64Adapter()
    executor = WalletExecutor(lambda: Bip39ReadOnlyBackend(root, core, source, _anchor_factory=adapter.make_anchor))
    window = Bip39FusionWindow(executor); window.show()
    for _ in range(50): app.processEvents(); time.sleep(0.01)
    rows.append(snap(meter, 'C python with Fusion window', {'python': me}))
    sampler.pids['python'] = me; sampler.thread.start()
    try:
        opened = executor.request('open', password, 'create', '', timeout=120)
        sampler.pids['core'] = executor._backend.owner.process.pid
        w = opened['mnemonic_once'].split(); c = executor.request('backup_challenge')
        assert executor.request('backup_verify', c['challenge_id'], tuple(w[n - 1] for n in c['positions'])) is True; w = None
        executor.request('mine', timeout=240); snapshot = executor.request('activate', timeout=240)
        window._on_ready('activate', snapshot)
        for _ in range(50): app.processEvents(); time.sleep(0.01)
        pids = {'python': me, 'core': executor._backend.owner.process.pid}
        rows.append(snap(meter, 'C activated wallet height %d' % snapshot['height'], pids))
        executor.request('quit', timeout=120); assert executor.join(15) and executor.closed
        rows.append(snap(meter, 'C after quit (python only)', {'python': me}))
        executor = WalletExecutor(lambda: Bip39ReadOnlyBackend(root, core, source, keychain=root / 'q05-disposable.keychain-db'))
        executor.request('open', password, 'reopen', '', timeout=120)
        sampler.pids['core'] = executor._backend.owner.process.pid
        again = executor.request('activate', timeout=240)
        pids = {'python': me, 'core': executor._backend.owner.process.pid}
        rows.append(snap(meter, 'C restarted same profile, activated height %d' % again['height'], pids))
        executor.request('quit', timeout=120); assert executor.join(15) and executor.closed
        result['status'] = 'MEASURED'
    except Exception as error:
        result.update(status='FAIL_MEASUREMENT', error_class=type(error).__name__, error=str(error)[:200])
    finally:
        sampler.stop.set(); sampler.thread.join(2)
        window._poll.stop(); window.hide()
        if not executor.closed:
            try: executor.request('quit', timeout=120); executor.join(15)
            except Exception: pass
        result['owner_shutdown_verified'] = executor.closed
    result.update(rows=rows, concurrent_max_sum_mib={k: mib(v) for k, v in sampler.max_sum.items()},
                  concurrent_samples=sampler.samples, python_lifetime_max_footprint_mib=mib(meter(me)['lifetime_max_footprint']))
    return result


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--core-dir', type=Path, required=True)
    ap.add_argument('--wsp-source', type=Path, required=True); ap.add_argument('--output-dir', type=Path, required=True)
    ap.add_argument('--confirm-disposable-regtest', action='store_true'); a = ap.parse_args()
    a.output_dir = a.output_dir.resolve(strict=True)  # Private-directory gate needs absolute paths.
    report = a.output_dir / 'q18-memory-profile.json'
    if not a.confirm_disposable_regtest or report.exists(): ap.error('new report and explicit consent required')
    root = Path(__file__).resolve().parents[1]
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--'], cwd=root, check=True)
    from wam_regtest.wsp_live import _pinned_source
    core, source = a.core_dir.resolve(strict=True), a.wsp_source.resolve(strict=True); _pinned_source(source)
    with tempfile.TemporaryDirectory(prefix='wam-q18-meter-') as t:
        meter = Meter(Path(t)); begin = time.monotonic()
        r = dict(source_sha=head, scope='measurement only; Q18 budget unchanged; not a PASS/FAIL evaluation',
                 metric_source='proc_pid_rusage RUSAGE_INFO_V4', usage_c_sha256=meter.source_sha256,
                 regtest_randomx=dict(epoch_blocks=64, lag=4, key_change_heights=[68, 132, 196, 260, 324]))
        r['stage_core_scanner'] = stage_core(meter, core, source, a.output_dir)
        r['stage_app'] = stage_app(meter, core, source, a.output_dir)
    ok = all(r[s]['status'] == 'MEASURED' and r[s]['owner_shutdown_verified'] for s in ('stage_core_scanner', 'stage_app'))
    r.update(status='MEASURED_Q18_PROFILE' if ok else 'FAIL_Q18_PROFILE', seconds=time.monotonic() - begin,
             host=dict(os=platform.system(), arch=platform.machine(), machine=platform.platform()),
             timestamp_utc=datetime.now(timezone.utc).isoformat())
    subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--'], cwd=root, check=True)
    with report.open('x') as f: json.dump(r, f, indent=2); f.write('\n')
    print(r['status'])
    if not ok: raise SystemExit(1)


if __name__ == '__main__':
    main()
