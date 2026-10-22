"""Q05 integrated GUI receipt gate; independent of preserved A06 policy."""
from .a06_artifact_gate import _one, _json, _identity, _payloads
from .a06_acceptance import core_pair

REQUIRED_CASES = {
    'normal-wrong-password', 'normal-decline', 'normal-read', 'normal-spend',
    'locked-gui-kill-reopen', 'core-kill-explicit-recovery-original-gui',
    'unlocked-gui-kill-authenticated-reopen', 'supervisor-lock-contention',
    'external-attach-has-no-lifecycle-authority', 'wrong-version-gui',
    'core-kill-while-spend-unlocked', 'concurrent-wallet-gui-denied',
    'unavailable-core-fresh-gui-locked', 'index-loss-gui-wallet-locked-before-reindex',
}


def check_component(proof, platform, frozen, binaries=()):
    """No inferred PASS from safe refusal, an A06 PASS or missing scenarios."""
    if (type(proof) is not dict
            or proof.get('schema') != 'wam-q05-managed-gui-lifecycle/v1'
            or proof.get('platform') != platform
            or proof.get('execution') != ('FROZEN' if frozen else 'SOURCE_NATIVE')
            or proof.get('core_version') != 'v0.1.11'
            or proof.get('synthetic_rpc') is not False
            or proof.get('mainnet_allowed') is not False
            or proof.get('automatic_rebroadcast') is not False
            or proof.get('owner_data_accessed') is not False
            or proof.get('full_v1_qualified') is not False
            or type(proof.get('cases')) is not dict
            or not REQUIRED_CASES <= set(proof['cases'])
            or any(type(row) is not dict for row in proof['cases'].values())):
        raise ValueError('Q05_GUI_EVIDENCE_REQUIRED')
    pair = core_pair(platform)
    if (proof.get('wamd_sha256') != pair[0] or proof.get('wam_cli_sha256') != pair[1]
            or frozen and proof.get('frozen_binary_sha256') not in binaries):
        raise ValueError('Q05_GUI_PROVENANCE_DENIED')
    failures = []
    for case in sorted(REQUIRED_CASES):
        expected = 'DENIED' if case in ('normal-wrong-password', 'normal-decline') else 'PASS'
        if proof['cases'][case].get('status') != expected:
            failures.append(case)
    verdict = 'FAIL' if failures else 'PASS'
    if proof.get('status') != verdict:
        raise ValueError('Q05_GUI_FALSE_VERDICT_DENIED')
    return {'status': verdict, 'nonpassing_cases': failures,
            'pending_cases': [case for case in sorted(REQUIRED_CASES) if proof['cases'][case].get('status') == 'PENDING'],
            'full_q05_qualified': False, 'full_v1_qualified': False}


def assess_gui_artifacts(root, platform, source, checkout):
    profiles = {
        'macos-arm64': ('native', 'real-core-evidence.json', 'frozen', 'macos-packaged-wallet-evidence.json'),
        'windows-x64': ('native', 'windows-operational-wallet-evidence.json', 'frozen', 'windows-packaged-wallet-evidence.json'),
        'linux-x86_64': ('native-qt', 'linux-qt-evidence.json', 'frozen-desktop', 'linux-qt-evidence.json'),
    }
    native, native_name, frozen, frozen_name = profiles[platform]
    record = _json(_one(root/native, native_name))
    _identity(record['a06_native_source_provenance'], source, checkout)
    rows = [{'role': native, **check_component(record.get('managed_gui_lifecycle_component'), platform, False)}]
    manifest_file = _one(root/frozen, 'RELEASE_CANDIDATE_MANIFEST.json')
    manifest = _json(manifest_file)
    _identity(manifest, source, checkout)
    binaries = _payloads(manifest_file.parent, manifest)
    names = [n for n in manifest['files_sha256'] if n.rsplit('/', 1)[-1] == frozen_name]
    if len(names) != (3 if platform == 'windows-x64' else 1):
        raise ValueError('Q05_GUI_FROZEN_REPORTS_REQUIRED')
    for member in names:
        record = _json(manifest_file.parent/member)
        rows.append({'role': frozen, 'member': member,
            **check_component(record.get('managed_gui_lifecycle_component'), platform, True, binaries)})
    return {'schema': 'wam-q05-platform-gui-gate/v1',
        'status': 'PASS' if all(r['status'] == 'PASS' for r in rows) else 'FAIL',
        'evidence': rows, 'source_head_sha': source, 'checkout_sha': checkout,
        'full_q05_qualified': False, 'full_v1_qualified': False}
