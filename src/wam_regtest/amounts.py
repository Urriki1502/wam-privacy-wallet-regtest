"""Exact shared decimal parsing; no GUI, floating point or price conversion."""
from decimal import Decimal
import re


def _parse_atoms(value,minimum,maximum):
    if type(value) is not str or not re.fullmatch(r'(?:0|[1-9][0-9]{0,7})(?:\.[0-9]{1,8})?',value):
        raise ValueError('WALLET_AMOUNT_DENIED')
    amount=Decimal(value)*100_000_000
    if not minimum<=amount<=maximum:raise ValueError('WALLET_AMOUNT_DENIED')
    return int(amount)


def parse_amount(value):return _parse_atoms(value,330,22_000_000*100_000_000)
