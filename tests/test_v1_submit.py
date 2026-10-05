import base64, json
from pathlib import Path
import pytest
from src.swqos.clients import (
    _signature_from_serialized_transaction,
    BlockRazorClient,
    create_cached_wire_submit,
)
from src.common.types import TradeType

v = json.loads((Path(__file__).parent / "fixtures/v1_submit_native.json").read_text())
raw = base64.b64decode(v["transaction"])


@pytest.mark.asyncio
async def test_v1_raw_http_submission_without_rpc(monkeypatch):
    assert _signature_from_serialized_transaction(raw) == v["signature"]
    calls = []

    class Response:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def text(self):
            return ""

    class Session:
        def post(self, url, **kwargs):
            calls.append((url, kwargs))
            assert kwargs["json"]["transaction"] == v["transaction"]
            return Response()

    client = BlockRazorClient("https://never-rpc.invalid", "https://mock.invalid")

    async def get_session():
        return Session()

    monkeypatch.setattr(client, "get_session", get_session)
    assert await create_cached_wire_submit(client)(raw, "Buy") == v["signature"]
    assert len(calls) == 1


def test_v1_malformed_bounds():
    changes = [raw[:-1], raw + b"\0"]
    for index, value in [(1, 2), (41, 65), (4, 32), (40, 64), (42 + 64 + 20, 0)]:
        x = bytearray(raw)
        x[index] = value
        changes.append(bytes(x))
    for x in changes:
        with pytest.raises(Exception):
            _signature_from_serialized_transaction(x)


@pytest.mark.asyncio
@pytest.mark.parametrize("direction,expected", [("Buy", TradeType.BUY), ("Sell", TradeType.SELL)])
async def test_adapter_preserves_direction_and_disables_polling(direction, expected):
    calls = []

    class Client:
        async def send_transaction(self, kind, wire, wait):
            calls.append((kind, wire, wait))
            return v["signature"]

    submit = create_cached_wire_submit(Client())
    assert await submit(raw, direction) == v["signature"]
    assert calls == [(expected, raw, False)]
    with pytest.raises(Exception):
        await submit(raw, "Arbitrage")
    with pytest.raises(Exception):
        await submit(raw[:-1], direction)
    assert len(calls) == 1
