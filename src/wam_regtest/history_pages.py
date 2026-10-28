"""Complete WSP history paging under one SQLite snapshot.

Pinned Wallet.history allows limit 1..1000 and offset 0..1_000_000, and each
public history() call starts its own BEGIN IMMEDIATE. Callers must hold one
store.transaction() and read via _history or equivalent SQL, never separate
public history() pages.
"""
from hashlib import sha256
import json
import re

HISTORY_PAGE_LIMIT=1000
HISTORY_OFFSET_MAX=1_000_000
HISTORY_COMPLETE_MAX=HISTORY_OFFSET_MAX+HISTORY_PAGE_LIMIT
_TXID=re.compile('[0-9a-f]{64}\\Z')


class HistoryPageError(ValueError):
    pass


def _canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':')).encode('ascii')


def complete_history(read_page,declared,height,*,collect=False,error=HistoryPageError):
    """Hash every canonical WSP history row; optionally retain rows.

    read_page(limit, offset) must observe the same snapshot as declared.
    Order is WSP canonical: height,txid ascending.
    """
    if type(declared) is not int or declared<0:
        raise error('HISTORY_INCONSISTENT')
    if declared>HISTORY_COMPLETE_MAX:
        raise error('HISTORY_INCOMPLETE')
    digest=sha256(b'[');seen=0;offset=0;previous=None;rows=[] if collect else None
    while True:
        if offset>HISTORY_OFFSET_MAX:
            raise error('HISTORY_INCOMPLETE')
        page=read_page(HISTORY_PAGE_LIMIT,offset)
        if type(page) is not list or len(page)>HISTORY_PAGE_LIMIT:
            raise error('HISTORY_INCONSISTENT')
        if not page:
            break
        for row in page:
            if type(row) is not dict:
                raise error('HISTORY_INCONSISTENT')
            txid,row_height=row.get('txid'),row.get('height')
            if (type(txid) is not str or not _TXID.fullmatch(txid)
                    or type(row_height) is not int or row_height<1):
                raise error('HISTORY_INCONSISTENT')
            order=(row_height,txid)
            if previous is not None and order<=previous:
                raise error('HISTORY_INCONSISTENT')
            if row.get('confirmations')!=height-row_height+1:
                raise error('HISTORY_INCONSISTENT')
            if seen:
                digest.update(b',')
            digest.update(_canonical(row));seen+=1;previous=order
            if collect:
                rows.append(row)
            if seen>declared:
                raise error('HISTORY_INCONSISTENT')
        if len(page)<HISTORY_PAGE_LIMIT or seen==declared:
            break
        offset+=len(page)
    digest.update(b']')
    if seen!=declared:
        raise error('HISTORY_INCONSISTENT')
    return seen,digest.hexdigest(),rows


def sql_history_pages(db,tip_height,sql,error=HistoryPageError,code='HISTORY_DENIED'):
    """Page a stable ORDER BY query; refuse truncation and count mismatch."""
    declared=db.execute('SELECT count(*) FROM history').fetchone()[0]
    if type(declared) is not int or declared<0:
        raise error(code)
    if declared>HISTORY_COMPLETE_MAX:
        raise error(code)
    seen=0;offset=0;out=[]
    while True:
        if offset>HISTORY_OFFSET_MAX:
            raise error(code)
        page=list(db.execute(sql,(HISTORY_PAGE_LIMIT,offset)))
        if len(page)>HISTORY_PAGE_LIMIT:
            raise error(code)
        if not page:
            break
        for txid,block,credit,debit in page:
            if (type(txid) is not str or not _TXID.fullmatch(txid)
                    or type(block) is not int or not 1<=block<=tip_height
                    or type(credit) is not int or type(debit) is not int
                    or not 0<=credit<=22_000_000*100_000_000
                    or not 0<=debit<=22_000_000*100_000_000):
                raise error(code)
            out.append((txid,block,credit,debit,tip_height-block+1))
            seen+=1
            if seen>declared:
                raise error(code)
        if len(page)<HISTORY_PAGE_LIMIT or seen==declared:
            break
        offset+=len(page)
    if seen!=declared:
        raise error(code)
    return out
