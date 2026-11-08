"""Explicit reviewed wallet module inventories; build-time only, never shipped.

RUNTIME is the reviewed macOS ARM64 set. Windows x64 and Linux x86_64 reuse it
and add only what their normal production entry actually needs (Phase 5).
Other-platform runtime helpers that common modules dispatch to behind
sys.platform guards stay until they can be separated in a qualified change;
their diagnostic callers are excluded. Windows/Linux production bytes are NOT
qualified until native frozen execution on those hosts.
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


# Windows: Core staging helper and the existing Win32 Core config/env/RPC
# helpers that core_supervisor/core_process/rpc_scope call on win32.
WINDOWS_EXTRA = frozenset(('windows_core_regtest_smoke', 'windows_core_stage',
                           'windows_production_entry'))
# Linux: existing headless wallet frontend (linux-wallet) and its entry.
LINUX_EXTRA = frozenset(('linux_headless', 'linux_production_entry'))
# Modules importing PySide6 at module level: never in the no-Qt headless build.
QT_MODULES = frozenset(('bip39_backup_page bip39_fusion_gui bip39_locale bip39_owner_gui '
                        'desktop external_core_gui fusion_motion fusion_pages fusion_ui '
                        'managed_gui operational_gui').split())
ENTRY = {'macos': 'production_entry', 'windows': 'windows_production_entry',
         'linux-desktop': 'linux_production_entry', 'linux-headless': 'linux_production_entry'}


def runtime_modules(platform='macos'):
    if platform == 'macos':
        return RUNTIME
    base = RUNTIME - {'production_entry'}
    if platform == 'windows':
        return frozenset(base | WINDOWS_EXTRA)
    if platform == 'linux-desktop':
        return frozenset(base | LINUX_EXTRA)
    if platform == 'linux-headless':
        return frozenset((base | LINUX_EXTRA) - QT_MODULES)
    raise ValueError('PRODUCTION_PLATFORM_POLICY_DENIED')


# Developer/qualification/alternate argv that every production executable must
# refuse with 64 before reading resources (all platforms, hostile CI env set).
DEVELOPER_ARGV = tuple([a] for a in (
    '--ci-q06-bip39-spend', '--ci-q05-managed-wallet', '--ci-real-core-gui', '--ci-ui-layout',
    '--ci-v1-net-shared-regtest', '--ci-q04-external-miner', '--ci-real-core-wallet-cocoa',
    '--ci-q06-bip39-readonly', '--ci-q06-owned-spend', '--ci-real-core-wallet',
    'q04-external-miner', 'linux-wallet', 'smoke', 'wallet', '-m', '-c', '--core-dir',
    '--check-bundle=1', '--mainnet', '--testnet', '--regtest', '-h', '--help', '')) + (
    ['--check-bundle', '--check-bundle'], ['--ci-q05-managed-wallet', 'native'],
    ['--ci-q06-owned-spend', 'spend'], ['wallet', '--confirm-headless-e2e'],
    ['wallet', '--manifest-sha256', '0' * 64, '--anchor-socket', '/nonexistent/anchor.sock',
     '--confirm-experimental-developer-regtest', '--confirm-qt-e2e'],
    ['wallet', '--manifest-sha256', '0' * 64, '--anchor-socket', '/nonexistent/anchor.sock',
     '--confirm-experimental-developer-regtest', '--report', '/nonexistent/report.json'],
    ['wallet', '--manifest-sha256', '0' * 64, '--anchor-socket', '/nonexistent/anchor.sock',
     '--confirm-experimental-developer-regtest', '--core-dir', '/nonexistent'],
    ['wallet', '--manifest-sha256', '0' * 64, '--anchor-socket', 'relative.sock',
     '--confirm-experimental-developer-regtest'],
    ['wallet', '--manifest', '0' * 64, '--anchor-socket', '/nonexistent/anchor.sock',
     '--confirm-experimental-developer-regtest'])

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
    # macOS: Contents/Resources/wsp-source (Frameworks/ holds a symlink to it).
    # Windows/Linux onedir: _internal/wsp-source. Exactly one real directory.
    found = [p for p in app.rglob('wsp-source') if p.is_dir() and not p.is_symlink()]
    if len(found) > 1:
        raise ValueError('PRODUCTION_LOOSE_MODULE_DENIED')
    wsp = found[0] if found else app/'wsp-source'
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


def arguments(root, platform='macos'):
    runtime, entry = runtime_modules(platform), ENTRY[platform]
    available = {p.stem for p in (Path(root)/'src/wam_regtest').glob('*.py')}
    if not runtime <= available:
        raise ValueError('PRODUCTION_ALLOWLIST_MEMBER_MISSING')
    args = []
    for name in sorted(runtime - {'__init__', entry}):
        args += ['--hidden-import', 'wam_regtest.' + name]
    for name in sorted(available - runtime):
        args += ['--exclude-module', 'wam_regtest.' + name]
    return args


def audit(binary, app, platform='macos'):
    from PyInstaller.archive.readers import CArchiveReader
    archive = CArchiveReader(str(binary))
    pyz_names = [n for n in archive.toc if n.endswith('.pyz')]
    if len(pyz_names) != 1:
        raise ValueError('PRODUCTION_PYZ_SHAPE_DENIED')
    modules = set(archive.open_embedded_archive(pyz_names[0]).toc)
    present = {n.partition('.')[2] or '__init__' for n in modules
               if n == 'wam_regtest' or n.startswith('wam_regtest.')}
    # The entry is a top-level script in CArchive, not a PYZ submodule.
    entry = ENTRY[platform]
    expected = runtime_modules(platform) - {entry}
    if present != expected:
        raise ValueError('PRODUCTION_MODULE_INVENTORY_DENIED:' + ','.join(sorted(present ^ expected)))
    audit_loose_files(app)
    return dict(status='PASS_EXACT_PRODUCTION_ALLOWLIST', modules=sorted(present),
                platform=platform, entrypoint=entry, developer_dispatch=False,
                wam_sp_source_is_pinned_data_not_wallet_developer_tools=True)
