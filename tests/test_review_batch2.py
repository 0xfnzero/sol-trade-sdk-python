import json, base64, asyncio
from pathlib import Path
from dataclasses import replace
import pytest
from solders.pubkey import Pubkey
from sol_trade_sdk import SubscriptionAccountCache, CachedAccount, CacheReadContext, PoolTradeHint
from sol_trade_sdk.common.subscription_handle import (
    SubscriptionHandle,
    SubscriptionState,
    SubscriptionManager,
    SubscriptionConfig,
    SlotSubscription,
)
from sol_trade_sdk.instruction.native_hops import (
    RaydiumClmmSwapV2Accounts,
    SwapV2Args,
    build_raydium_clmm_swap_v2,
)


def fixture(name):
    v = json.loads((Path(__file__).parent / "fixtures" / f"batch2_{name}.json").read_text())
    c = SubscriptionAccountCache()
    for a in v["accounts"]:
        c.update(
            Pubkey.from_string(a["pubkey"]),
            CachedAccount(Pubkey.from_string(a["owner"]), base64.b64decode(a["data"]), 100, 1),
        )
    return (
        v,
        c,
        PoolTradeHint(*(Pubkey.from_string(v[k]) for k in ("pool", "input_mint", "output_mint"))),
        CacheReadContext(100, 0, 0),
    )


@pytest.mark.parametrize("kind", ["clmm", "dlmm"])
def test_sparse_arrays_farther_than_2048(kind):
    v, c, h, ctx = fixture("sparse_" + kind)
    with pytest.raises(ValueError, match=v["expected_missing"]):
        getattr(c.snapshot(), "prepare_" + kind)(
            h, ctx, 1000, Pubkey.from_string(v["payer"]), 100, 100, 8
        )


def test_cpmm_zero_protection_and_vault_authority():
    v, c, h, ctx = fixture("cpmm")
    payer = Pubkey.from_string(v["payer"])
    with pytest.raises(ValueError, match="zero protected"):
        c.snapshot().prepare_cpmm(h, ctx, 1000, payer, 1, 100)
    assert c.snapshot().prepare_cpmm(h, ctx, 1000, payer, 10000, 100)[1].minimum_amount_out > 0
    key = Pubkey.from_string(v["vault"])
    a = c.snapshot().get(key, ctx)
    d = bytearray(a.data)
    d[32:64] = bytes(32)
    c.update(key, replace(a, data=d, write_version=2))
    with pytest.raises(ValueError, match="vault"):
        c.snapshot().cpmm(h, ctx, 1000)


def test_native_hops_reject_bad_bitmap_and_non_boolean_mode():
    k = Pubkey.default()
    a = RaydiumClmmSwapV2Accounts(*([k] * 12), (k,), k)
    with pytest.raises(ValueError, match="bitmap"):
        build_raydium_clmm_swap_v2(a, SwapV2Args(1, 1))
    a = replace(a, tick_array_bitmap_extension=None)
    with pytest.raises(ValueError, match="boolean"):
        build_raydium_clmm_swap_v2(a, SwapV2Args(1, 1, 0, 2))


@pytest.mark.asyncio
async def test_queue_lifecycle_single_task_pause_self_stop_and_duplicate():
    h = SubscriptionHandle("x")
    await h.start()
    task = h._task
    await h.pause()
    await h.start()
    assert h._task is task
    done = asyncio.Event()

    async def callback(value):
        await h.stop()
        done.set()

    h.on_message(callback)
    await h.send(1)
    await asyncio.wait_for(done.wait(), 1)
    assert h.state == SubscriptionState.CLOSED and not await h.send(2)
    with pytest.raises(RuntimeError, match="closed"):
        await h.start()
    with pytest.raises(ValueError):
        SubscriptionHandle("bad", SubscriptionConfig(buffer_size=0))
    m = SubscriptionManager()
    await m.create_subscription(subscription_id="a")
    with pytest.raises(ValueError, match="Duplicate"):
        await m.create_subscription(subscription_id="a")
    await m.close_all()


@pytest.mark.asyncio
async def test_websocket_real_ack_notification_cancel_and_reconnect():
    from aiohttp import web

    requests = []
    connections = 0
    received = []
    done = asyncio.Event()

    async def endpoint(request):
        nonlocal connections
        connections += 1
        generation = connections
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        async for msg in ws:
            q = json.loads(msg.data)
            requests.append(q)
            if q["method"] == "slotSubscribe":
                await ws.send_json({"jsonrpc": "2.0", "id": q["id"], "result": 700 + generation})
                await ws.send_json(
                    {
                        "jsonrpc": "2.0",
                        "method": "slotNotification",
                        "params": {
                            "subscription": 700 + generation,
                            "result": {"slot": generation},
                        },
                    }
                )
                if generation == 1:
                    await ws.close()
            else:
                await ws.send_json({"jsonrpc": "2.0", "id": q["id"], "result": True})
        return ws

    app = web.Application()
    app.router.add_get("/", endpoint)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    h = SlotSubscription(f"http://127.0.0.1:{port}", SubscriptionConfig(reconnect_delay_ms=1))

    def callback(v):
        received.append(v["slot"])
        if len(received) == 2:
            done.set()

    h.on_message(callback)
    try:
        await h.connect()
        await asyncio.wait_for(done.wait(), 3)
        assert received == [1, 2]
        await h.stop()
        await h.stop()
        assert any(q["method"] == "slotUnsubscribe" and q["params"] == [702] for q in requests)
    finally:
        await h.stop()
        await runner.cleanup()
