"""Opted-in real-Core acceptance guards; never substitutes an RPC result."""
from contextlib import contextmanager, ExitStack
from unittest.mock import patch


@contextmanager
def forbid_core_cli_reads():
    # These guards raise on the old path. Every successful read still reaches
    # the owned, authenticated real Core through ManagedReadRpc.
    def denied(*args, **kwargs):
        raise AssertionError("WALLET_READ_CLI_OR_REHASH_FORBIDDEN")
    with ExitStack() as stack:
        for target in (
                "wam_regtest.wallet_session.verified_core_paths",
                "wam_regtest.wallet_session.WalletCoreCli._call",
                "wam_regtest.core.verified_core_paths",
                "wam_regtest.core._read_cli",
                "wam_regtest.core_process.verified_core_paths"):
            stack.enter_context(patch(target, denied))
        yield


def prove_session_reads(session):
    with forbid_core_cli_reads():
        snapshots=[session.snapshot() for _ in range(3)]
        assert snapshots[0]==snapshots[1]==snapshots[2]
    return {"transport":"owned-http", "repeated_reads":3,
            "cli_and_rehash_forbidden":True, "synthetic_rpc":False}
