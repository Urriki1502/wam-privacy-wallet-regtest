"""Bounded public REGTEST history fixture; no user-seed signing or migration."""
from decimal import Decimal
import time


def fund_public_history(owner, source, receive_code):
    """253 genuine incoming payments on THIS original disposable Core only."""
    from .managed_wallet_checkpoint import _owned
    from .wsp_live import public_regtest_mining_address, _pinned_source
    from .wallet_session import WalletCoreCli
    from .wallet_read import HistoryRow
    from wam_sp.core import Input, pub, send
    from wam_sp.transaction import p2wpkh, signed_single_input
    _pinned_source(source)
    _owned(owner)
    rpc = WalletCoreCli(owner.cli, owner.directory)
    deadline = time.monotonic() + 180
    def atoms(value):
        result = Decimal(str(value)) * 100_000_000
        if result != int(result) or not 10000 < result <= 22_000_000 * 100_000_000:
            raise ValueError('Q06_HISTORY_FIXTURE_AMOUNT_DENIED')
        return int(result)
    def bounded():
        if time.monotonic() >= deadline:
            raise ValueError('Q06_HISTORY_FIXTURE_TIME_BUDGET')
    try:
        rpc.attest()
        mining = public_regtest_mining_address(source)
        # Coinbase1 funded the existing single-payment fixture. Mine enough
        # for distinct public coinbases2..254 to be mature without assumptions
        # about subsidy halvings. No wallet-owned input is used or reserved.
        for count in (101, 101, 101, 50):
            bounded()
            rpc._call('generatetoaddress', [str(count), mining])
        submitted = {}
        for height in range(2, 255):
            bounded()
            block = rpc.call('getblock', [rpc.call('getblockhash', [height]), 3])
            tx = block['tx'][0]
            output = next(v for v in tx['vout'] if v['scriptPubKey']['hex'] == p2wpkh(31).hex())
            value = atoms(output['value'])
            inp = Input(tx['txid'], output['n'], p2wpkh(31), witness=(b'\x30', pub(31)), secret=31)
            script = b'\x51\x20' + send((inp,), (receive_code,))[0]
            raw = signed_single_input(inp, value, ((value - 10000, script),), 31)
            txid = rpc.call('sendrawtransaction', [raw])  # Exactly once; no retries.
            if txid in submitted:
                raise ValueError('Q06_HISTORY_FIXTURE_DUPLICATE')
            submitted[txid] = value - 10000
        bounded()
        rpc._call('generatetoaddress', ['1', mining])
        height = rpc.call('getblockcount')
        block = rpc.call('getblock', [rpc.call('getblockhash', [height]), 3])
        canonical = {tx['txid']: tx for tx in block['tx']}
        rows = []
        for txid, value in submitted.items():
            tx = canonical[txid]
            if (len(tx['vout']) != 1 or atoms(tx['vout'][0]['value']) != value
                    or sum(atoms(v['prevout']['value']) for v in tx['vin']) != value + 10000):
                raise ValueError('Q06_HISTORY_CANONICAL_ACCOUNTING_DENIED')
            rows.append(HistoryRow(txid, height, 1, value, 0))
        _owned(owner)
        bounded()
        return tuple(rows)
    finally:
        if rpc._transport is not None:
            rpc._transport.close()


def verify_pages(executor, baseline, extra, *, window=None):
    """Real backend pages, optionally via the existing Qt Older/Newer buttons."""
    from .wallet_read import HistoryRow
    from .history_pages import GUI_HISTORY_LIMIT
    expected = {row.txid: (row.block_height, row.credit_atoms, row.debit_atoms)
                for row in baseline['fusion_snapshot'].history}
    if len(expected) != baseline['fusion_snapshot'].history_count:
        raise ValueError('Q06_HISTORY_FIXTURE_COMPLETE_BASELINE_REQUIRED')
    expected.update({row.txid: (row.block_height, row.credit_atoms, row.debit_atoms) for row in extra})
    head = executor.request('snapshot', timeout=240)
    amount = baseline['confirmed_atoms'] + sum(row.credit_atoms for row in extra)
    if head['available_atoms'] != amount:
        raise ValueError('Q06_HISTORY_AVAILABLE_BALANCE_DENIED')
    rows = tuple(HistoryRow(txid, height, head['height'] - height + 1, credit, debit)
                 for txid, (height, credit, debit) in sorted(expected.items(),
                     key=lambda item: (item[1][0], item[0]), reverse=True))
    def check(view, offset):
        if (view.history_count != len(rows) or view.history_offset != offset
                or view.history != rows[offset:offset + GUI_HISTORY_LIMIT]
                or view.confirmed_atoms != amount
                or view.receive_code != baseline['receive_code']
                or view.mainnet_allowed is not False
                or view.reservation_count != baseline['fusion_snapshot'].reservation_count
                or view.reservation_sha256 != baseline['fusion_snapshot'].reservation_sha256):
            raise ValueError('Q06_HISTORY_PAGE_CUSTODY_OR_CORE_ORACLE_DENIED')
        if view.history_sha256 != head['fusion_snapshot'].history_sha256:
            raise ValueError('Q06_HISTORY_PAGE_FULL_FINGERPRINT_CHANGED')
    check(head['fusion_snapshot'], 0)
    actions = []
    if window is None:
        tail = executor.request('snapshot', GUI_HISTORY_LIMIT, timeout=240)
        check(tail['fusion_snapshot'], GUI_HISTORY_LIMIT)
        head = executor.request('snapshot', 0, timeout=240)
        check(head['fusion_snapshot'], 0)
    else:
        from .desktop import qt_application
        app = qt_application()
        window._on_ready('snapshot', head)
        window.navigation.setCurrentRow(2)
        app.processEvents()
        original = executor.submit
        def observed(action, *args, **kwargs):
            actions.append(action)
            return original(action, *args, **kwargs)
        executor.submit = observed
        def wait(offset):
            deadline = time.monotonic() + 240
            while (window._worker is not None or executor.busy or window._delivering_result
                   or window._last_verified is None or window._last_verified.history_offset != offset):
                app.processEvents()
                if window._last_error_code is not None or time.monotonic() >= deadline:
                    raise ValueError('Q06_HISTORY_GUI_PAGE_DENIED')
                time.sleep(.005)
            check(window._last_verified, offset)
        try:
            if not window.history_page.older.isEnabled():
                raise ValueError('Q06_HISTORY_OLDER_NOT_ENABLED')
            window.history_page.older.click()
            wait(GUI_HISTORY_LIMIT)
            window.history_page.newer.click()
            wait(0)
            if actions != ['snapshot', 'snapshot']:
                raise ValueError('Q06_HISTORY_GUI_NON_READ_DISPATCH')
        finally:
            executor.submit = original
        window.navigation.setCurrentRow(0)
        app.processEvents()
    return head, {'status': 'Q06_GENUINE_CORE_PAGED_HISTORY_PASS',
                  'canonical_history_count': len(rows), 'page_size': GUI_HISTORY_LIMIT,
                  'tail_count': len(rows) - GUI_HISTORY_LIMIT,
                  'gui_snapshot_actions': actions, 'signing_or_broadcast_dispatched': False}
