"""Q20 privacy probe: live socket inventory + synthetic-secret scan (read-only).

1. Starts ONE new disposable REGTEST Core (original Popen, existing owned RPC)
   and records every socket of Core and of this Python host with lsof: every
   listener must be 127.0.0.1 and no connection may leave loopback.
2. Scans the given files/directories (frozen app, packages, evidence logs,
   matching crash reports) for the disposable test passwords used by the
   qualification scripts, 12-word BIP39 sequences, extended private keys,
   'rpcpassword=' and non-empty 'mnemonic_once'. Only counts and file paths are
   written; matched content is never copied into the report.
"""
from hashlib import sha256
import argparse, json, os, platform, re, subprocess, time
from datetime import datetime, timezone
from pathlib import Path

SYNTHETIC = [b'public-phase2-disposable-native-only', b'public-phase2-recovered-cancel-disposable-only',
             b'public-phase3-native-reorg-disposable-only', b'public-phase4-q16-native-fault-disposable-only',
             b'public-phase4-q18-memory-disposable-only', b'public-disposable-q06-signed-core-spend-only',
             b'public-disposable-q06-recovered-unsigned-cancel-only', b'public-disposable-q06-empty-core-loss-only']
XPRV = re.compile(rb'\b[xtv]prv[1-9A-HJ-NP-Za-km-z]{100,}')
RPCPASS = re.compile(rb'rpcpassword=[0-9a-f]{16,}')
MNEMONIC_ONCE = re.compile(rb'"mnemonic_once"\s*:\s*"[a-z ]{20,}"')
PUBLIC_VECTOR = 'abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about'
MAX_FILE = 256 * 1024 * 1024


def sockets(pid):
    out = subprocess.run(['lsof', '-nP', '-a', '-p', str(pid), '-i'], capture_output=True, text=True).stdout
    rows = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        name = ' '.join(parts[8:]) if len(parts) > 8 else ''
        rows.append(dict(type=parts[4] if len(parts) > 4 else '', name=name))
    return rows


def loopback_only(rows):
    bad = []
    for r in rows:
        for endpoint in re.split(r'->| ', r['name'].replace('(LISTEN)', '').replace('(ESTABLISHED)', '')):
            endpoint = endpoint.strip()
            if not endpoint or endpoint.startswith('('):
                continue
            host = endpoint.rsplit(':', 1)[0].strip('[]')
            if host not in ('127.0.0.1', 'localhost', '::1'):
                bad.append(r['name'])
    return bad


def wordlist():
    from mnemonic import Mnemonic
    return set(Mnemonic('english').wordlist)


def bip39_sequences(data, words):
    tokens = re.findall(rb'[a-z]+', data); run = 0; found = 0; window = []
    for t in tokens:
        if t.decode() in words:
            window.append(t.decode()); run += 1
            if run >= 12:
                if ' '.join(window[-12:]) != PUBLIC_VECTOR: found += 1
        else:
            run = 0; window = []
    return found


def scan(paths, words):
    result = dict(files=0, bytes=0, skipped_large=0, skipped_source_scripts=0, skipped_bip39_wordlists=0, hits=[])
    for base in paths:
        files = [base] if base.is_file() else [p for p in base.rglob('*') if p.is_file() and not p.is_symlink()]
        for f in files:
            if f.suffix == '.py':  # Qualification scripts define the synthetic fixture passwords.
                result['skipped_source_scripts'] += 1; continue
            if 'wordlist' in f.parts or f.name == 'english.txt':
                result['skipped_bip39_wordlists'] += 1; continue
            try:
                size = f.stat().st_size
                if size > MAX_FILE: result['skipped_large'] += 1; continue
                data = f.read_bytes()
            except OSError:
                continue
            result['files'] += 1; result['bytes'] += size
            kinds = {}
            n = sum(data.count(s) for s in SYNTHETIC)
            if n: kinds['synthetic_password'] = n
            for name, rx in (('extended_private_key', XPRV), ('rpcpassword_literal', RPCPASS), ('mnemonic_once_value', MNEMONIC_ONCE)):
                c = len(rx.findall(data))
                if c: kinds[name] = c
            if size <= 32 * 1024 * 1024 and (f.suffix in ('.log', '.json', '.txt', '.md', '.ips', '.crash', '.py', '') or b'\0' not in data[:4096]):
                c = bip39_sequences(data.lower(), words)
                if c: kinds['bip39_12_word_sequence'] = c
            if kinds: result['hits'].append(dict(path=str(f), kinds=kinds))
    return result


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--core-dir', type=Path, required=True)
    ap.add_argument('--wsp-source', type=Path, required=True); ap.add_argument('--scan', type=Path, action='append', default=[])
    ap.add_argument('--report', type=Path, required=True); ap.add_argument('--confirm-disposable-regtest', action='store_true')
    a = ap.parse_args()
    if not a.confirm_disposable_regtest or a.report.exists(): ap.error('new report and explicit consent required')
    root = Path(__file__).resolve().parents[1]
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--'], cwd=root, check=True)
    from wam_regtest.q02_probe import _Node
    from wam_regtest.rpc_scope import identity, unregister
    from wam_regtest.wsp_live import _pinned_source
    _pinned_source(a.wsp_source.resolve(strict=True))
    r = dict(source_sha=head, status='FAIL', mainnet_allowed=False, matched_content_recorded=False)
    node = _Node(a.core_dir.resolve(strict=True)); node.temp._finalizer.detach()
    try:
        node.start(); assert identity(node.directory).binding.process is node.proc
        time.sleep(2); node.call('getblockcount')
        config = (node.directory / 'wam.conf').read_text()
        r['core_config_network_keys'] = {k: v for k, v in re.findall(r'^(listen|connect|dnsseed|discover|upnp|rpcbind|rpcallowip)=(.*)$', config, re.M)}
        r['core_sockets'] = sockets(node.proc.pid); r['python_sockets'] = sockets(os.getpid())
        r['non_loopback_endpoints'] = loopback_only(r['core_sockets'] + r['python_sockets'])
        r['core_listeners'] = [s['name'] for s in r['core_sockets'] if 'LISTEN' in s['name']]
        assert r['non_loopback_endpoints'] == [], r['non_loopback_endpoints']
        assert r['core_listeners'] and all(x.startswith('127.0.0.1:') for x in r['core_listeners'])
    finally:
        if node.proc is not None and node.proc.poll() is None:
            node.call('stop', timeout=10); node.proc.wait(timeout=30)
        r['owner_shutdown_verified'] = node.proc is not None and node.proc.poll() is not None
        if r['owner_shutdown_verified']: unregister(node.directory)
    words = wordlist()
    r['secret_scan'] = scan([p.resolve() for p in a.scan], words)
    r['scanned_roots'] = [str(p) for p in a.scan]
    r['status'] = 'PASS_LOOPBACK_ONLY' + ('_NO_SECRET_HITS' if not r['secret_scan']['hits'] else '_SECRET_HITS_REVIEW')
    r.update(host=dict(os=platform.system(), arch=platform.machine()), timestamp_utc=datetime.now(timezone.utc).isoformat())
    with a.report.open('x') as f: json.dump(r, f, indent=2); f.write('\n')
    print(r['status'])


if __name__ == '__main__':
    main()
