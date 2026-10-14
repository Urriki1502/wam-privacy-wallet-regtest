"""Select only the native platform custody implementation; Linux stays HOLD."""
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
    raise ValueError('VAULT_NATIVE_PLATFORM_REQUIRED')


def create_directory(directory):
    if sys.platform == 'win32':
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
    raise ValueError('VAULT_NATIVE_PLATFORM_REQUIRED')


def platform_name():
    storage()
    return 'windows-x64' if sys.platform=='win32' else 'macos-arm64'


def anchor(wallet_id,keychain=None):
    if sys.platform=='win32':
        if keychain is not None:raise ValueError('VAULT_FOREIGN_ANCHOR_DENIED')
        from .windows_checkpoint_anchor import WindowsCredentialAnchor
        return WindowsCredentialAnchor(wallet_id)
    if sys.platform=='darwin':
        from .vault import KeychainAnchor
        return KeychainAnchor(wallet_id,keychain)
    raise ValueError('VAULT_NATIVE_PLATFORM_REQUIRED')


def anchor_label():
    return 'Windows Credential Manager' if sys.platform=='win32' else 'macOS Keychain'
