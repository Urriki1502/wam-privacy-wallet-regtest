"""F-08 managed REGTEST welcome/connection navigator.

Display only supervisor-authenticated Core status and existing verified-wallet
controls. Never start Core, import secrets, adopt a wallet or enable a signer
by virtue of displaying this screen. Every action must be wired to the
original guarded ManagedCoreWindow control; status text is not authority.
"""
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout
from .fusion_ui import page,panel,label,action,ResponsiveRow


class ManagedWelcomePage(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        root=QVBoxLayout(self)
        root.setContentsMargins(0,0,0,0)
        self.scroll,layout=page(
            'Welcome to WAM Fusion',
            'Connect an owned REGTEST Core, then explicitly create or verify '
            'your encrypted WSP wallet. No automatic imports or transactions.',
            'GET STARTED / REGTEST ONLY')
        root.addWidget(self.scroll)
        state,sl=panel('1 · Connect your own WAM Core',
            'Only the already-authorized, isolated local Core can be started. '
            'A status poll cannot unlock a wallet or confirm a balance.')
        self.core_state=label('Core: unverified','FusionCardValue')
        self.height_state=label('No verified block height')
        sl.addWidget(self.core_state)
        sl.addWidget(self.height_state)
        self.refresh=action('Verify Core status','sync',True)
        self.start=action('Start owned Core','core')
        c=QHBoxLayout();c.addWidget(self.refresh);c.addWidget(self.start);sl.addLayout(c)
        wallet,wl=panel('2 · Create or verify WSP custody',
            'Create a NEW 12/24-word BIP39 wallet only when the vault is '
            'absent. Existing encrypted wallets must be verified; never '
            'overwrite, import automatically or discard descriptors.')
        self.wallet_state=label('Wallet: locked / unverified','FusionCardValue')
        wl.addWidget(self.wallet_state)
        self.create=action('Create new BIP39 wallet','security',True)
        self.verify=action('Verify existing wallet','security')
        wl.addWidget(self.create);wl.addWidget(self.verify)
        layout.addWidget(ResponsiveRow(state,wallet,weights=[1,1],breakpoint=960))
        inspect,il=panel('3 · Import or inspect',
            'Core .dat import is NOT enabled by inspection. Inspect format '
            'only; no RPC import, BDB conversion, key migration or wallet '
            'replacement. Original source stays unchanged.')
        self.inspect=action('Inspect .dat / .enc · NO IMPORT','security')
        il.addWidget(self.inspect)
        see,vl=panel('4 · View, sync or send',
            'A verified read-only snapshot does NOT grant Sign/Broadcast. '
            'REGTEST Send requires a separate passphrase, native custody '
            'check and exact-intent approval.')
        self.view=action('View verified wallet · read only','receive')
        self.sync=action('Sync + save encrypted checkpoint','sync')
        self.send=action('Open guarded REGTEST Send','send',True)
        vl.addWidget(self.view);vl.addWidget(self.sync);vl.addWidget(self.send)
        layout.addWidget(ResponsiveRow(inspect,see,weights=[1,1],breakpoint=960))
        self.security_notice=label(
            'Developer/REGTEST only · mainnet, real funds and '
            'automatic Sign/Broadcast are disabled. Imported keys are preserved.',
            'FusionGold')
        layout.addWidget(self.security_notice)
        layout.addStretch()
        self.controls=(self.refresh,self.start,self.create,self.verify,
                       self.inspect,self.view,self.sync,self.send)
        for button in self.controls:
            button.setEnabled(False)

    def render_status(self, *, state, authenticated, height, wallet_exists):
        # No unverified snapshot or owned miner/pool balance in this view.
        if (type(state) is not str or type(authenticated) is not bool
                or type(wallet_exists) is not bool
                or (height is not None and (type(height) is not int or height<0))):
            raise ValueError('F08_WELCOME_STATUS_DENIED')
        known={
            'error':'Unverified', 'stopped':'Stopped',
            'starting':'Starting', 'syncing':'Syncing',
            'busy':'Busy', 'ready':'Ready',
            'recovery-needed':'Recovery required',
        }
        if state not in known:
            raise ValueError('F08_WELCOME_STATUS_DENIED')
        self.core_state.setText(
            'Core: '+(known[state] if authenticated else 'Unverified'))
        self.height_state.setText(
            'Verified Core height: '+str(height)
            if authenticated and state=='ready' and height is not None
            else 'Verified Core height: unavailable')
        self.wallet_state.setText(
            'Existing encrypted vault · verification required'
            if wallet_exists else 'No existing vault · creation requires a ready Core')
