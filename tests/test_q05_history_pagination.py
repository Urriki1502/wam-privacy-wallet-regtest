"""Bounded complete-history fingerprint; mocks never stand in for native Core."""
from hashlib import sha256
from unittest.mock import Mock
import unittest

from wam_regtest import managed_wallet_checkpoint as module


def _row(index,height,tip):
    return {'confirmations':tip-height+1,'credit':index+1,'debit':0,
            'height':height,'txid':f'{index:064x}'}


def _rows(count,tip=10_000):
    return [_row(i,i+1,tip) for i in range(count)]


class _Txn:
    def __init__(self,store):
        self.store=store

    def __enter__(self):
        if self.store.depth:
            raise RuntimeError('nested BEGIN IMMEDIATE')
        self.store.depth+=1
        self.store.frozen=list(self.store.live)
        self.store.frozen_reservations=list(self.store.reservations)
        self.store.frozen_chain=self.store.chain
        return self

    def __exit__(self,typ,value,tb):
        self.store.depth-=1
        self.store.frozen=None
        self.store.frozen_reservations=None
        self.store.frozen_chain=None


class FakeStore:
    def __init__(self,rows,reservations=(),chain=(10_000,'a'*64)):
        self.live=list(rows)
        self.reservations=list(reservations)
        self.chain=chain
        self.depth=0
        self.frozen=None
        self.frozen_reservations=None
        self.frozen_chain=None

    def transaction(self):
        return _Txn(self)

    def tip(self):
        return self.chain


class FakeDb:
    def __init__(self,store):
        self.store=store

    def execute(self,sql,params=None):
        if sql=='SELECT count(*) FROM history':
            source=self.store.frozen if self.store.depth else self.store.live
            return FakeCursor(((len(source),),))
        if sql.startswith('SELECT txid,vout,token,state,created FROM reservations'):
            source=(self.store.frozen_reservations if self.store.depth
                    else self.store.reservations)
            return FakeCursor(source)
        raise AssertionError(sql)


class FakeCursor:
    def __init__(self,rows):
        self._rows=list(rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def __iter__(self):
        return iter(self._rows)


class FakeWallet:
    def __init__(self,store,mutate=None,page=None):
        self.scanner=FakeScanner(store)
        self.db=FakeDb(store)
        self.store=store
        self.mutate=mutate
        self.page=page
        self.public_history_calls=0

    def history(self,limit=100,offset=0):
        self.public_history_calls+=1
        raise AssertionError('wallet.history() opens a separate SQLite transaction')

    def _history(self,limit,offset):
        if not self.store.depth:
            raise AssertionError('history page read outside snapshot')
        if self.mutate is not None:
            self.mutate(self.store,offset)
        if self.page is not None:
            return self.page(limit,offset,self.store)
        rows=self.store.frozen
        return [dict(row) for row in rows[offset:offset+limit]]

    def _balance(self,min_confirmations):
        if not self.store.depth:
            raise AssertionError('balance read outside snapshot')
        if min_confirmations!=1:
            raise AssertionError(min_confirmations)
        reserved=len(self.store.frozen_reservations)
        return {'confirmed_atoms':len(self.store.frozen),'reserved_atoms':reserved,
                'available_atoms':max(0,len(self.store.frozen)-reserved)}

    def balance(self,min_confirmations=1):
        raise AssertionError('wallet.balance() opens a separate SQLite transaction')


class FakeScanner:
    def __init__(self,store):
        self.store=store
        self.ready=True
        self.synced=0

    def sync(self,rpc):
        self.synced+=1

    def assert_current(self):
        if not self.ready:
            raise ValueError('SCAN_NOT_CURRENT')


class FakeRpc:
    def __init__(self,height,tip):
        self.height=height;self.tip=tip

    def call(self,method):
        if method=='getblockcount':
            return self.height
        if method=='getbestblockhash':
            return self.tip
        raise AssertionError(method)


def _fixtures(rows,reservations=(),chain=None,rpc=None,mutate=None,page=None,
              wallet=None,store=None):
    chain=chain or (10_000,'a'*64)
    store=store or FakeStore(rows,reservations,chain)
    wallet=wallet or FakeWallet(store,mutate=mutate,page=page)
    rpc=rpc or FakeRpc(*chain)
    ring=Mock();ring.accounts.return_value=[Mock(payment_code=lambda:'sp1q-public-fixture')]
    vault=Mock();vault.anchor.wallet_id='b'*32;vault._expected=('c'*64,)
    return ring,wallet.scanner,rpc,vault,wallet


def _observe(rows,reservations=(),**kwargs):
    return module._locked_observation(*_fixtures(rows,reservations,**kwargs))


class HistoryPaginationContracts(unittest.TestCase):
    def test_empty_history_fingerprint_matches_canonical_array(self):
        snap=_observe([])
        self.assertEqual(snap['history_count'],0)
        self.assertEqual(snap['history_sha256'],sha256(module._canonical([])).hexdigest())
        self.assertEqual(snap['signer_allowed'],False)
        self.assertEqual(snap['broadcast_allowed'],False)
        self.assertEqual(snap['mainnet_allowed'],False)

    def test_999_and_1000_and_1001_are_complete_not_truncated(self):
        for count in (999,1000,1001):
            rows=_rows(count)
            snap=_observe(rows)
            self.assertEqual(snap['history_count'],count)
            self.assertEqual(snap['history_sha256'],
                             sha256(module._canonical(rows)).hexdigest())

    def test_2500_records_stream_without_public_history_calls(self):
        rows=_rows(2500)
        store=FakeStore(rows)
        wallet=FakeWallet(store)
        snap=_observe(rows,wallet=wallet,store=store)
        self.assertEqual(snap['history_count'],2500)
        self.assertEqual(snap['history_sha256'],sha256(module._canonical(rows)).hexdigest())
        self.assertEqual(wallet.public_history_calls,0)

    def test_fingerprint_is_deterministic_after_reopen(self):
        rows=_rows(1001)
        reservations=(('d'*64,0,'token-signed','signed',1),
                      ('e'*64,1,'token-uncertain','uncertain',2))
        first=_observe(rows,reservations)
        second=_observe(rows,reservations)
        self.assertEqual(first['history_sha256'],second['history_sha256'])
        self.assertEqual(first['reservation_sha256'],second['reservation_sha256'])
        self.assertEqual(first['reservation_states'],['signed','uncertain'])
        self.assertEqual(first['reservation_count'],2)
        digest=sha256()
        for row in reservations:
            digest.update(module._canonical(list(row))+b'\n')
        count,observed,states=module.reservation_fingerprint(reservations)
        self.assertEqual(observed,digest.hexdigest())
        self.assertEqual(count,2)
        self.assertEqual(states,['signed','uncertain'])
        self.assertEqual(first['reservation_sha256'],observed)

    def test_signed_and_uncertain_reservations_are_not_dropped(self):
        reservations=(('a'*64,0,'t1','signed',9),('b'*64,1,'t2','uncertain',8),
                      ('c'*64,2,'t3','draft',7))
        snap=_observe(_rows(3),reservations)
        self.assertEqual(snap['reservation_states'],['draft','signed','uncertain'])
        self.assertEqual(snap['reserved_atoms'],3)

    def test_concurrent_live_insert_cannot_change_frozen_pages(self):
        rows=_rows(1500)
        extra=_row(9999,9999,10_000)

        def mutate(store,offset):
            if offset and extra not in store.live:
                store.live.append(extra)

        snap=_observe(rows,mutate=mutate)
        self.assertEqual(snap['history_count'],1500)
        self.assertEqual(snap['history_sha256'],sha256(module._canonical(rows)).hexdigest())
        self.assertNotEqual(snap['history_sha256'],
                            sha256(module._canonical(rows+[extra])).hexdigest())

    def test_live_mutation_without_snapshot_is_detected(self):
        rows=_rows(1500)

        def page(limit,offset,store):
            source=list(store.live)
            if offset:
                source=source[offset-1:offset-1+limit]
            else:
                source=source[:limit]
            return [dict(row) for row in source]

        with self.assertRaisesRegex(module.ManagedWalletError,'HISTORY_INCONSISTENT'):
            _observe(rows,page=page)

    def test_chain_tip_change_refuses_before_and_after_history(self):
        with self.assertRaisesRegex(module.ManagedWalletError,'CHAIN_CHANGED'):
            _observe(_rows(2),rpc=FakeRpc(6,'b'*64))
        ring,scanner,rpc,vault,wallet=_fixtures(_rows(2))
        calls={'n':0}
        original=rpc.call

        def later(method):
            calls['n']+=1
            if calls['n']>2:
                return 9 if method=='getblockcount' else 'c'*64
            return original(method)

        rpc.call=later
        with self.assertRaisesRegex(module.ManagedWalletError,'CHAIN_CHANGED'):
            module._locked_observation(ring,scanner,rpc,vault,wallet)

    def test_short_page_before_declared_count_is_inconsistent(self):
        rows=_rows(1001)

        def page(limit,offset,store):
            if offset:
                return []
            return [dict(row) for row in store.frozen[:limit]]

        with self.assertRaisesRegex(module.ManagedWalletError,'HISTORY_INCONSISTENT'):
            _observe(rows,page=page)

    def test_overlapping_pages_are_refused(self):
        rows=_rows(1500)

        def page(limit,offset,store):
            return [dict(row) for row in store.frozen[:limit]]

        with self.assertRaisesRegex(module.ManagedWalletError,'HISTORY_INCONSISTENT'):
            _observe(rows,page=page)

    def test_changed_record_changes_fingerprint(self):
        rows=_rows(1000)
        other=list(rows);other[-1]=dict(other[-1],credit=99)
        self.assertNotEqual(_observe(rows)['history_sha256'],
                            _observe(other)['history_sha256'])

    def test_exactly_complete_max_records_do_not_raise_after_last_full_page(self):
        tip=2_000_000
        count=module.HISTORY_OFFSET_MAX+module.HISTORY_PAGE_LIMIT
        seen,digest=module._fingerprint_history(_GeneratedWallet(count,tip),tip)
        self.assertEqual(seen,count)
        self.assertEqual(len(digest),64)

    def test_one_past_complete_max_is_incomplete(self):
        tip=2_000_000
        count=module.HISTORY_OFFSET_MAX+module.HISTORY_PAGE_LIMIT+1
        with self.assertRaisesRegex(module.ManagedWalletError,'HISTORY_INCOMPLETE'):
            module._fingerprint_history(_GeneratedWallet(count,tip),tip)

    def test_offset_ceiling_refuses_unreadable_tail(self):
        store=FakeStore([])
        wallet=FakeWallet(store)
        with store.transaction():
            store.frozen=['x']*(module.HISTORY_OFFSET_MAX+module.HISTORY_PAGE_LIMIT+1)
            with self.assertRaisesRegex(module.ManagedWalletError,'HISTORY_INCOMPLETE'):
                module._fingerprint_history(wallet,10_000)

    def test_wrong_confirmations_are_inconsistent(self):
        rows=_rows(4)
        rows[2]=dict(rows[2],confirmations=1)

        def page(limit,offset,store):
            return [dict(row) for row in rows[offset:offset+limit]]

        with self.assertRaisesRegex(module.ManagedWalletError,'HISTORY_INCONSISTENT'):
            _observe(rows,page=page)

    def test_public_history_is_not_used_for_checkpoint_pages(self):
        from pathlib import Path
        source=Path(module.__file__).read_text(encoding='utf-8')
        self.assertIn('wallet._history',source)
        self.assertNotIn('history=wallet.history',source)
        self.assertNotIn('limit=1000',source)

    def test_sqlite_autocommit_insert_between_pages_is_detected(self):
        import sqlite3,tempfile,os
        path=tempfile.mkstemp(suffix='.sqlite')[1]
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        db=sqlite3.connect(path,isolation_level=None)
        self.addCleanup(db.close)
        db.execute('CREATE TABLE history(txid TEXT PRIMARY KEY,height INTEGER NOT NULL,'
                   'credit INTEGER NOT NULL,debit INTEGER NOT NULL)')
        db.executemany('INSERT INTO history VALUES(?,?,?,?)',
                       [(f'{i:064x}',i+1,i+1,0) for i in range(1500)])
        wallet=_SqliteWallet(db,10_000)
        first=module._fingerprint_history(wallet,10_000)
        extra=('f'*64,1,1,0)
        calls={'n':0}
        original=wallet._history

        def page(limit,offset):
            calls['n']+=1
            if calls['n']==2:
                db.execute('INSERT INTO history VALUES(?,?,?,?)',extra)
            return original(limit,offset)

        wallet._history=page
        with self.assertRaisesRegex(module.ManagedWalletError,'HISTORY_INCONSISTENT'):
            module._fingerprint_history(wallet,10_000)
        self.assertEqual(first[0],1500)

    def test_sqlite_immediate_snapshot_excludes_blocked_writer(self):
        import sqlite3,tempfile,os,threading
        path=tempfile.mkstemp(suffix='.sqlite')[1]
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        db=sqlite3.connect(path,isolation_level=None,timeout=5)
        self.addCleanup(db.close)
        db.execute('CREATE TABLE history(txid TEXT PRIMARY KEY,height INTEGER NOT NULL,'
                   'credit INTEGER NOT NULL,debit INTEGER NOT NULL)')
        db.executemany('INSERT INTO history VALUES(?,?,?,?)',
                       [(f'{i:064x}',i+1,i+1,0) for i in range(1500)])
        started=threading.Event();done=threading.Event();error=[]

        def writer():
            extra=sqlite3.connect(path,isolation_level=None,timeout=8,
                                  check_same_thread=False)
            try:
                started.set()
                extra.execute('INSERT INTO history VALUES(?,?,?,?)',('f'*64,1,1,0))
            except Exception as exc:
                error.append(exc)
            finally:
                extra.close();done.set()

        db.execute('BEGIN IMMEDIATE')
        thread=threading.Thread(target=writer);thread.start()
        self.assertTrue(started.wait(2))
        wallet=_SqliteWallet(db,10_000)
        count,digest=module._fingerprint_history(wallet,10_000)
        self.assertEqual(count,1500)
        self.assertEqual(digest,sha256(module._canonical(_rows(1500))).hexdigest())
        self.assertFalse(done.is_set())
        db.execute('COMMIT')
        self.assertTrue(done.wait(5));thread.join(5)
        self.assertEqual(error,[])
        self.assertEqual(db.execute('SELECT count(*) FROM history').fetchone()[0],1501)


class _GeneratedWallet:
    def __init__(self,count,tip):
        self.count=count;self.tip=tip;self.db=self

    def execute(self,sql,params=None):
        if sql=='SELECT count(*) FROM history':
            return FakeCursor(((self.count,),))
        raise AssertionError(sql)

    def _history(self,limit,offset):
        if (type(limit) is not int or not 1<=limit<=1000
                or type(offset) is not int or not 0<=offset<=1_000_000):
            raise ValueError('HISTORY_PAGE')
        end=min(self.count,offset+limit)
        if offset>=self.count:
            return []
        return [_row(i,i+1,self.tip) for i in range(offset,end)]


class _SqliteWallet:
    def __init__(self,db,tip):
        self.db=db;self.tip=tip

    def _history(self,limit,offset):
        return [{'confirmations':self.tip-row[1]+1,'credit':row[2],'debit':row[3],
                 'height':row[1],'txid':row[0]}
                for row in self.db.execute(
                    'SELECT txid,height,credit,debit FROM history '
                    'ORDER BY height,txid LIMIT ? OFFSET ?',(limit,offset))]

