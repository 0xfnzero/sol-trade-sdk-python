from types import SimpleNamespace

import pytest
from solders.hash import Hash
from solders.pubkey import Pubkey

from sol_trade_sdk.nonce_cache import fetch_nonce_info


class _FakeRpc:
    def __init__(self, data):
        self._data = data

    async def get_account_info(self, *args, **kwargs):
        if self._data is None:
            return SimpleNamespace(value=None)
        return SimpleNamespace(value=SimpleNamespace(data=self._data))


@pytest.mark.asyncio
async def test_fetch_nonce_info_parses_rust_layout():
    authority = Pubkey.from_bytes(bytes([7]) * 32)
    nonce_bytes = bytes([9]) + bytes(31)
    data = bytearray(80)
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
