"""Explicit process-wide Linux trust configuration shared by worker threads."""
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import secrets
import threading
from .linux_developer_core import verify,native,LinuxCoreError,_read_binary
from .linux_anchor_witness import LinuxRootWitnessAnchor


@dataclass(frozen=True)
class LinuxPolicy:
    core: Path
    manifest_sha256: str
    witness: Path
    cli_sha256: str


_policy=None
_guard=threading.RLock()


def configure(core,manifest_sha256,witness,*,authorized=False):
    native()
    global _policy
    with _guard:
        if _policy is not None:raise LinuxCoreError('LINUX_POLICY_ALREADY_BOUND')
        _,_,record=verify(core,manifest_sha256,authorized=authorized)
        # Before creating/funding any wallet, require the actual root peer.
        LinuxRootWitnessAnchor(secrets.token_hex(16),witness).read()
        _policy=LinuxPolicy(core,manifest_sha256,witness,record['files']['wam-cli']['sha256'])


def policy():
    native()
    with _guard:
        if _policy is None:raise LinuxCoreError('LINUX_EXPLICIT_CORE_AND_WITNESS_POLICY_REQUIRED')
        return _policy


def verified_paths(core):
    bound=policy()
    if core!=bound.core:raise LinuxCoreError('LINUX_FOREIGN_CORE_DIRECTORY_DENIED')
    node,cli,record=verify(core,bound.manifest_sha256,authorized=True)
    return node,cli,{'platform':'linux-x86_64','wamd_sha256':record['files']['wamd']['sha256'],
        'wam_cli_sha256':record['files']['wam-cli']['sha256'],
        'official_signed_release':False,'source_manifest_sha256':bound.manifest_sha256,
        'mainnet_allowed':False,'loader_process_binding_qualified':False}


def validate_cli(binary):
    bound=policy()
    if binary!=bound.core/'wam-cli' or sha256(_read_binary(binary)).hexdigest()!=bound.cli_sha256:
        raise LinuxCoreError('LINUX_APPROVED_CLI_HASH_DENIED')
