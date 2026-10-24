"""Exercise missing native WSP/crypto in real isolated interpreters, no Core."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    root = Path(__file__).resolve().parents[1]
    program = '''
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1])/'src'))
if sys.argv[2]=='missing-crypto':
    sys.path.insert(0, str(Path(sys.argv[1])/'wsp-upstream/src'))
import wam_regtest
try:
    import wam_sp
except ModuleNotFoundError as error:
    if sys.argv[2]!='missing-crypto' or error.name not in ('coincurve','Crypto','cryptography','cffi','_cffi_backend'):
        raise
    print('Q01_MISSING_CRYPTO_REFUSED')
except ImportError as error:
    if sys.argv[2]!='missing-wsp' or str(error)!='WSP_NATIVE_SOURCE_IMPORT_REQUIRED':
        raise
    print('Q01_MISSING_WSP_REFUSED')
else:
    raise AssertionError('Q01_MISSING_DEPENDENCY_UNEXPECTEDLY_AVAILABLE')
'''
    cases = []
    with tempfile.TemporaryDirectory(prefix='wam-q01-empty-site-') as temporary:
        for case, expected in (('missing-wsp', 'Q01_MISSING_WSP_REFUSED'),
                               ('missing-crypto', 'Q01_MISSING_CRYPTO_REFUSED')):
            # -S excludes ALL site-packages and editable hooks; source is the
            # explicit authenticated checkout, never a different installed copy.
            result = subprocess.run([sys.executable, '-I', '-S', '-B', '-c',
                program, str(root), case], cwd=temporary, capture_output=True,
                text=True, timeout=60)
            if result.returncode or result.stdout.strip() != expected:
                raise AssertionError('Q01_MISSING_DEPENDENCY_REFUSAL_UNPROVEN')
            cases.append({'case': case, 'status': 'PASS', 'public_result': expected})
    receipt = {'schema': 'wam-q01-missing-dependency/v1', 'layer': 'SOURCE',
        'source_checkout_sha': subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip(),
        'timestamp_utc': datetime.now(timezone.utc).isoformat(), 'platform': sys.platform,
        'cases': cases, 'core_process_started': False, 'wallet_opened': False,
        'source_site_packages_available': False, 'core_e2e_qualified': False}
    with (root / 'q01-dependency-negatives.json').open('x') as output:
        json.dump(receipt, output, sort_keys=True, indent=2)
        output.write('\n')
    print('Q01_MISSING_DEPENDENCY_NATIVE_REFUSALS_PASS')


if __name__ == '__main__':
    main()
