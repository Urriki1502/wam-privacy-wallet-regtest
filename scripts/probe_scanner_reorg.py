"""Genuine-Core WSP scanner reorg lab on ONE new disposable REGTEST node.

Q14 scope: depth 1/12/100 reorgs, canonical replacement (same tx re-mined),
orphaned outputs (BIP125 conflict replaces the payment), reorg DURING an active
scan, interrupted scan + restart, rescan consistency against a fresh scanner
and an independent integer-atom oracle from Core active-chain blocks + gettxout. Signed/
uncertain/draft reservation rows and the label table must be byte-identical.

Uses the pinned WSP Scanner and Fusion's REAL BIP39 derivation with the published
BIP39 test mnemonic (public, disposable). No Fusion profile, native anchor,
wallet session, signer authority, owner wallet, mainnet or retry of a payment.
Reuses existing original-Popen ownership and the finite owned RPC allowlist.
"""
from decimal import Decimal
from hashlib import sha256, pbkdf2_hmac
import argparse, json, platform, re, subprocess, tempfile, time
from datetime import datetime, timezone
from pathlib import Path

from wam_regtest.q02_probe import _Node
from wam_regtest.rpc_scope import identity, reauthenticate_owned, unregister
from wam_regtest.wsp_live import _pinned_source, REGTEST_GENESIS

PUBLIC_MNEMONIC = 'abandon ' * 11 + 'about'   # Published BIP39 vector; never owner data.
FEE = 10_000


def atoms(value):
    exact = Decimal(str(value)) * 100_000_000
    if exact != int(exact):
        raise ValueError('REORG_NON_INTEGER_ATOMS')
    return int(exact)


def probe(core, source):
    _pinned_source(source)
    from wam_sp.hd import ExtendedPrivate, HARDENED
    from wam_sp.core import Input, send, pub
    from wam_sp.codec import encode
    from wam_sp.core import hash160
    from wam_sp.transaction import p2wpkh, signed_single_input
    from wam_sp.scanner import Scanner
    from wam_regtest.bip39_12 import Bip39Regtest12Keys
    from wam_regtest.wallet_session import WalletCoreCli
    seed = pbkdf2_hmac('sha512', PUBLIC_MNEMONIC.encode(), b'mnemonic', 2048)
    miner = ExtendedPrivate.master(seed).derive((84 | HARDENED, 1 | HARDENED, HARDENED, 0, 0))
    miner_secret = int.from_bytes(miner.secret, 'big')
    miner_script = p2wpkh(miner_secret)
    miner_address = encode('wamrt', hash160(miner.public), bech32m=False)
    node = _Node(core); node.temp._finalizer.detach()  # Retain new fixture evidence.
    work = Path(tempfile.mkdtemp(prefix='wam-reorg-scanners-', dir=node.root))
    result = {'status': 'INCOMPLETE', 'synthetic_rpc': False, 'frozen': False, 'new_fixture_only': True,
              'fixture_directory': str(node.directory), 'mainnet_allowed': False,
              'core_member_sha256': {p.name: sha256(p.read_bytes()).hexdigest() for p in (node.node, node.cli)},
              'owner_shutdown_verified': False, 'automatic_rebroadcast': False, 'cases': {}}
    keys = None; scanners = []; rpcs = []
    payments = {}  # txid -> dict(coinbase_height, atoms, vout)
    try:
        node.start(); context = identity(node.directory)
        assert context.binding.process is node.proc
        assert node.call('getblockhash', '0') == REGTEST_GENESIS
        info = node.call('getnetworkinfo')
        assert (info['version'], info['subversion']) == (113, '/WAM:0.1.13/')
        keys = Bip39Regtest12Keys(PUBLIC_MNEMONIC, source=source, authorized_disposable=True)
        receive = keys.public_metadata()['receive_code']
        accounts = keys.accounts()
        assert all(a.labels == () for a in accounts), 'FUSION_LABELS_EXPECTED_EMPTY'

        # Replacement branches pay a different public dummy key so a re-mined
        # block can never be byte-identical to the block just invalidated.
        branch_address = encode('wamrt', hash160(pub(31)), bech32m=False)

        def mine(count, to=None):
            hashes = []
            while count:
                step = min(count, 101)
                hashes += node.call('generatetoaddress', str(step), to or miner_address, timeout=120)
                count -= step
            return hashes

        def tip():
            return node.call('getblockcount'), node.call('getbestblockhash')

        def coinbase(height):
            block = node.call('getblock', node.call('getblockhash', str(height)), '2')
            tx = block['tx'][0]
            outs = [o for o in tx['vout'] if o['scriptPubKey']['hex'] == miner_script.hex()]
            assert len(outs) == 1
            return tx['txid'], outs[0]['n'], atoms(outs[0]['value'])

        def build(height, to_wallet=True, fee=FEE):
            txid, n, value = coinbase(height)
            txin = Input(txid, n, miner_script, witness=(b'\x30', miner.public), secret=miner_secret)
            if to_wallet:
                script = b'\x51\x20' + send([txin], [receive])[0]
            else:
                script = p2wpkh(31)  # Public non-wallet script; never ours.
            raw = signed_single_input(txin, value, ((value - fee, script),), miner_secret)
            return raw if isinstance(raw, str) else raw.hex(), value - fee

        def pay(height):
            raw, value = build(height)
            txid = node.call('sendrawtransaction', raw)
            payments[txid] = dict(coinbase_height=height, atoms=value, vout=0,
                                  height=node.call('getblockcount') + 1)  # Earliest possible inclusion.
            return txid

        def conflict(height):
            raw, _ = build(height, to_wallet=False, fee=FEE * 3)
            return node.call('sendrawtransaction', raw)  # BIP125 nSequence 0xfffffffd.

        def canonical_txids(low):
            """Core's active chain only; never mempool, never WSP."""
            seen = set()
            for h in range(low, node.call('getblockcount') + 1):
                block = node.call('getblock', node.call('getblockhash', str(h)), '2')
                seen.update(tx['txid'] for tx in block['tx'])
            return seen

        def oracle():
            """Independent of WSP: our constructed outputs confirmed on Core's active chain."""
            if not payments:
                return {}
            on_chain = canonical_txids(min(p['height'] for p in payments.values()))
            expected = {}
            for txid, p in payments.items():
                if txid not in on_chain:
                    continue  # Orphaned/conflicted: absent from every canonical block.
                coin = node.call('gettxout', txid, str(p['vout']), 'true')  # Non-null: unspent.
                assert coin['confirmations'] >= 1 and atoms(coin['value']) == p['atoms']
                assert coin['scriptPubKey']['hex'].startswith('5120')
                expected[(txid, p['vout'])] = p['atoms']
            return expected

        def new_scanner(name):
            s = Scanner(work / (name + '.sqlite'), accounts); scanners.append(s); return s

        def rpc():
            r = WalletCoreCli(node.cli, node.directory); rpcs.append(r); return r

        def held(s):
            return {(c['txid'], c['vout']): c['atoms'] for c in s.coins()}

        def table(s, name):
            return s.store.db.execute('SELECT * FROM ' + name + ' ORDER BY 1,2').fetchall()

        def reorg(depth, replacement):
            """invalidate the block at depth `depth`; mine `replacement` (> depth) blocks."""
            height, _ = tip(); fork = height - depth + 1
            node.call('invalidateblock', node.call('getblockhash', str(fork)))
            assert node.call('getblockcount') == fork - 1
            return fork, replacement

        mine(110)  # Coinbases at 1..10 mature; miner fixture only.
        s1 = new_scanner('incremental'); r1 = rpc()
        s1.sync(r1); s1.assert_current(); assert held(s1) == {}

        # ---- depth 1: canonical replacement (same payment re-mined on stronger branch)
        a = pay(1); mine(1); s1.sync(r1)
        assert held(s1) == oracle() and (a, 0) in held(s1)
        old_hash = tip()[1]
        fork, n = reorg(1, 2)
        assert a in node.call('getrawmempool')  # Disconnected tx returned to mempool.
        mine(n, branch_address); m = s1.sync(r1); s1.assert_current()
        assert m.rollback == 1 and held(s1) == oracle() and (a, 0) in held(s1)
        assert node.call('getblockhash', str(fork)) != old_hash
        result['cases']['depth1_canonical_replacement'] = dict(status='PASS', rollback=m.rollback,
            payment_remined=True, wallet_atoms=sum(held(s1).values()))

        # ---- reservations preserved across a reorg that orphans a reserved output
        b = pay(2); mine(1); mine(11); s1.sync(r1)
        assert (b, 0) in held(s1) and held(s1) == oracle()
        s1.store.db.execute('INSERT INTO reservations VALUES(?,?,?,?,?)', (b, 0, 'b' * 32, 'signed', 1))
        s1.store.db.execute('INSERT INTO reservations VALUES(?,?,?,?,?)', (a, 0, 'a' * 32, 'uncertain', 1))
        reservations, labels = table(s1, 'reservations'), table(s1, 'labels')
        # ---- depth 12: orphaned output (conflict replaces the reorged payment)
        fork, n = reorg(12, 13)
        b_returned = b in node.call('getrawmempool')  # Core may not re-add deep reorgs.
        replaced = conflict(2)  # Replaces b if pooled; otherwise a plain conflicting spend.
        assert b not in node.call('getrawmempool') and replaced in node.call('getrawmempool')
        mine(n, branch_address); m = s1.sync(r1); s1.assert_current()
        assert m.rollback == 12 and (b, 0) not in held(s1) and held(s1) == oracle()
        assert b not in canonical_txids(payments[b]['height'])
        assert table(s1, 'reservations') == reservations, 'RESERVATIONS_CHANGED_BY_REORG'
        assert table(s1, 'labels') == labels == [], 'LABELS_CHANGED_BY_REORG'
        result['cases']['depth12_orphaned_output'] = dict(status='PASS', rollback=m.rollback,
            orphaned_txid=b, conflict_txid=replaced, orphan_removed=True, core_readded_to_mempool=b_returned,
            reservations_preserved=len(reservations), labels_table_rows=0)

        # ---- depth 100: orphaned output at maximum tested depth
        c = pay(3); mine(1); mine(99); s1.sync(r1)
        assert (c, 0) in held(s1)
        fork, n = reorg(100, 101)
        c_returned = c in node.call('getrawmempool')
        conflict(3); assert c not in node.call('getrawmempool')
        mine(n, branch_address); m = s1.sync(r1); s1.assert_current()
        assert m.rollback == 100 and (c, 0) not in held(s1) and held(s1) == oracle()
        assert table(s1, 'reservations') == reservations and table(s1, 'labels') == []
        result['cases']['depth100_orphaned_output'] = dict(status='PASS', rollback=m.rollback,
            orphaned_txid=c, orphan_removed=True, reservations_preserved=len(reservations),
            core_readded_to_mempool=c_returned)

        # ---- reorg DURING an active scan (fresh scanner from genesis)
        d = pay(4); mine(1); mine(5)  # d at depth 6.
        s1.sync(r1); assert (d, 0) in held(s1)
        height, _ = tip(); trigger = height - 2; fork_at = height - 7
        s2 = new_scanner('mid-scan'); r2 = rpc(); fired = []

        def reorg_mid_scan():
            # Called by WSP before each block fetch. One explicit fault only.
            if not fired and s2.store.tip()[0] == trigger - 1:
                fired.append(s2.store.tip())
                node.call('invalidateblock', node.call('getblockhash', str(fork_at)))
                conflict(4)
                mine(height - fork_at + 2, branch_address)
            return False
        try:
            s2.sync(r2, cancel=reorg_mid_scan)
        except ValueError as error:
            mid_code = error.args[0]
        else:
            raise AssertionError('MID_SCAN_REORG_NOT_DETECTED')
        assert fired and mid_code == 'CHAIN_CHANGED_RETRY', mid_code
        partial = s2.store.tip()
        assert partial[0] >= fork_at and not s2.ready  # Committed old-branch blocks, not current.
        m = s2.sync(r2); s2.assert_current()
        assert m.rollback >= 1 and (d, 0) not in held(s2) and held(s2) == oracle()
        s1.sync(r1); assert held(s1) == held(s2)
        result['cases']['reorg_during_active_scan'] = dict(status='PASS', detected=mid_code,
            committed_old_branch_height=partial[0], fork_height=fork_at, resync_rollback=m.rollback,
            orphaned_txid=d, orphan_removed=True)

        # ---- interrupted scan + restart of a NEW scanner object on the same store
        s3 = new_scanner('interrupted'); r3 = rpc(); stop_at = 57
        try:
            s3.sync(r3, cancel=lambda: s3.store.tip()[0] >= stop_at)
        except ValueError as error:
            assert error.args[0] == 'SCAN_CANCELLED'
        else:
            raise AssertionError('SCAN_NOT_INTERRUPTED')
        assert s3.store.tip()[0] == stop_at and not s3.ready
        s3.close(); scanners.remove(s3)
        s3 = Scanner(work / 'interrupted.sqlite', accounts); scanners.append(s3)
        s3.sync(r3); s3.assert_current()
        result['cases']['interrupted_scan_restart'] = dict(status='PASS', interrupted_at=stop_at,
            resumed_from=stop_at, final_height=s3.store.tip()[0])

        # ---- rescan consistency: incremental-with-reorgs == mid-scan == restarted == fresh
        s4 = new_scanner('fresh'); s4.sync(rpc()); s4.assert_current()
        expected = oracle()
        coins = [held(s) for s in (s1, s2, s3, s4)]
        history = [table(s, 'history') for s in (s1, s2, s3, s4)]
        tips = [s.store.tip() for s in (s1, s2, s3, s4)]
        assert all(c == expected for c in coins), 'RESCAN_COIN_SET_MISMATCH'
        assert all(h == history[0] for h in history), 'RESCAN_HISTORY_MISMATCH'
        assert all(t == tip() for t in tips)
        assert len(expected) == 1 and (a, 0) in expected  # Only the re-mined payment survives.
        result['cases']['rescan_consistency'] = dict(status='PASS', scanners=4,
            oracle_outputs=len(expected), oracle_atoms=sum(expected.values()),
            wallet_atoms=[sum(c.values()) for c in coins], tip_height=tip()[0])
        assert node.call('getrawmempool') == []
        result.update(status='PASS_SCOPED_SCANNER_REORG_LAB', financial_broadcasts=len(payments),
                      conflict_broadcasts=3, payments_constructed=len(payments),
                      final_tip=list(tip()), reservation_rows=len(reservations))
    except Exception as error:
        result['status'] = 'FAIL_SCOPED_SCANNER_REORG_LAB'
        result['error_class'] = type(error).__name__
        result['error'] = str(error)[:300] if re.fullmatch(r'[A-Za-z0-9_ :.,()\[\]-]{0,300}', str(error)) else 'REDACTED'
    finally:
        for s in scanners:
            try: s.close()
            except Exception: pass
        for r in rpcs:
            if getattr(r, '_transport', None) is not None: r._transport.close()
        if keys is not None: keys.close()
        if node.proc is not None and node.proc.poll() is None:
            try:
                context = identity(node.directory)
                if context is not None and context.faulted:
                    reauthenticate_owned(node.directory, authorized=True)  # Same original Popen only.
                    result['shutdown_after_explicit_reauthentication'] = True
                node.call('stop', timeout=5); node.proc.wait(timeout=20)
            except Exception:
                result['status'] = 'BLOCKED_ORIGINAL_OWNER_SHUTDOWN_UNVERIFIED'
                result['retained_original_process_pid'] = node.proc.pid
        if node.proc is not None and node.proc.poll() is not None:
            result['owner_shutdown_verified'] = True
            unregister(node.directory)
    return result


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--core-dir', type=Path, required=True)
    ap.add_argument('--wsp-source', type=Path, required=True); ap.add_argument('--report', type=Path, required=True)
    ap.add_argument('--confirm-disposable-regtest', action='store_true'); args = ap.parse_args()
    if not args.confirm_disposable_regtest or args.report.exists():
        ap.error('new report and explicit disposable REGTEST consent required')
    from wam_regtest.probe_source import _tree, verify_python_tree
    root = Path(__file__).resolve().parents[1]
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--'], cwd=root, check=True)
    tree = _tree(root, head); digests, _ = verify_python_tree(root, tree, tree)
    begin = time.monotonic()
    result = probe(args.core_dir.resolve(strict=True), args.wsp_source.resolve(strict=True))
    subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--'], cwd=root, check=True)
    after, _ = verify_python_tree(root, tree, tree)
    if after != digests or subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip() != head:
        raise ValueError('SCANNER_REORG_SOURCE_CHANGED')
    result.update(source_sha=head, literal_python_unchanged_across_probe=True, seconds=time.monotonic() - begin,
                  wsp_source_commit='ac55f13423620252bdbf848c7e8a280c3b84721e',
                  host={'os': platform.system(), 'arch': platform.machine()},
                  scope='WSP scanner layer on genuine Core; not Fusion native custody or GUI',
                  timestamp_utc=datetime.now(timezone.utc).isoformat())
    with args.report.open('x') as f: json.dump(result, f, indent=2); f.write('\n')
    print(result['status'])
    if result['status'] != 'PASS_SCOPED_SCANNER_REORG_LAB': raise SystemExit(1)


if __name__ == '__main__': main()
