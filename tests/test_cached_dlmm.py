import base64, json, copy
from pathlib import Path
import pytest
from solders.pubkey import Pubkey
from sol_trade_sdk import CachedAccount, CacheReadContext, PoolTradeHint, SubscriptionAccountCache

V = json.loads(
    (Path(__file__).parents[1] / "examples/fixtures/dlmm_mainnet_20261002.json").read_text()
)


def prepare(v, reverse=False, age=0, budget=8):
    c = SubscriptionAccountCache()
    for a in v["accounts"]:
        c.update(
            Pubkey.from_string(a["pubkey"]),
            CachedAccount(
                Pubkey.from_string(a["owner"]),
                base64.b64decode(a["data"]),
                int(a["slot"]),
                int(a["write_version"]),
            ),
        )
    im, om = (v["output_mint"], v["input_mint"]) if reverse else (v["input_mint"], v["output_mint"])
    return c.snapshot().prepare_dlmm(
        PoolTradeHint(*(Pubkey.from_string(k) for k in (v["pool"], im, om))),
        CacheReadContext(int(v["read_slot"]) + age, int(v["epoch"]), 0),
        int(v["unix_timestamp"]),
        Pubkey.from_string(v["payer"]),
        1000000 if reverse else 10000,
        100,
        budget,
    )


@pytest.mark.parametrize("reverse", [False, True])
def test_dlmm_cache_replay(reverse):
    a, q, ix = prepare(V, reverse)
    assert (
        str(q.estimated_net_amount_out)
        == V["expected"]["wsol_to_usdc" if reverse else "usdc_to_wsol"]
    )
    assert q.minimum_amount_out == q.estimated_net_amount_out * 99 // 100
    assert a.bin_arrays and ix.data[:8] == bytes([65, 75, 63, 76, 235, 91, 91, 136])


@pytest.mark.parametrize(
    "kind",
    [
        "stale",
        "owner",
        "missing",
        "pool_identity",
        "zero_price",
        "closed",
        "budget",
        "future_time",
        "mode",
        "power",
        "activation",
        "function",
    ],
)
def test_invalid(kind):
    v = copy.deepcopy(V)
    kept = []
    for a in v["accounts"]:
        d = bytearray(base64.b64decode(a["data"]))
        if a["pubkey"] == v["pool"]:
            if kind == "owner":
                a["owner"] = str(Pubkey.default())
            if kind == "closed":
                d.clear()
            if kind == "future_time":
                d[56:64] = (int(v["unix_timestamp"]) + 1).to_bytes(8, "little")
            if kind == "mode":
                d[36] = 2
            if kind == "power":
                d[34] = 19
            if kind == "activation":
                d[86] = 0
                d[816:824] = (int(v["read_slot"]) + 1).to_bytes(8, "little")
            if kind == "function":
                d[35] = 3
        if d[:8] == bytes([92, 142, 92, 220, 5, 148, 70, 181]):
            if kind == "missing":
                continue
            if kind == "pool_identity":
                d[24:56] = bytes(32)
            if kind == "zero_price":
                d[56:64] = (1).to_bytes(8, "little")
                d[72:88] = bytes(16)
        a["data"] = base64.b64encode(d).decode()
        kept.append(a)
    v["accounts"] = kept
    with pytest.raises(ValueError):
        prepare(v, age=1 if kind == "stale" else 0, budget=0 if kind == "budget" else 8)


@pytest.mark.parametrize(
    "v", json.loads((Path(__file__).parent / "fixtures/dlmm_bitmap_synthetic.json").read_text())
)
def test_extended_bitmap_certified_empty_interval(v):
    a, q, _ = prepare(v)
    assert q.estimated_net_amount_out == 10000
    assert a.bin_arrays == (Pubkey.from_string(v["expected_array"]),)
    assert a.bitmap_extension == Pubkey.from_string(v["expected_bitmap"])
    broken = copy.deepcopy(v)
    next(a for a in broken["accounts"] if a["pubkey"] == v["expected_bitmap"])["data"] = ""
    with pytest.raises(ValueError):
        prepare(broken)
