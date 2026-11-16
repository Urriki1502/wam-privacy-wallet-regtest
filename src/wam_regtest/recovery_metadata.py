"""Draft public recovery hints; pure validation, no custody or signing authority.

Not integrated with profile IO, backups, scanner checkpoints or wallet unlock.
No mining account is qualified, therefore descriptors MUST be null. The only
supported identity is the existing REGTEST account-zero derivation. WAM-SP's
namespace is proposed, not a registered production convention.
"""
from .wsp_live import REGTEST_GENESIS

VERSION = 'fusion-public-recovery-metadata/regtest-draft-v1'
PATHS = {'scan': "m/352'/1'/0'/1'/0", 'spend': "m/352'/1'/0'/0'/0"}
FIELDS = frozenset(('version','chain','birthday','mining_descriptors','paths',
                    'hrp','label_high_water_mark'))


def validate_public_metadata(value):
    """Return a fresh public seven-field mapping; never infer state continuity.

    Birthday/label hints remain untrusted until reconciled to the authenticated
    original chain and native journal. This validator cannot authorize scanning,
    signing, broadcast, migration, reservation release or native anchor creation.
    """
    if (type(value) is not dict or set(value) != FIELDS
            or type(value['version']) is not str or value['version'] != VERSION
            or type(value['chain']) is not dict
            or value['chain'] != {'network':'regtest','genesis':REGTEST_GENESIS}
            or type(value['paths']) is not dict or value['paths'] != PATHS
            or value['mining_descriptors'] is not None
            or type(value['hrp']) is not str or value['hrp'] != 'wamrtsp'
            or type(value['birthday']) is not int or not 1 <= value['birthday'] < 2**31
            or type(value['label_high_water_mark']) is not int
            or not 0 <= value['label_high_water_mark'] < 2**32):
        raise ValueError('RECOVERY_PUBLIC_METADATA_DENIED')
    return {'version':VERSION, 'chain':dict(value['chain']),
            'birthday':value['birthday'], 'mining_descriptors':None,
            'paths':dict(PATHS), 'hrp':'wamrtsp',
            'label_high_water_mark':value['label_high_water_mark']}
