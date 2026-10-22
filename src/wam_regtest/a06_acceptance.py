"""Recovery-aware A06 evidence policy; never runtime/wallet authorization.

Historical no-reindex SIGKILL observations are not graceful-stop or recovery
acceptance. Every A/B/C assertion below requires its own genuine test receipt.
"""
import hashlib
import json
from .r06_release_transition import PINS


def _require(condition):
    if not condition:
        raise ValueError('A06_RECOVERY_EVIDENCE_DENIED')


def core_pair(platform):
    key = 'linux-x86_64-headless' if platform == 'linux-x86_64' else platform
    pins = PINS[key]
    return tuple(pins[name] for name in (
        ('wamd.exe', 'wam-cli.exe') if platform == 'windows-x64' else ('wamd', 'wam-cli')))


def _core(receipt, platform):
    _require(receipt['platform'] == platform and receipt['core_version'] == 'v0.1.11')
    _require((receipt['wamd_sha256'], receipt['wam_cli_sha256']) == core_pair(platform))
    _require(receipt['synthetic_rpc'] is False and receipt['mainnet_allowed'] is False)


def _reindex(case, platform):
    height = case['original_height']
    _require(type(height) is int and height in (101, 104))
    _require(type(case['index_loss_observed_height']) is int
             and 0 <= case['index_loss_observed_height'] < height)
    r = case['explicit_reindex']
    _require(r['status'] == 'OWNED_REGTEST_EXPLICIT_REINDEX_VERIFIED_STOPPED')
    _require(type(r['height']) is int and (r['height'], r['tip']) == (height, case['original_tip']))
    _require(r['core_version'] == 'v0.1.11')
    _require((r['wamd_sha256'], r['wam_cli_sha256']) == core_pair(platform))
    _require(all(r[k] is True for k in ('operator_reindex_approved',
        'same_datadir_identity', 'protected_profile_config_unchanged')))
    _require(all(r[k] is False for k in ('automatic_broadcast', 'post_crash_mining', 'mainnet_allowed')))
    _require(case['status'] == 'PASS' and case['complete_block_file_bytes_unchanged'] is True)
    _require(case['automatic_broadcast'] is False and case['post_crash_mining'] is False)


def require_components(graceful, legacy, bip39, operator, *, platform, frozen):
    _require(type(frozen) is bool)
    for receipt in (graceful, legacy, bip39):
        _core(receipt, platform)
    _require(graceful['status'] == 'REAL_CORE_GRACEFUL_SHUTDOWN_CONTINUITY_PASS')
    expected = {'rpc-stop'} if platform == 'windows-x64' else {'rpc-stop', 'sigterm'}
    _require(len(graceful['cases']) == len(expected)
             and {c['method'] for c in graceful['cases']} == expected)
    _require(graceful['owned_processes_reaped'] is True and graceful['cleanup_verified'] is True)
    for c in graceful['cases']:
        _require(c['status'] == 'PASS' and c['height_before'] == c['height_after'] == 101)
        _require(type(c['clean_exit_code']) is int and c['clean_exit_code'] == 0)
        _require(all(c[k] is True for k in ('exact_tip_preserved', 'same_datadir_identity',
            'protected_profile_unchanged', 'core_wallet_address_and_balance_preserved')))
        _require(all(c[k] is False for k in ('reindex_performed', 'post_restart_mining',
            'replacement_wallet_created')))
    _require(legacy['status'] == 'REAL_CORE_EXPLICIT_INDEX_RECOVERY_WALLET_CONTINUITY_PASS'
             and legacy['cleanup_verified'] is True and len(legacy['cases']) == 2)
    _require({c['scenario'] for c in legacy['cases']} == {
        'fusion-native-checkpoint', 'original-101-core-wallet'})
    for c in legacy['cases']:
        _reindex(c, platform)
        _require(c['original_height'] == (104 if c['scenario'] == 'fusion-native-checkpoint' else 101))
        _require(c['exact_height_tip_after_second_restart'] is True
                 and c['original_wallet_state_preserved'] is True and c['replacement_wallet'] is False)
        if c['scenario'] == 'fusion-native-checkpoint':
            _require(all(c[k] is True for k in ('native_anchor_and_vault_unchanged_by_reindex',
                'signed_and_uncertain_reservations_preserved', 'confirmed_scanner_history_preserved')))
    _require(bip39['status'] == 'REAL_BIP39_MANAGED_INDEX_RECOVERY_PASS')
    _require(bip39['execution'] == ('FROZEN' if frozen else 'SOURCE_NATIVE'))
    _require([c['words'] for c in bip39['cases']] == [12, 24])
    for c in bip39['cases']:
        _reindex(c, platform)
        _require(c['original_height'] == 104 and c['passphrase_used'] is (c['words'] == 24))
        _require(all(c[k] is True for k in ('exact_original_64_byte_seed_and_identity',
            'real_authenticated_ipc_before_supervisor_restart', 'signed_and_uncertain_reservations_preserved',
            'native_anchor_vault_unchanged_by_reindex', 'confirmed_scanner_history_preserved', 'cleanup_verified')))
        interrupted = c['interrupted_recovery']
        _require(interrupted['status'] == 'PASS')
        _require(all(interrupted[k] is True for k in ('owned_reindex_child_killed_and_reaped',
            'normal_start_refused_without_child', 'unapproved_continuation_refused',
            'wrong_target_refused_without_journal_change', 'original_intent_preserved',
            'explicit_same_target_continuation', 'pending_journal_resolved_after_exact_verification',
            'original_chain_wallet_and_reservations_preserved')))
    if frozen:
        _require(operator['status'] == 'ACTUAL_FROZEN_OPERATOR_REINDEX_ENTRY_PASS')
        _require(operator['missing_approval_exit_code'] == 2 and operator['explicit_approval_exit_code'] == 0)
        _require(all(operator[k] is True for k in ('same_block_bytes_and_original_core_wallet',
            'own_child_processes_reaped', 'cleanup_verified')))
        _require(all(operator[k] is False for k in ('source_python_fallback', 'automatic_broadcast',
            'post_crash_mining', 'mainnet_allowed')))
    raw = json.dumps([graceful, legacy, bip39, operator], sort_keys=True, separators=(',', ':')).encode()
    return {'schema': 'wam-a06-recovery-acceptance/v1', 'status': 'A06_RECOVERY_A_B_C_PASS',
        'A06-A': 'PASS', 'A06-B': 'PASS', 'A06-C': 'PASS', 'platform': platform,
        'execution': 'FROZEN' if frozen else 'SOURCE_NATIVE',
        'component_receipts_sha256': hashlib.sha256(raw).hexdigest(),
        'historical_sigkill_without_reindex_is_release_requirement': False,
        'interruption_scope': 'verified owned reindex child terminated before completion observation',
        'physical_power_loss_qualified': False, 'full_q05_qualified': False,
        'full_v1_qualified': False, 'automatic_release_authorized': False}
