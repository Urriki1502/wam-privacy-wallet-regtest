"""Explicit reviewed macOS wallet module inventory; build-time only, never shipped.

Platform-specific runtime helpers stay until their imports can be separated in
an independently qualified change. Their diagnostic callers are not included.
This policy is macOS-only; Windows/Linux build scripts remain unqualified.
"""
from pathlib import Path

RUNTIME = frozenset(('''
__init__ amounts bip39_12 bip39_backup_page bip39_fusion_gui bip39_locale
bip39_native_checkpoint bip39_owner_backend bip39_owner_gui bip39_reconciliation
bip39_recovery_proof bip39_scanner_checkpoint bip39_seed_vault bip39_spend_session
branding build_provenance cli_rpc core core_process core_supervisor custody desktop
disclosure encrypted_storage external_core external_core_gui external_recovery
fusion_motion fusion_pages fusion_status fusion_ui gui_errors history_pages json_rpc
linux_anchor_witness linux_developer_core linux_official_core linux_private_storage
linux_runtime managed_gui managed_onboarding managed_wallet_checkpoint managed_wallet_session
network_policy official_core_v013 operational_gui payjoin_safety private_directory
production_entry q05_platforms release rpc_contention rpc_credentials rpc_scope
shared_regtest shared_regtest_gui supervisor_client supervisor_identity supervisor_journal
supervisor_protocol supervisor_store telemetry vault wallet_executor wallet_read wallet_recovery
wallet_session windows_checkpoint_anchor windows_core_files windows_core_transport
windows_private_storage windows_read_gui windows_release_preflight windows_wallet_read
wsp_import wsp_live
''').split())


def arguments(root):
    available = {p.stem for p in (Path(root)/'src/wam_regtest').glob('*.py')}
    if not RUNTIME <= available:
        raise ValueError('PRODUCTION_ALLOWLIST_MEMBER_MISSING')
    args = []
    for name in sorted(RUNTIME - {'__init__', 'production_entry'}):
        args += ['--hidden-import', 'wam_regtest.' + name]
    for name in sorted(available - RUNTIME):
        args += ['--exclude-module', 'wam_regtest.' + name]
    return args


def audit(binary, app):
    from PyInstaller.archive.readers import CArchiveReader
    archive = CArchiveReader(str(binary))
    pyz_names = [n for n in archive.toc if n.endswith('.pyz')]
    if len(pyz_names) != 1:
        raise ValueError('PRODUCTION_PYZ_SHAPE_DENIED')
    modules = set(archive.open_embedded_archive(pyz_names[0]).toc)
    present = {n.partition('.')[2] or '__init__' for n in modules
               if n == 'wam_regtest' or n.startswith('wam_regtest.')}
    # The entry is a top-level script in CArchive, not a PYZ submodule.
    expected = RUNTIME - {'production_entry'}
    if present != expected:
        raise ValueError('PRODUCTION_MODULE_INVENTORY_DENIED:' + ','.join(sorted(present ^ expected)))
    for p in Path(app).rglob('*'):
        if p.is_file() and p.suffix in ('.py', '.pyc') and p.stem in (set(n for n in modules if n.startswith('wam_regtest.'))):
            raise ValueError('PRODUCTION_LOOSE_MODULE_DENIED')
        if p.is_file() and p.suffix in ('.py', '.pyc') and ('wam_regtest' in p.parts or p.stem in {'cli','package_entry','bip39_reconcile'}):
            raise ValueError('PRODUCTION_LOOSE_MODULE_DENIED')
    return dict(status='PASS_EXACT_PRODUCTION_ALLOWLIST', modules=sorted(present),
                entrypoint='production_entry', developer_dispatch=False,
                wam_sp_source_is_pinned_data_not_wallet_developer_tools=True)
