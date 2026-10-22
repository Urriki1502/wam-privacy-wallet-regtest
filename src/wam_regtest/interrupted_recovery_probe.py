"""Actual owned recovery-child termination, not mocked Core/RPC acceptance.

Fault window: durable intent published, verified reindex Popen launched, before
the application observes completion. No claim about an exact LevelDB write,
intermediate height, physical power loss or arbitrary OS-kernel failure.
"""
from unittest.mock import patch


def interrupt_before_verification(root, core, height, tip):
    from . import owned_recovery
    from .core_supervisor import CoreSupervisor, ManagedCoreError
    from .supervisor_store import read_exact
    assert not list(root.glob('supervisor.recovery.*.intent'))
    killed = []

    def terminate_verified_child(owner, *_):
        child = owner.process
        assert child.poll() is None and child.args[-1] == '-reindex=1'
        owner.binding._assert_image()
        child.kill()  # POSIX SIGKILL / native Windows TerminateProcess.
        assert child.wait(timeout=15) != 0
        killed.append(True)
        raise owned_recovery.IndexRecoveryError('RECOVERY_OWNED_CORE_EXITED')

    with patch.object(owned_recovery, '_wait_reindexed', terminate_verified_child):
        try:
            owned_recovery.recover_index(root, core, expected_height=height,
                expected_tip=tip, authorized_reindex=True)
        except owned_recovery.IndexRecoveryError as error:
            assert error.args == ('RECOVERY_OWNED_CORE_EXITED',)
        else:
            raise AssertionError('A06C_INTERRUPTED_RECOVERY_ACCEPTED')
    assert killed == [True]
    intents = list(root.glob('supervisor.recovery.*.intent'))
    assert len(intents) == 1 and not list(root.glob('supervisor.recovery.*.complete'))
    intent = intents[0]
    original = read_exact(root, intent.name)
    owner = CoreSupervisor(root, core, authorized=True, existing_only=True)
    try:
        try:
            owner.start()
        except ManagedCoreError as error:
            assert error.args == ('MANAGED_INDEX_RECOVERY_PENDING',)
        else:
            raise AssertionError('A06C_PENDING_NORMAL_START_ACCEPTED')
        assert owner.process is None
    finally:
        owner.close_listener()
        owner.stack.close()
    for approved, target, code in (
            (False, tip, 'RECOVERY_EXPLICIT_EXISTING_REGTEST_REINDEX_APPROVAL_REQUIRED'),
            (True, '0'*64, 'RECOVERY_PENDING_TARGET_MISMATCH')):
        try:
            owned_recovery.recover_index(root, core, expected_height=height,
                expected_tip=target, authorized_reindex=approved)
        except owned_recovery.IndexRecoveryError as error:
            assert error.args == (code,)
        else:
            raise AssertionError('A06C_UNAPPROVED_OR_WRONG_TARGET_ACCEPTED')
        assert read_exact(root, intent.name) == original
        assert len(list(root.glob('supervisor.recovery.*.intent'))) == 1
        assert not list(root.glob('supervisor.recovery.*.complete'))
    return {'owned_reindex_child_killed_and_reaped': True,
        'fault_window': 'durable intent and verified Popen before completion observation',
        'normal_start_refused_without_child': True,
        'unapproved_continuation_refused': True,
        'wrong_target_refused_without_journal_change': True,
        'original_intent_preserved': True,
        'physical_power_loss_qualified': False,
        'exact_leveldb_write_phase_qualified': False}
