"""Semantic GUI status from verified backend facts. Never invents Core health."""
from __future__ import annotations

STATES = ('unknown', 'pending', 'verified', 'warning', 'error')


def classify(kind, *, snap=None, locked=False, operational=False, faulted=False,
             core_alive=None, busy=False, network=None):
    """Map one indicator to (state, title, detail). Unknown is not verified."""
    network = network or {}
    if kind not in ('core', 'chain', 'security', 'network', 'snapshot'):
        raise ValueError('FUSION_STATUS_KIND_DENIED')
    if faulted:
        if kind == 'security':
            return ('error', 'Faulted',
                    'Original reservations are preserved. Do not retry uncertain payments.')
        if kind == 'snapshot':
            return ('error', 'Core error', 'Owned Core reported a fault.')
        if kind == 'core':
            return ('error', 'Core fault', 'Owned Core reported a fault. Reservations stay preserved.')
    if kind == 'core':
        if snap is not None:
            if core_alive is False:
                return ('warning', 'Identity pinned',
                        'Pinned binary · Core not connected')
            if core_alive is True:
                return ('verified', 'Identity pinned',
                        'Pinned binary from this snapshot')
            return ('warning', 'Identity pinned',
                    'Pinned binary · live process unconfirmed')
        if busy:
            return ('pending', 'Verifying', 'Checking owned Core identity')
        if core_alive is False:
            return ('unknown', 'Not connected', 'Owned Core is not running')
        if core_alive is True:
            return ('pending', 'Core running', 'Process alive · snapshot not verified')
        return ('unknown', 'Not verified', 'Identity appears after a verified snapshot')
    if kind == 'chain':
        if snap is not None:
            return ('verified', 'Height ' + str(snap.height),
                    'Verified snapshot height')
        if busy:
            return ('pending', 'Syncing', 'Waiting for a verified snapshot')
        return ('unknown', 'Not verified', 'Height appears after a verified snapshot')
    if kind == 'security':
        if locked or snap is None or not operational:
            return ('unknown', 'Locked',
                    'Password required to unlock')
        return ('warning', 'Unlocked',
                'Keys open · not a security score')
    if kind == 'network':
        shared = bool(network.get('shared'))
        if 'peer_count' in network and type(network['peer_count']) is int:
            if network.get('connected') is False:
                return ('error', 'Disconnected',
                        str(network['peer_count']) + ' peer(s) disconnected')
            if network.get('connected') is True:
                return ('verified', 'Connected',
                        str(network['peer_count']) + ' verified peer(s)')
            return ('warning', 'Peer check',
                    str(network['peer_count']) + ' peer(s) without a connection flag')
        if shared:
            return ('pending' if busy else 'unknown', 'Awaiting peer check',
                    'Peer state follows a verified network check')
        return ('unknown', 'Isolated', 'Zero-peer REGTEST')
    if snap is not None:
        return ('verified', 'Snapshot verified', 'Wallet values come from this verified REGTEST snapshot.')
    if busy:
        return ('pending', 'Verifying', 'Refreshing owned Core and WSP state.')
    if core_alive is True:
        return ('pending', 'Core running', 'Owned Core is alive. Snapshot is not verified yet.')
    return ('unknown', 'Snapshot not verified', 'Header reports wallet snapshot state, not Core identity.')


def never_green_when_unknown(state):
    return state in STATES and state != 'verified'
