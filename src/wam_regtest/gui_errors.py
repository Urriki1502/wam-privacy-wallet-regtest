"""Fixed public UX categories. Never format exception text or authorize recovery."""
INPUT_ERRORS=frozenset(('WALLET_INPUT_AMOUNT_INVALID','WALLET_INPUT_FEE_INVALID',
                        'WALLET_INPUT_RECIPIENT_INVALID','WALLET_INPUT_FUNDS_UNAVAILABLE'))
_MESSAGES={
 'WALLET_CORE_REAUTHENTICATION_REQUIRED':'Explicit approval to reauthenticate the original REGTEST Core is required after wallet passphrase and custody verification. No automatic retry or external node adoption is allowed.',

 'WALLET_CORE_AUTHENTICATION_DENIED':'Local Core authentication failed. Balances are hidden and sensitive operations are stopped. Verify the authorized local credentials, then explicitly reauthenticate. Wallet state and reservations are retained.',
 'WALLET_CORE_IDENTITY_DENIED':'Local Core identity or private configuration changed. Balances are hidden and sensitive operations are stopped. Verify the original REGTEST node before authenticated reopening; do not reset custody.',
 'WALLET_CORE_UNAVAILABLE':'The verified local Core is unavailable. Balances are hidden and sensitive operations are stopped. Check the authorized local node; no request is retried automatically.',
 'WALLET_CORE_UNVERIFIED':'Core verification failed. Balances are hidden and sensitive operations are stopped. Explicitly verify the original REGTEST environment before authenticated reopening. Reservations remain protected.',

 'WALLET_INPUT_AMOUNT_INVALID':'Amount not accepted. Enter 0.00000330 to 22000000 WAM, using a decimal point and at most 8 decimal places.',
 'WALLET_INPUT_FEE_INVALID':'Fee not accepted. Enter 0.00000001 to 0.01000000 WAM, using a decimal point and at most 8 decimal places.',
 'WALLET_INPUT_RECIPIENT_INVALID':'Recipient not accepted. Use the complete REGTEST silent-payment code (wamrtsp1…). Ordinary Core addresses, other networks and invalid checksums are not supported.',
 'WALLET_INPUT_FUNDS_UNAVAILABLE':'Not enough available confirmed funds in one privacy cluster for the amount and fee. Reserved or pending inputs stay unavailable; locks are not released.',
 'WALLET_STALE_SESSION_DENIED':'Wallet session is stale. Sensitive operations are stopped and reservations retained. Use the latest anchored backup; do not reset or replace the anchor.',
 'WALLET_REVIEW_CHAIN_CHANGED':'The chain changed after review. Recheck the live chain. Only an unsigned draft may be canceled; signed reservations stay locked.',
 'WALLET_REVIEW_UTXO_CHANGED':'A reviewed input is no longer available. Signing or broadcast was refused. Reservations remain protected.',
 'WALLET_PAYMENT_ALREADY_PENDING':'A payment review is already active. Finish that review or cancel its unsigned draft before preparing another.',
 'WALLET_SIGN_UNCERTAIN_LOCK_RETAINED':'Signing did not complete safely. Input reservations are irreversible. Do not retry automatically or release the locks.',
 'WALLET_BROADCAST_UNCERTAIN_LOCK_RETAINED':'Broadcast result is uncertain. The node may have accepted the transaction. Do not retry automatically; reservations remain locked.',
 'WALLET_ROOT_LEASE_UNCERTAIN_LOCK_RETAINED':'The independent custody lease was lost. Operations are stopped and reservations retained. Do not reset the witness or retry automatically.',
 'WALLET_BACKUP_STALE_OR_TAMPERED':'This backup does not match the latest anchored checkpoint. Choose the current unmodified backup; do not reset the anchor.',
 'WALLET_UNLOCK_REFUSED':'Could not unlock: passphrase, encrypted snapshot or custody verification failed. The wallet remains locked. Check the passphrase and latest backup; do not reset custody.',
 'WALLET_RECOVERY_REFUSED':'Recovery was refused: backup authentication, freshness or custody could not be verified. The wallet remains locked; use the latest same-platform backup.',
 'WALLET_BACKUP_DIRECTORY_DENIED':'Backup destination was refused. Choose a new private folder owned by this account, without links or inherited access.',
 'WALLET_LOCKED_OR_FAULTED':'Wallet is locked or faulted. Balances are hidden and sensitive operations are unavailable; reservations remain protected.',
 'WALLET_SYNC_UNVERIFIED':'Live REGTEST synchronization could not be verified. Balances are hidden. Verify the local node and use Sync again; do not reset custody.',
 'WALLET_HISTORY_INCONSISTENT':'Confirmed history pages do not form one complete snapshot. Balances are hidden. Do not treat a truncated list as the wallet; verify the local node and latest checkpoint.',
 'WALLET_RESERVATION_INCONSISTENT':'Input reservations do not form one complete snapshot. Balances are hidden. Signed and uncertain locks stay in place; do not release them or treat a partial list as the wallet.',
 'WALLET_HISTORY_INCOMPLETE':'Confirmed history exceeds the readable WSP page range. Balances are hidden. Do not silently omit older records.',
 'WALLET_OWNED_OPEN_DENIED':'Could not open the managed REGTEST wallet on the original Core owner. Reservations and encrypted checkpoints are retained; do not adopt another process or delete unknown runtime files.',
 'WALLET_EXISTING_RUNTIME_DENIED':'An existing wallet runtime or sidecar is present. Automatic recovery is refused. Reconcile the orphaned SQLite and ciphertext with the native anchor; do not delete unknown files.',
 'MANAGED_WALLET_EXISTING_RUNTIME_DENIED':'An existing wallet runtime or sidecar is present. Automatic recovery is refused. Reconcile the orphaned SQLite and ciphertext with the native anchor; do not delete unknown files.',
 'MANAGED_WALLET_EXISTS_OR_UNCERTAIN':'A managed wallet reference or vault already exists. Duplicate create is refused. Use authenticated restore; do not reset custody.',
 'MANAGED_WALLET_ORIGINAL_OWNER_REQUIRED':'Wallet access requires the original live CoreSupervisor process. Foreign PID adoption is refused.',
 'MANAGED_WALLET_ANCHOR_EXISTS':'A native checkpoint anchor already exists for this wallet identity. Duplicate create is refused.',
 'WALLET_OPERATION_DENIED_STATE_RETAINED':'Operation could not complete safely. Wallet state and reservations are retained. Verify the live chain and latest checkpoint; do not reset custody.',
}

def public_code(code,*,fallback='WALLET_OPERATION_DENIED_STATE_RETAINED'):
    safe=fallback if type(fallback) is str and fallback in _MESSAGES else 'WALLET_OPERATION_DENIED_STATE_RETAINED'
    return code if type(code) is str and code in _MESSAGES else safe

def error_text(code,*,fallback='WALLET_OPERATION_DENIED_STATE_RETAINED'):
    # No arbitrary reason, path, RPC error, address, passphrase or traceback.
    return _MESSAGES[public_code(code,fallback=fallback)]

def operation_error(action,error):
    from .wallet_session import WalletSessionError
    from .vault import VaultError
    # Do not call str(error): an external exception may contain private data
    # or implement a hostile formatter. Exact single-argument categories only.
    args=error.args if type(error) in (ValueError,WalletSessionError,VaultError) else ()
    code=args[0] if len(args)==1 and type(args[0]) is str else None
    if action=='prepare' and type(error) is ValueError:
        if code in ('INVALID_ADDRESS','INVALID_ENCODING','INVALID_PADDING','WRONG_NETWORK_OR_ADDRESS',
                    'INVALID_VERSION_OR_CHECKSUM','INVALID_ADDRESS_LENGTH','INVALID_PUBLIC_KEY'):
            return 'WALLET_INPUT_RECIPIENT_INVALID'
        if code=='PAYMENT_AMOUNT':return 'WALLET_INPUT_AMOUNT_INVALID'
        if code=='FEE_POLICY':return 'WALLET_INPUT_FEE_INVALID'
        if code=='INSUFFICIENT_SINGLE_CLUSTER_FUNDS':return 'WALLET_INPUT_FUNDS_UNAVAILABLE'
    if type(error) is WalletSessionError and code in _MESSAGES and code not in INPUT_ERRORS:
        return code
    if action in ('unlock','recover') and type(error) in (VaultError,WalletSessionError):
        return 'WALLET_UNLOCK_REFUSED' if action=='unlock' else 'WALLET_RECOVERY_REFUSED'
    return 'WALLET_SYNC_UNVERIFIED' if action=='sync' else 'WALLET_OPERATION_DENIED_STATE_RETAINED'
