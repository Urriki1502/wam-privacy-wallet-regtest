"""Shared complete-history paging; no Core and no native qualification."""
from hashlib import sha256
import sqlite3
import tempfile
import os
import unittest

from wam_regtest.history_pages import (
    GUI_HISTORY_LIMIT,HISTORY_COMPLETE_MAX,HISTORY_PAGE_LIMIT,complete_history,
    sql_history_pages,_canonical)
from wam_regtest.wallet_read import HistoryRow


def _row(index,height,tip):
    return {'confirmations':tip-height+1,'credit':index+1,'debit':0,
            'height':height,'txid':f'{index:064x}'}


class HistoryPagesContracts(unittest.TestCase):
    def test_sql_pages_include_exactly_1000_and_1001(self):
        descriptor,path=tempfile.mkstemp(suffix='.sqlite');os.close(descriptor)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        db=sqlite3.connect(path,isolation_level=None)
        self.addCleanup(db.close)
        db.execute('CREATE TABLE history(txid TEXT PRIMARY KEY,height INTEGER NOT NULL,'
                   'credit INTEGER NOT NULL,debit INTEGER NOT NULL)')
        for count in (0,999,1000,1001,2500):
            db.execute('DELETE FROM history')
            db.executemany('INSERT INTO history VALUES(?,?,?,?)',
                           [(f'{i:064x}',i+1,i+1,0) for i in range(count)])
            db.execute('BEGIN IMMEDIATE')
            declared,raw=sql_history_pages(
                db,10_000,
                'SELECT txid,height,credit,debit FROM history '
                'ORDER BY height DESC,txid LIMIT ? OFFSET ?')
            db.execute('COMMIT')
            self.assertEqual(declared,count)
            self.assertEqual(len(raw),count)
            if count:
                self.assertEqual(raw[0][1],count)  # newest height first

    def test_complete_history_collect_matches_canonical_fingerprint(self):
        rows=[_row(i,i+1,1001) for i in range(1001)]
        def page(limit,offset):
            return [dict(r) for r in rows[offset:offset+limit]]
        count,digest,collected=complete_history(page,len(rows),1001,collect=True)
        self.assertEqual(count,1001)
        self.assertEqual(collected,rows)
        self.assertEqual(digest,sha256(_canonical(rows)).hexdigest())
        newest=tuple(HistoryRow(r['txid'],r['height'],r['confirmations'],r['credit'],r['debit'])
                     for r in reversed(collected))
        self.assertEqual(newest[0].block_height,1001)

    def test_keep_tail_bounds_gui_memory_without_changing_fingerprint(self):
        rows=[_row(i,i+1,3000) for i in range(2500)]
        def page(limit,offset):
            return [dict(r) for r in rows[offset:offset+limit]]
        full=complete_history(page,len(rows),3000,collect=True)
        tail=complete_history(page,len(rows),3000,keep_tail=GUI_HISTORY_LIMIT)
        self.assertEqual(full[0],2500)
        self.assertEqual(full[1],tail[1])
        self.assertEqual(len(tail[2]),GUI_HISTORY_LIMIT)
        self.assertEqual(tail[2],rows[-GUI_HISTORY_LIMIT:])
        descriptor,path=tempfile.mkstemp(suffix='.sqlite');os.close(descriptor)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        db=sqlite3.connect(path,isolation_level=None);self.addCleanup(db.close)
        db.execute('CREATE TABLE history(txid TEXT PRIMARY KEY,height INTEGER NOT NULL,'
                   'credit INTEGER NOT NULL,debit INTEGER NOT NULL)')
        db.executemany('INSERT INTO history VALUES(?,?,?,?)',
                       [(f'{i:064x}',i+1,i+1,0) for i in range(2500)])
        count,raw=sql_history_pages(
            db,10_000,
            'SELECT txid,height,credit,debit FROM history '
            'ORDER BY height DESC,txid LIMIT ? OFFSET ?',window=GUI_HISTORY_LIMIT)
        self.assertEqual(count,2500)
        self.assertEqual(len(raw),GUI_HISTORY_LIMIT)
        self.assertEqual(raw[0][1],2500)

    def test_skip_newest_window_does_not_change_fingerprint(self):
        rows=[_row(i,i+1,3000) for i in range(800)]
        def page(limit,offset):
            return [dict(r) for r in rows[offset:offset+limit]]
        full=complete_history(page,len(rows),3000,collect=True)
        older=complete_history(page,len(rows),3000,keep_tail=GUI_HISTORY_LIMIT,
                               skip_newest=GUI_HISTORY_LIMIT)
        self.assertEqual(full[1],older[1])
        self.assertEqual(len(older[2]),GUI_HISTORY_LIMIT)
        self.assertEqual(older[2],rows[-2*GUI_HISTORY_LIMIT:-GUI_HISTORY_LIMIT])
        newest=complete_history(page,len(rows),3000,keep_tail=GUI_HISTORY_LIMIT)
        self.assertEqual(newest[2],rows[-GUI_HISTORY_LIMIT:])
        descriptor,path=tempfile.mkstemp(suffix='.sqlite');os.close(descriptor)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        db=sqlite3.connect(path,isolation_level=None);self.addCleanup(db.close)
        db.execute('CREATE TABLE history(txid TEXT PRIMARY KEY,height INTEGER NOT NULL,'
                   'credit INTEGER NOT NULL,debit INTEGER NOT NULL)')
        db.executemany('INSERT INTO history VALUES(?,?,?,?)',
                       [(f'{i:064x}',i+1,i+1,0) for i in range(800)])
        count,raw=sql_history_pages(
            db,10_000,
            'SELECT txid,height,credit,debit FROM history '
            'ORDER BY height DESC,txid LIMIT ? OFFSET ?',
            window=GUI_HISTORY_LIMIT,skip=GUI_HISTORY_LIMIT)
        self.assertEqual(count,800)
        self.assertEqual(len(raw),GUI_HISTORY_LIMIT)
        self.assertEqual(raw[0][1],800-GUI_HISTORY_LIMIT)

    def test_future_height_or_nonpositive_confirmations_are_inconsistent(self):
        tip=10
        def page(limit,offset,rows):
            return [dict(r) for r in rows[offset:offset+limit]]
        future=[_row(0,11,tip)]
        future[0]['confirmations']=0
        with self.assertRaisesRegex(Exception,'HISTORY_INCONSISTENT'):
            complete_history(lambda limit,offset:page(limit,offset,future),1,tip,collect=True)
        bad=[_row(0,5,tip)]
        bad[0]['confirmations']=0
        with self.assertRaisesRegex(Exception,'HISTORY_INCONSISTENT'):
            complete_history(lambda limit,offset:page(limit,offset,bad),1,tip,collect=True)

    def test_skip_newest_without_window_is_inconsistent(self):
        rows=[_row(i,i+1,10) for i in range(3)]
        def page(limit,offset):
            return [dict(r) for r in rows[offset:offset+limit]]
        with self.assertRaisesRegex(Exception,'HISTORY_INCONSISTENT'):
            complete_history(page,len(rows),10,skip_newest=1)

    def test_complete_max_constant_matches_wsp_offset_plus_page(self):
        self.assertEqual(HISTORY_COMPLETE_MAX,1_000_000+HISTORY_PAGE_LIMIT)

    def test_checkpoint_path_uses_complete_history_in_single_snapshot(self):
        from pathlib import Path
        root=Path(__file__).resolve().parents[1]
        checkpoint=(root/'src/wam_regtest/managed_wallet_checkpoint.py').read_text(encoding='utf-8')
        self.assertNotIn('wallet.history(',checkpoint)
        self.assertIn('complete_history(',checkpoint)
        self.assertIn('with scanner.store.transaction():',checkpoint)
        self.assertIn('wallet._balance(1)',checkpoint)
