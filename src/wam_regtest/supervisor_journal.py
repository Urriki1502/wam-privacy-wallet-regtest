"""Native create-only lifecycle journal; never a foreign-process capability.

Authenticated chaining detects partial/divergent publication. Root custody and
the held supervisor lease provide the writer boundary. Like the control token,
this is not an independent witness against full same-user/OS rollback.
"""
from hashlib import sha256
import hmac
import json
import re
import secrets

from .supervisor_protocol import _distinct
from .supervisor_store import create_once,read_exact

SCHEMA='wam-managed-lifecycle/v1'
STATES=frozenset(('CLEAN','STARTING','RUNNING','STOPPING','FAULT','RECOVERING'))
MAX_EVENTS=100000  # Lifecycle events, not status/IPC calls. No silent compaction.
TRANSITIONS={None:{'CLEAN'},'CLEAN':{'STARTING'},'STARTING':{'RUNNING','FAULT'},
             'RUNNING':{'STOPPING','FAULT','RECOVERING'},
             'STOPPING':{'CLEAN','FAULT','RECOVERING'},'FAULT':{'STOPPING','RECOVERING'},
             'RECOVERING':{'STARTING','FAULT'}}


class JournalError(ValueError):pass


def _canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':')).encode('ascii')


class LifecycleJournal:
    def __init__(self,root,profile,secret,directory,*,fresh=False):
        if type(secret) is not bytes or len(secret)!=32:
            raise JournalError('MANAGED_JOURNAL_KEY_DENIED')
        self.root,self.profile,self.directory=root,profile,directory
        self.__secret=secret
        self.owner=secrets.token_hex(16)
        info=directory.stat()
        self.identity=[info.st_dev,info.st_ino]
        self.events=[]
        self._read()
        if not self.events:
            if not fresh:raise JournalError('MANAGED_LEGACY_JOURNAL_REQUIRED')
            self.append('CLEAN')

    def _read(self):
        info=self.directory.stat()
        if self.directory.is_symlink() or [info.st_dev,info.st_ino]!=self.identity:
            raise JournalError('MANAGED_JOURNAL_DATADIR_CHANGED')
        names=sorted(p.name for p in self.root.iterdir()
                     if p.name.startswith('supervisor.event.'))
        if len(names)>MAX_EVENTS:raise JournalError('MANAGED_JOURNAL_CAPACITY')
        events=[];previous='0'*64
        try:
            for seq,name in enumerate(names,1):
                if name!=f'supervisor.event.{seq:06d}':raise ValueError
                raw=read_exact(self.root,name)
                row=json.loads(raw.decode('ascii'),object_pairs_hook=_distinct)
                if type(row) is not dict or set(row)!={'schema','seq','profile_id','owner',
                        'state','core_pid','datadir_identity','previous','mac'}:raise ValueError
                mac=row.pop('mac')
                if (row['schema']!=SCHEMA or type(row['seq']) is not int or row['seq']!=seq
                        or row['profile_id']!=self.profile['profile_id']
                        or row['datadir_identity']!=self.identity
                        or type(row['owner']) is not str or not re.fullmatch('[0-9a-f]{32}',row['owner'])
                        or row['state'] not in STATES or row['previous']!=previous
                        or row['state'] not in TRANSITIONS[events[-1]['state'] if events else None]
                        or row['core_pid'] is not None and
                           (type(row['core_pid']) is not int or not 1<=row['core_pid']<2**31)
                        or type(mac) is not str or not re.fullmatch('[0-9a-f]{64}',mac)
                        or not hmac.compare_digest(mac,hmac.digest(self.__secret,
                            SCHEMA.encode()+b'\n'+_canonical(row),'sha256').hex())):raise ValueError
                row['mac']=mac;events.append(row);previous=sha256(raw).hexdigest()
        except (OSError,ValueError,TypeError,KeyError,UnicodeError):
            raise JournalError('MANAGED_JOURNAL_UNVERIFIED') from None
        self.events=events;self.previous=previous

    @property
    def state(self):return self.events[-1]['state'] if self.events else None

    def reserve_start(self):
        self._read()
        # Keep failure/stop records available even at capacity. Never exhaust
        # publication space only after a child has already been launched.
        if len(self.events)>MAX_EVENTS-16:
            raise JournalError('MANAGED_JOURNAL_CAPACITY')

    def append(self,state,pid=None):
        if state not in STATES or pid is not None and (type(pid) is not int or not 1<=pid<2**31):
            raise JournalError('MANAGED_JOURNAL_STATE_DENIED')
        self._read()
        if state not in TRANSITIONS[self.state]:raise JournalError('MANAGED_JOURNAL_TRANSITION_DENIED')
        if len(self.events)>=MAX_EVENTS:raise JournalError('MANAGED_JOURNAL_CAPACITY')
        row={'schema':SCHEMA,'seq':len(self.events)+1,'profile_id':self.profile['profile_id'],
             'owner':self.owner,'state':state,'core_pid':pid,'datadir_identity':self.identity,
             'previous':self.previous}
        row['mac']=hmac.digest(self.__secret,SCHEMA.encode()+b'\n'+_canonical(row),'sha256').hex()
        raw=_canonical(row)
        create_once(self.root,f"supervisor.event.{row['seq']:06d}",raw)
        self.events.append(row);self.previous=sha256(raw).hexdigest()
