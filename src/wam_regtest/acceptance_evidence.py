"""Evidence bookkeeping, not a trust oracle or permission to release funds."""
from datetime import datetime, timedelta
import re

KINDS=('SOURCE','CORE_E2E','FROZEN','PHYSICAL','DEV_REVIEWED')
IDENTITY=('code_sha','os','architecture','core_version','wamd_sha256','wam_cli_sha256','wsp_commit')


def effective_status(record,candidate):
    """Missing/SKIP cannot pass; a changed tested dependency invalidates PASS.

    The caller still independently verifies the referenced test/artifact. This
    function never promotes SOURCE into another layer or authenticates JSON.
    """
    if type(record) is not dict or type(candidate) is not dict:return 'PENDING'
    state=record.get('status')
    if state in ('FAIL','STALE'):return state
    if state!='PASS' or record.get('kind') not in KINDS:return 'PENDING'
    identity=record.get('identity')
    if type(identity) is not dict or any(not identity.get(k) or not candidate.get(k) for k in IDENTITY):return 'PENDING'
    if any(identity[k]!=candidate[k] for k in IDENTITY):return 'STALE'
    for field,length in (('code_sha',40),('wsp_commit',40),('wamd_sha256',64),('wam_cli_sha256',64)):
        if type(identity[field]) is not str or not re.fullmatch('[0-9a-f]{'+str(length)+'}',identity[field]):return 'PENDING'
    try:
        when=datetime.fromisoformat(record['tested_utc'].replace('Z','+00:00'))
        if when.utcoffset()!=timedelta(0) or not record.get('test_ref'):return 'PENDING'
    except (ValueError,TypeError,KeyError,AttributeError):return 'PENDING'
    kind=record['kind']
    if kind in ('CORE_E2E','FROZEN') and record.get('genuine_core') is not True:return 'PENDING'
    if kind=='FROZEN' and not (type(record.get('artifact_sha256')) is str and re.fullmatch('[0-9a-f]{64}',record['artifact_sha256']) and record.get('final_entrypoint') is True):return 'PENDING'
    if kind in ('PHYSICAL','DEV_REVIEWED') and not record.get('authorized_operator_receipt'):return 'PENDING'
    return 'PASS'
