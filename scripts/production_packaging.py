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
production_entry q05_platforms regtest_funding release rpc_contention rpc_credentials rpc_scope
shared_regtest shared_regtest_gui supervisor_client supervisor_identity supervisor_journal
supervisor_protocol supervisor_store telemetry vault wallet_executor wallet_read wallet_recovery
wallet_session windows_checkpoint_anchor windows_core_files windows_core_transport
windows_private_storage windows_release_preflight
wsp_import wsp_live
''').split())


def runtime_modules(platform='macos'):
    if platform != 'macos':
        raise ValueError('PRODUCTION_PLATFORM_POLICY_DENIED')
    return RUNTIME


PYTHON_SUFFIXES = ('.py', '.pyc', '.pyo', '.pyw', '.pyd')


def audit_loose_files(app):
    """No loose Python may bypass the audited PYZ.

    The only permitted loose sources are the pinned public WSP data corpus,
    exactly as listed (path and SHA-256) in its bundled SOURCE_SHA256.json.
    Any other Python source/bytecode file anywhere in the app is denied.
    """
    import hashlib
    import json
    app = Path(app)
    wsp = app/'Contents/Resources/wsp-source'
    allowed = {}
    if wsp.exists():
        if wsp.is_symlink() or not wsp.is_dir():
            raise ValueError('PRODUCTION_LOOSE_MODULE_DENIED')
        receipt = json.loads((wsp/'SOURCE_SHA256.json').read_text())
        if (receipt.get('source_commit') != 'ac55f13423620252bdbf848c7e8a280c3b84721e'
                or type(receipt.get('files')) is not dict):
            raise ValueError('PRODUCTION_LOOSE_MODULE_DENIED')
        for relative, digest in receipt['files'].items():
            if (type(relative) is not str or not relative.startswith('src/wam_sp/')
                    or not relative.endswith('.py') or '..' in Path(relative).parts):
                raise ValueError('PRODUCTION_LOOSE_MODULE_DENIED')
            allowed[(wsp/relative).resolve()] = digest
    for p in app.rglob('*'):
        if p.suffix.lower() not in PYTHON_SUFFIXES or p.is_dir():
            continue
        if p.is_symlink():
            raise ValueError('PRODUCTION_LOOSE_MODULE_DENIED')
        digest = allowed.get(p.resolve())
        if digest is None or hashlib.sha256(p.read_bytes()).hexdigest() != digest:
            raise ValueError('PRODUCTION_LOOSE_MODULE_DENIED')


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
    audit_loose_files(app)
    return dict(status='PASS_EXACT_PRODUCTION_ALLOWLIST', modules=sorted(present),
                entrypoint='production_entry', developer_dispatch=False,
                wam_sp_source_is_pinned_data_not_wallet_developer_tools=True)
