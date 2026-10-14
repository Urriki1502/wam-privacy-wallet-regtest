"""Wallet-local selected-record consent; no ownership proof or remote API.

Adapted from reviewed wam-privacy PR #53 scope/one-use/revocation patterns.
Issuance belongs to authenticated trusted wallet/UI code, never RPC clients.
"""
from dataclasses import dataclass
import hashlib,hmac,json,secrets,time

FIELDS=frozenset(('txid','block_height','credit_atoms','debit_atoms'))

class DisclosureError(ValueError): pass

@dataclass(frozen=True,repr=False)
class LocalConsent:
    nonce:str
    session:str
    wallet:str
    anchor:tuple
    record_digest:str
    fields:tuple
    expires:float
    mac:str


def canonical(data): return json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(record):
    if (type(record) is not dict or set(record)!=FIELDS or type(record['txid']) is not str
            or len(record['txid'])!=64 or any(c not in '0123456789abcdef' for c in record['txid'])
            or type(record['block_height']) is not int or not 0<=record['block_height']<2**31
            or any(type(record[k]) is not int or not 0<=record[k]<=22_000_000*100_000_000
                   for k in ('credit_atoms','debit_atoms'))):
        raise DisclosureError('LOCAL_DISCLOSURE_RECORD_DENIED')
    return hashlib.sha256(canonical(record)).hexdigest()


class LocalDisclosureGate:
    def __init__(self,wallet_id,clock=time.monotonic):
        if type(wallet_id) is not str or len(wallet_id)!=32 or any(c not in '0123456789abcdef' for c in wallet_id):
            raise DisclosureError('LOCAL_DISCLOSURE_SCOPE_DENIED')
        self.wallet=wallet_id;self.session=secrets.token_hex(16)
        self._key=bytearray(secrets.token_bytes(32));self._issued={};self._clock=clock;self.closed=False
        self.audit=()
    def event(self,code): self.audit=(self.audit+(code,))[-128:]
    def payload(self,ticket):
        return {'nonce':ticket.nonce,'session':ticket.session,'wallet':ticket.wallet,
                'anchor':ticket.anchor,'record_digest':ticket.record_digest,
                'fields':ticket.fields,'expires':ticket.expires,'network':'regtest'}
    def mac(self,payload): return hmac.new(self._key,b'WAM/REGTEST/LocalDisclosure/v1\0'+canonical(payload),hashlib.sha256).hexdigest()
    def issue(self,record,fields,anchor,*,approved,authenticated):
        if (self.closed or approved is not True or authenticated is not True or type(fields) is not tuple
                or not 1<=len(fields)<=4 or any(type(f) is not str or f not in FIELDS for f in fields)
                or tuple(sorted(set(fields)))!=fields or len(self._issued)>=32
                or type(anchor) is not tuple or len(anchor)!=2 or type(anchor[0]) is not int or not 1<=anchor[0]<10**9
                or type(anchor[1]) is not str or len(anchor[1])!=64 or any(c not in '0123456789abcdef' for c in anchor[1])):
            self.event('DISCLOSE_DENIED');raise DisclosureError('LOCAL_DISCLOSURE_CONSENT_DENIED')
        try: record_hash=digest(record)
        except DisclosureError:
            self.event('DISCLOSE_DENIED')
            raise
        ticket=LocalConsent(secrets.token_hex(16),self.session,self.wallet,anchor,record_hash,fields,self._clock()+30.0,'')
        from dataclasses import replace
        ticket=replace(ticket,mac=self.mac(self.payload(ticket)))
        self._issued[ticket.nonce]=ticket.mac
        return ticket
    def release(self,ticket,record,anchor):
        try:
            if (self.closed or type(ticket) is not LocalConsent or ticket.session!=self.session
                    or ticket.wallet!=self.wallet or ticket.anchor!=anchor or self._clock()>=ticket.expires
                    or self._issued.get(ticket.nonce)!=ticket.mac or digest(record)!=ticket.record_digest
                    or not hmac.compare_digest(ticket.mac,self.mac(self.payload(ticket)))):
                raise DisclosureError('LOCAL_DISCLOSURE_AUTHORIZATION_DENIED')
            # Consume before returning selected facts; no hidden tx/resource ID.
            del self._issued[ticket.nonce]
            result={'schema':1,'network':'regtest','facts':{k:record[k] for k in ticket.fields},'ownership_proof':False}
            self.event('DISCLOSE_RELEASED')
            return result
        except Exception:
            self.event('DISCLOSE_DENIED');raise DisclosureError('LOCAL_DISCLOSURE_AUTHORIZATION_DENIED') from None
    def revoke(self,ticket):
        if type(ticket) is LocalConsent: self._issued.pop(ticket.nonce,None)
        self.event('DISCLOSE_REVOKED')
    def close(self):
        self._issued.clear();self._key[:]=bytes(len(self._key));self.closed=True;self.event('DISCLOSE_REVOKED')
