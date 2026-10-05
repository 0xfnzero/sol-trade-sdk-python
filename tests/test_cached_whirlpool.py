import base64, json, copy
from pathlib import Path
import pytest
from solders.pubkey import Pubkey
from sol_trade_sdk import (
    CachedAccount,
    CacheReadContext,
    PoolTradeHint,
    SubscriptionAccountCache,
    whirlpool_tick_at_sqrt_price,
)

F = Path(__file__).parents[1] / "examples/fixtures"
V = json.loads((F / "whirlpool_mainnet_20261002.json").read_text())


def prepare(v, reverse=False, age=0, budget=6):
    cache = SubscriptionAccountCache()
    for a in v["accounts"]:
        cache.update(
            Pubkey.from_string(a["pubkey"]),
            CachedAccount(
                Pubkey.from_string(a["owner"]),
                base64.b64decode(a["data"]),
                int(a["slot"]),
                int(a["write_version"]),
            ),
        )
    im, om = (v["output_mint"], v["input_mint"]) if reverse else (v["input_mint"], v["output_mint"])
    return cache.snapshot().prepare_whirlpool(
        PoolTradeHint(*(Pubkey.from_string(k) for k in (v["pool"], im, om))),
        CacheReadContext(int(v["read_slot"]) + age, int(v["epoch"]), 0),
        int(v["unix_timestamp"]),
        Pubkey.from_string(v["payer"]),
        int(v["amount"]),
        100,
        budget,
    )


def dynamic(d):
    b = bytearray(d[:12])
    b[:8] = bytes([17, 216, 246, 142, 225, 199, 218, 56])
    b.extend(d[9956:9988])
    b.extend(bytes(16))
    payload = bytearray()
    for i in range(88):
        o = 12 + i * 113
        tag = d[o]
        payload.append(tag)
        if tag:
            b[44 + i // 8] |= 1 << (i % 8)
            payload.extend(d[o + 1 : o + 113])
    return b + payload


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("layout", ["fixed", "dynamic"])
def test_replay(reverse, layout):
    v = copy.deepcopy(V)
    v["amount"] = "1000000" if reverse else "10000"
    if layout == "dynamic":
        for a in v["accounts"]:
            d = base64.b64decode(a["data"])
            if d[:8] == bytes([69, 97, 189, 190, 110, 7, 66, 187]):
                a["data"] = base64.b64encode(dynamic(d)).decode()
    a, q, _ = prepare(v, reverse)
    assert (
        str(q.estimated_net_amount_out)
        == v["expected"]["wsol_to_usdc" if reverse else "usdc_to_wsol"]
    )
    assert q.minimum_amount_out == q.estimated_net_amount_out * 99 // 100
    assert len(a.tick_arrays) == 3 and a.tick_arrays[0] == a.tick_arrays[1] == a.tick_arrays[2]


@pytest.mark.parametrize(
    "case",
    json.loads((F / "whirlpool_execution_replays_20261002.json").read_text()),
    ids=lambda c: c["name"],
)
def test_execution_preprice_replay(case):
    v = copy.deepcopy(V)
    a = next(a for a in v["accounts"] if a["pubkey"] == v["pool"])
    d = bytearray(base64.b64decode(a["data"]))
    p = int(case["pre_sqrt_price"])
    d[65:81] = p.to_bytes(16, "little")
    d[81:85] = whirlpool_tick_at_sqrt_price(p).to_bytes(4, "little", signed=True)
    a["data"] = base64.b64encode(d).decode()
    v["amount"] = case["amount_in"]
    _, q, _ = prepare(v, case["down"])
    assert str(q.estimated_net_amount_out) == case["actual_output"]


@pytest.mark.parametrize(
    "kind", ["stale", "owner", "missing", "pool_identity", "tag", "bitmap", "closed", "budget"]
)
def test_invalid(kind):
    v = copy.deepcopy(V)
    age = 0
    budget = 6
    kept = []
    if kind == "stale":
        age = 1
    if kind == "budget":
        budget = 0
    for a in v["accounts"]:
        d = bytearray(base64.b64decode(a["data"]))
        if a["pubkey"] == v["pool"]:
            if kind == "owner":
                a["owner"] = "11111111111111111111111111111111"
            if kind == "closed":
                d.clear()
        if d[:8] == bytes([69, 97, 189, 190, 110, 7, 66, 187]):
            if kind == "missing":
                continue
            if kind == "pool_identity":
                d[9956:9988] = bytes(32)
            if kind == "tag":
                d[12] = 2
            if kind == "bitmap":
                d = dynamic(d)
                d[44] ^= 1
        a["data"] = base64.b64encode(d).decode()
        kept.append(a)
    v["accounts"] = kept
    with pytest.raises(ValueError):
        prepare(v, age=age, budget=budget)
