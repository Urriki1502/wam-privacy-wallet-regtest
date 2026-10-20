"""F-07 public-only Base58Check and WAM Core parser-address parity.

Offline parser is for classification only; it must NEVER authorize sends,
spend imported funds, rewrite a descriptor, derive a key or replace native
Core validateaddress. Mainnet Core RPC/network is intentionally absent.
"""
from dataclasses import dataclass
from hashlib import sha256
import hmac
import re

B58="123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
NETS={"main":(73,135,"wam"),"test":(65,128,"twam"),
      "regtest":(65,128,"wamrt")}
CORE_SOURCE_KEY_IO_V28_1="6cece47e410397e318d54643d0e459a44f756691"
WAM_CHAINPARAMS_V011="6e7eebfec5483f99ed13849a9b22cd502781364f"


class AddressParityRefusal(ValueError):
    pass


@dataclass(frozen=True)
class PublicLegacyAddress:
    network: str
    kind: str
    script_pub_key: str
    checksum_valid: bool
    core_bech32_prefix_collision: bool
    offline_decoding_is_core_acceptance: bool = False
    imported_key_deleted: bool = False
    signer_allowed: bool = False
    broadcast_allowed: bool = False


def inspect_legacy_public(address, *, network):
    """Return only checksum/network/script facts, never send eligibility."""
    try:
        if (type(network) is not str or network not in NETS
                or type(address) is not str or
                not 26<=len(address)<=64 or
                not all(ch in B58 for ch in address)):
            raise ValueError
        number=0
        for ch in address:
            number=number*58+B58.index(ch)
        raw=(b'\0'*(len(address)-len(address.lstrip('1')))
             +number.to_bytes((number.bit_length()+7)//8,'big'))
        if len(raw)!=25:
            raise ValueError
        payload,checksum=raw[:-4],raw[-4:]
        expected=sha256(sha256(payload).digest()).digest()[:4]
        if not hmac.compare_digest(checksum,expected):
            raise ValueError
        pub,script,hrp=NETS[network]
        if payload[0] not in (pub,script):
            raise ValueError
        data=payload[1:].hex()
        kind="P2PKH" if payload[0]==pub else "P2SH"
        script_pub_key=("76a914"+data+"88ac" if kind=="P2PKH"
                        else "a914"+data+"87")
        # Reproduces only the v28.1 key_io.cpp Bech32 BRANCH predicate,
        # not a native Core validateaddress result.
        collided=(address[:len(hrp)].lower()==hrp)
        return PublicLegacyAddress(network,kind,script_pub_key,True,collided)
    except (ValueError,TypeError,OverflowError):
        raise AddressParityRefusal("F07_PUBLIC_BASE58_NETWORK_DENIED") from None


@dataclass(frozen=True)
class CoreLegacyParity:
    network: str
    address_accepted_by_core: bool
    expected_script_matches_core: bool
    prefix_collision: bool
    spending_allowed: bool = False
    import_mutation_allowed: bool = False
    mainnet_runtime_qualified: bool = False


def verify_core_regtest_legacy(address, *, core_reply):
    """Require native signed/developer Core REGTEST validateaddress evidence.

    No injectable mainnet Core evidence is accepted by this function.
    """
    facts=inspect_legacy_public(address,network='regtest')
    try:
        if (type(core_reply) is not dict
                or core_reply.get('isvalid') is not True
                or type(core_reply.get('scriptPubKey')) is not str
                or core_reply['scriptPubKey']!=facts.script_pub_key
                or facts.core_bech32_prefix_collision):
            raise ValueError
        return CoreLegacyParity(
            'regtest',True,True,False)
    except (ValueError,TypeError):
        raise AddressParityRefusal("F07_CORE_REGTEST_ADDRESS_PARITY_DENIED") from None


def classify_collision_send_refusal(address):
    """The REGTEST WSP-only Send screen must never accept a mainnet legacy
    address, including the source-demonstrable Wam HRP/Base58 collision.
    No unrelated/invalid address is silently reinterpreted as valid.
    """
    try:
        facts=inspect_legacy_public(address,network='main')
    except AddressParityRefusal:
        return None
    if facts.core_bech32_prefix_collision:
        return "WALLET_F07_CORE_BASE58_HRP_COLLISION_SEND_DENIED"
    return "WALLET_F07_MAINNET_LEGACY_ON_REGTEST_DENIED"
