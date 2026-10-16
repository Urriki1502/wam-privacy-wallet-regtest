"""Presentation only: Core account amounts never augment WSP payment balance."""
import re
from .fusion_ui import page, panel, label, ResponsiveRow
from .mining_read import MiningSnapshot
from .mining_account import MiningWalletBalance, RewardSplit
from .wallet_read import format_wam


class MiningAccountPage:
    def __init__(self):
        self.widget, layout = page('Mining Account',
            'Read-only Core account · disposable REGTEST. Separate from the silent-payment account.',
            'CORE / MINING ACCOUNT')
        self.state = label('Not verified · Sync required', 'FusionGold')
        layout.addWidget(self.state)
        self.values = {}
        cards = []
        for field, title, detail in (
            ('available_atoms', 'Core eligible', 'Safe, spendable UTXOs checked against gettxout. Not WSP spend authority.'),
            ('immature_atoms', 'Immature coinbase', 'Unavailable at depths 99 and 100. Core wallet eligibility starts at depth 101.'),
            ('trusted_atoms', 'Core trusted', 'May include trusted unconfirmed change. Not a confirmed or spendable total.'),
            ('pending_untrusted_atoms', 'Pending / untrusted', 'Excluded from available funds.')):
            card, inner = panel(title, detail)
            value = label('—', 'FusionCardValue', True)
            value.setAccessibleName(title+' in WAM')
            inner.addWidget(value);self.values[field] = value;cards.append(card)
        layout.addWidget(ResponsiveRow(*cards[:2]));layout.addWidget(ResponsiveRow(*cards[2:]))
        rules, inner = panel('WAM REGTEST reward rules',
            'The next-block split is a network rule, not an owned balance or a promise of mining income.')
        self.reward = label('—', 'FusionInfo', True);inner.addWidget(self.reward)
        inner.addWidget(label('REGTEST halves every 150 blocks. Treasury receives 5% of subsidy only through height 400000, then zero. All transaction fees go to the miner. Genesis is excluded.'))
        inner.addWidget(label('WAM target interval: 120 seconds · probabilistic, never a confirmation guarantee.'))
        layout.addWidget(rules)
        layout.addWidget(label('No Core signing, key export, import or treasury ownership. This page cannot release Fusion reservations or transfer funds between accounts.', 'FusionGold'))
        layout.addStretch()

    def render_snapshot(self, snapshot):
        if snapshot is None:
            self.state.setText('Not verified · Sync required')
            for value in self.values.values():value.setText('—')
            self.reward.setText('—');return
        try:
            if (type(snapshot) is not MiningSnapshot or type(snapshot.balance) is not MiningWalletBalance
                    or type(snapshot.next_reward) is not RewardSplit or type(snapshot.height) is not int
                    or not 0 <= snapshot.height < 1_000_000
                    or type(snapshot.tip) is not str or not re.fullmatch('[0-9a-f]{64}',snapshot.tip)
                    or snapshot.balance.available_atoms > snapshot.balance.trusted_atoms):raise ValueError
            amounts={k:format_wam(getattr(snapshot.balance,k))+' WAM' for k in self.values}
            r=snapshot.next_reward
            if r != RewardSplit.regtest(snapshot.height+1):raise ValueError
            reward=(f'Next height {snapshot.height+1} · subsidy {format_wam(r.subsidy_atoms)} WAM\n'
                    f'Treasury {format_wam(r.treasury_atoms)} WAM · miner subsidy {format_wam(r.miner_atoms)} WAM + fees')
        except (TypeError, ValueError, AttributeError):
            self.render_snapshot(None);raise ValueError('MINING_GUI_SNAPSHOT_DENIED') from None
        for k,value in amounts.items():self.values[k].setText(value)
        self.state.setText(f'Verified owned Core account · height {snapshot.height} · treasury excluded')
        self.reward.setText(reward)
