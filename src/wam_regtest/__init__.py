"""Real WAM Core REGTEST-first wallet prototype. Never use on mainnet."""

__version__ = "0.1.0"

from .wsp_import import install_native_wsp_guard
install_native_wsp_guard()
