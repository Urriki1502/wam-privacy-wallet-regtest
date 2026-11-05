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
                        'Snapshot includes the pinned Core binary. The Core process is not connected.')
            if core_alive is True:
                return ('verified', 'Identity pinned',
                        'Pinned WAM Core binary identity from this verified snapshot.')
            return ('warning', 'Identity pinned',
                    'Pinned Core binary is in this snapshot. Live process is not confirmed here.')
        if busy:
            return ('pending', 'Verifying', 'Checking owned Core identity. No wallet values yet.')
        if core_alive is False:
            return ('unknown', 'Not connected', 'Owned Core process is not running.')
        if core_alive is True:
            return ('pending', 'Core running', 'Owned Core is alive. Wallet snapshot is not verified yet.')
        return ('unknown', 'Not verified', 'Pinned Core identity appears after a verified snapshot.')
    if kind == 'chain':
        if snap is not None:
            return ('verified', 'Height ' + str(snap.height),
                    'Verified tip height from this snapshot. Not a live peer count.')
        if busy:
            return ('pending', 'Syncing', 'Waiting for a verified chain snapshot.')
        return ('unknown', 'Not verified', 'Chain height appears after a verified snapshot.')
    if kind == 'security':
        if locked or snap is None or not operational:
            return ('unknown', 'Locked',
                    'Unlock requires the original wallet password. Locked is the custody state.')
        return ('warning', 'Unlocked',
                'Keys are open on this device. Unlocked is not a security score or Core proof.')
    if kind == 'network':
        shared = bool(network.get('shared'))
        if 'peer_count' in network and type(network['peer_count']) is int:
            if network.get('connected') is False:
                return ('error', 'Disconnected',
                        str(network['peer_count']) + ' peer(s) reported disconnected.')
            if network.get('connected') is True:
                return ('verified', 'Connected',
                        str(network['peer_count']) + ' verified peer(s). Shared REGTEST only.')
            return ('warning', 'Peer check',
                    str(network['peer_count']) + ' peer(s) reported without a connection flag.')
        if shared:
            return ('pending' if busy else 'unknown', 'Awaiting peer check',
                    'Shared REGTEST peer state is shown only after a verified network check.')
        return ('unknown', 'Isolated', 'Zero-peer isolated REGTEST profile. Not a public network.')
    if snap is not None:
        return ('verified', 'Snapshot verified', 'Wallet values come from this verified REGTEST snapshot.')
    if busy:
        return ('pending', 'Verifying', 'Refreshing owned Core and WSP state.')
    if core_alive is True:
        return ('pending', 'Core running', 'Owned Core is alive. Snapshot is not verified yet.')
    return ('unknown', 'Snapshot not verified', 'Header reports wallet snapshot state, not Core identity.')


def never_green_when_unknown(state):
    return state in STATES and state != 'verified'
