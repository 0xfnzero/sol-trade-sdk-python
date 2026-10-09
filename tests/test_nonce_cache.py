from types import SimpleNamespace

import pytest
from solders.hash import Hash
from solders.pubkey import Pubkey

from sol_trade_sdk.nonce_cache import fetch_nonce_info


class _FakeRpc:
    def __init__(self, data, owner=Pubkey.default(), executable=False):
        self._data = data
        self._owner = owner
        self._executable = executable

    async def get_account_info(self, *args, **kwargs):
        if self._data is None:
            return SimpleNamespace(value=None)
        return SimpleNamespace(value=SimpleNamespace(data=self._data, owner=self._owner, executable=self._executable))


@pytest.mark.asyncio
async def test_fetch_nonce_info_parses_rust_layout():
    authority = Pubkey.from_bytes(bytes([7]) * 32)
    nonce_bytes = bytes([9]) + bytes(31)
    data = bytearray(80)
    data[:4] = (1).to_bytes(4, "little")
    data[4:8] = (1).to_bytes(4, "little")
    data[8:40] = bytes(authority)
    data[40:72] = nonce_bytes

    nonce_account = Pubkey.from_bytes(bytes([3]) * 32)
    got = await fetch_nonce_info(_FakeRpc(bytes(data)), nonce_account)

    assert got is not None
    assert got.nonce_account == nonce_account
    assert got.authority == authority
    assert got.nonce_hash == str(Hash.from_bytes(nonce_bytes))
    assert got.recent_blockhash == got.nonce_hash
    assert got.current_nonce == Hash.from_bytes(nonce_bytes)


@pytest.mark.asyncio
async def test_fetch_nonce_info_returns_none_for_missing_or_short_account():
    nonce_account = Pubkey.default()

    assert await fetch_nonce_info(_FakeRpc(None), nonce_account) is None
    assert await fetch_nonce_info(_FakeRpc(bytes(10)), nonce_account) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["foreign-owner", "executable", "uninitialized", "unknown-state",
                                     "legacy-version", "unknown-version", "truncated", "oversized"])
async def test_fetch_nonce_info_rejects_invalid_account_metadata_and_state(case):
    data = bytearray(80)
    data[:4] = (1).to_bytes(4, "little")
    data[4:8] = (1).to_bytes(4, "little")
    owner, executable = Pubkey.default(), False
    if case == "foreign-owner": owner = Pubkey.from_bytes(bytes([2]) * 32)
    if case == "executable": executable = True
    if case in ("uninitialized", "unknown-state"): data[4:8] = (0 if case == "uninitialized" else 2).to_bytes(4, "little")
    if case in ("legacy-version", "unknown-version"): data[:4] = (0 if case == "legacy-version" else 2).to_bytes(4, "little")
    if case == "truncated": data = data[:72]
    if case == "oversized": data += bytes(1)
    assert await fetch_nonce_info(_FakeRpc(bytes(data), owner, executable), Pubkey.default()) is None
