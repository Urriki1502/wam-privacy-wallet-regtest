"""Read-only adjudication of current native and final frozen A06 artifacts.

Trusted CI checkout/download context is required. Self-consistent public JSON
is not a signature, independent security review, wallet authority or V1 release.
"""
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import tarfile
import zipfile
from .a06_acceptance import require_components, core_pair
from .r04_package_audit import audit_candidate_output, _unique_pairs
from .r06_release_transition import _valid, PINS


def _require(value):
    if not value:raise ValueError('A06_ARTIFACT_ACCEPTANCE_DENIED')


def _json(path):
    info=path.lstat()
    _require(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and 0<info.st_size<=8*1024*1024)
    return json.loads(path.read_bytes(),object_pairs_hook=_unique_pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))


def _one(folder,name):
    values=list(folder.rglob(name));_require(len(values)==1)
    return values[0]


def _summary(data,platform,frozen):
    result=require_components(data['graceful_shutdown_component'],data['index_recovery_component'],
        data['bip39_index_recovery_component'],data['frozen_operator_recovery_component'],
        platform=platform,frozen=frozen)
    _require(data['a06_recovery_acceptance']==result)
    return result


def _identity(data,source,checkout):
    _require(data['source_head_sha']==source and data['checkout_sha']==checkout)


def _payloads(folder,manifest):
    """Hash actual embedded Core pair and executable; never extract/execute."""
    cores={};executables=set()
    wanted=manifest['core_sha256']
    apps={'WAM Privacy Wallet REGTEST','WAM-Privacy-Wallet-REGTEST.exe',
          'wam-regtest-desktop','wam-regtest-headless'}
    packages=0
    for name in manifest['files_sha256']:
        if not name.endswith(('.app.zip','.zip','.tar.gz')):continue
        packages+=1
        path=folder/name
        _require(path.stat().st_size<=512*1024*1024)
        found={}
        if name.endswith('.zip'):
            with zipfile.ZipFile(path) as archive:
                members=archive.infolist();_require(len(members)<=8192)
                _require(len({m.filename for m in members})==len(members))
                for m in members:
                    base=PurePosixPath(m.filename).name
                    if base not in wanted and base not in apps:continue
                    kind=stat.S_IFMT(m.external_attr>>16)
                    if kind==stat.S_IFLNK:
                        # PyInstaller's signed macOS layout has Resources aliases
                        # to the same regular Frameworks bytes. Validate the exact
                        # internal alias; never follow a general archive symlink.
                        app='WAM Privacy Wallet REGTEST.app/Contents/'
                        _require(manifest['platform']=='macos-arm64' and base in wanted
                            and m.filename==app+'Resources/core/'+base and m.file_size<=512)
                        _require(archive.read(m)==('../../Frameworks/core/'+base).encode())
                        target=archive.getinfo(app+'Frameworks/core/'+base)
                        _require(stat.S_ISREG(target.external_attr>>16))
                        continue  # The regular member below must still match its pin.
                    _require(not m.is_dir() and kind in (0,stat.S_IFREG) and m.file_size<=128*1024*1024)
                    h=hashlib.sha256(archive.read(m)).hexdigest()
                    if base in wanted:
                        _require(base not in found);found[base]=h
                    else:executables.add(h)
        else:
            with tarfile.open(path,'r:gz') as archive:
                members=archive.getmembers();_require(len(members)<=8192)
                _require(len({m.name for m in members})==len(members))
                for m in members:
                    base=PurePosixPath(m.name).name
                    if base not in wanted and base not in apps:continue
                    _require(m.isfile() and not m.issym() and not m.islnk() and m.size<=128*1024*1024)
                    h=hashlib.sha256(archive.extractfile(m).read()).hexdigest()
                    if base in wanted:
                        _require(base not in found);found[base]=h
                    else:executables.add(h)
        _require(found==wanted)
        cores.update(found)
    _require(packages==1 and cores==wanted and executables)
    return executables


def assess_artifacts(root,platform,source,checkout):
    """Every designated native/frozen frontend must prove A+B+C, no SKIP."""
    if platform=='macos-arm64':
        natives=[('native','real-core-evidence.json')]
        frozen=[('frozen','macos-arm64','macos-packaged-wallet-evidence.json',1)]
    elif platform=='windows-x64':
        natives=[('native','windows-operational-wallet-evidence.json')]
        frozen=[('frozen','windows-x64','windows-packaged-wallet-evidence.json',3)]
    elif platform=='linux-x86_64':
        natives=[('native-headless','linux-headless-evidence.json'),('native-qt','linux-qt-evidence.json')]
        frozen=[('frozen-headless','linux-x86_64-headless','linux-headless-evidence.json',1),
                ('frozen-desktop','linux-x86_64-desktop','linux-qt-evidence.json',1)]
    else:raise ValueError('A06_PLATFORM_UNSUPPORTED')
    rows=[]
    for label,name in natives:
        path=_one(root/label,name);data=_json(path)
        identity=data['a06_native_source_provenance'];_identity(identity,source,checkout)
        _require(identity['tracked_source_matches_head'] is True and identity['source_unchanged_across_build'] is True)
        summary=_summary(data,platform,False)
        rows.append({'role':label,'receipt_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'acceptance':summary})
    for label,profile,name,count in frozen:
        manifest_path=_one(root/label,'RELEASE_CANDIDATE_MANIFEST.json');folder=manifest_path.parent
        audit_candidate_output(folder,expected_platform=profile)
        manifest=_json(manifest_path);_require(_valid(manifest));_identity(manifest,source,checkout)
        _require(manifest['core_sha256']==PINS[profile])
        binaries=_payloads(folder,manifest)
        names=[n for n in manifest['files_sha256'] if PurePosixPath(n).name==name]
        _require(len(names)==count)
        if platform=='windows-x64':
            _require({PurePosixPath(n).parent.as_posix() for n in names}=={'.','ui-scale-1.25','ui-scale-1.5'})
        for member in names:
            path=folder/member;data=_json(path);summary=_summary(data,platform,True)
            _require(data['frozen_operator_recovery_component']['frozen_binary_sha256'] in binaries)
            rows.append({'role':label,'member':member,'receipt_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'manifest_sha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                'actual_payload_executable_sha256':sorted(binaries),'acceptance':summary})
    return {'schema':'wam-a06-platform-recovery-gate/v1','status':'PASS',
        'A06-A':'PASS','A06-B':'PASS','A06-C':'PASS','platform':platform,
        'source_head_sha':source,'checkout_sha':checkout,'evidence':rows,
        'full_q05_qualified':False,'full_v1_qualified':False,'physical_accepted':False,
        'automatic_release_authorized':False}
