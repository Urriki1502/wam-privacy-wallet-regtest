"""Read-only owner scope proposal review. Never activates or bypasses Q-GATE."""
from .q_gate import ORDER, validate

DE_SCOPED = ('Q07', 'Q08', 'Q09', 'Q17')
FUTURE_ORDER = tuple(q for q in ORDER[9:] if q not in DE_SCOPED)


def review_scope_draft(ledger, proposal):
    """Conversation authority records a draft; integration needs real governance.

    A URL-shaped string alone is not authenticated authorization. This function
    deliberately supports only the unresolved proposal, never live activation.
    The canonical ledger remains intact and is validated with the original rules.
    """
    current = validate(ledger)
    if (type(proposal) is not dict or set(proposal) != {
            'schema', 'status', 'owner_decision_url', 'owner_de_scoped',
            'future_engineering_order'}
            or proposal['schema'] != 'wam-v1-owner-scope-proposal/v1'
            or proposal['status'] != 'PROPOSED'
            or proposal['owner_decision_url'] is not None
            or proposal['owner_de_scoped'] != list(DE_SCOPED)
            or proposal['future_engineering_order'] != list(FUTURE_ORDER)):
        raise ValueError('V1_SCOPE_DRAFT_INVALID')
    failures = sorted(c['id'] for q in ledger['questions'] for c in q['cases']
                      if c['status'] == 'FAIL')
    return {
        'status': 'PENDING_AUTHENTICATED_GOVERNANCE',
        'active_q': current['active_q'],
        'owner_de_scoped': list(DE_SCOPED),
        'future_engineering_order': list(FUTURE_ORDER),
        'historical_failures': failures,
        'in_scope_failures': [c for c in failures if c.split('-', 1)[0] not in DE_SCOPED],
        'engineering_transition_allowed': False,
        'acceptance_granted': False,
        'mainnet_allowed': False,
    }
