"""Native custody; Linux requires explicit Core trust and a root witness."""
import os
import sys
from . import encrypted_storage


def storage():
    if sys.platform == 'darwin':
        return encrypted_storage
    if sys.platform == 'win32':
        from . import windows_private_storage
        windows_private_storage.require_native()
        return windows_private_storage
    if sys.platform == 'linux':
        from .linux_runtime import policy
        policy()
        from . import linux_private_storage
        linux_private_storage.require_native()
        return linux_private_storage
    raise ValueError('VAULT_NATIVE_PLATFORM_REQUIRED')


def create_directory(directory):
    if sys.platform in ('win32','linux'):
        storage().create_private_directory(directory)
    elif sys.platform == 'darwin':
        directory.mkdir(mode=0o700)
        encrypted_storage.validate_directory(directory)
    else:
        raise ValueError('VAULT_NATIVE_PLATFORM_REQUIRED')


def envelope_profile():
    # Existing macOS v1 backups retain their exact format. Windows v2 backups
    # explicitly bind the custody platform, denying cross-platform restoration.
    if sys.platform == 'darwin':
        return {'version': 1}
    if sys.platform == 'win32':
        storage()
        return {'version': 2, 'custody_platform': 'windows-x64'}
    if sys.platform == 'linux':
        storage()
        return {'version':3,'custody_platform':'linux-x86_64','anchor_policy':'root-witness-v1'}
    raise ValueError('VAULT_NATIVE_PLATFORM_REQUIRED')


def platform_name():
    storage()
    return {'win32':'windows-x64','darwin':'macos-arm64','linux':'linux-x86_64'}[sys.platform]


def anchor(wallet_id,keychain=None):
    if sys.platform=='linux':
        if keychain is not None:raise ValueError('VAULT_FOREIGN_ANCHOR_DENIED')
        from .linux_runtime import policy
        from .linux_anchor_witness import LinuxRootWitnessAnchor
        return LinuxRootWitnessAnchor(wallet_id,policy().witness)
    if sys.platform=='win32':
        if keychain is not None:raise ValueError('VAULT_FOREIGN_ANCHOR_DENIED')
        from .windows_checkpoint_anchor import WindowsCredentialAnchor
        return WindowsCredentialAnchor(wallet_id)
    if sys.platform=='darwin':
        from .vault import KeychainAnchor
        return KeychainAnchor(wallet_id,keychain)
    raise ValueError('VAULT_NATIVE_PLATFORM_REQUIRED')


def anchor_label():
    if sys.platform=='linux':return 'Independent Linux root witness'
    return 'Windows Credential Manager' if sys.platform=='win32' else 'macOS Keychain'
