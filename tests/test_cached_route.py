import json, base64, copy
from pathlib import Path
import pytest
from solders.pubkey import Pubkey
from sol_trade_sdk import (
    CachedAccount,
    CacheReadContext,
    PoolTradeHint,
    SubscriptionAccountCache,
)

F = Path(__file__).parents[1] / "examples/fixtures"


def prepare(v, age=0):
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
    hints = [
        PoolTradeHint(
            *(Pubkey.from_string(h[k]) for k in ("pool", "input_mint", "output_mint"))
        )
        for h in v["legs"]
    ]
    return cache.snapshot().prepare_route(
        hints,
        CacheReadContext(int(v["read_slot"]) + age, int(v["epoch"]), 0),
        int(v["unix_timestamp"]),
        Pubkey.from_string(v["payer"]),
        int(v["amount"]),
        v["slippage_bps"],
        v["maximum_arrays"],
    )


@pytest.mark.parametrize("direction", ["buy", "sell"])
def test_mainnet_route(direction):
    v = json.loads((F / f"route_{direction}_mainnet_20261002.json").read_text())
    r = prepare(v)
    assert str(r.minimum_net_amount_out) == v["expected"]["minimum_amount_out"]
    assert len(r.setup_instructions) == 3 and len(r.swap_instructions) == 2
    for l, w in zip(r.legs, v["expected"]["legs"]):
        assert [
            str(l.amount_in),
            str(l.estimated_net_amount_out),
            str(l.minimum_net_amount_out),
        ] == [w["amount_in"], w["amount_out"], w["minimum_amount_out"]]
    assert r.legs[1].amount_in <= r.legs[0].minimum_net_amount_out
    assert (
        str(r.estimated_intermediate_residuals[0][1])
        == v["expected"]["intermediate_residuals"][0]["amount"]
    )
    assert all(
        ix.accounts[0].pubkey == Pubkey.from_string(v["payer"])
        for ix in r.swap_instructions
    )


@pytest.mark.parametrize(
    "kind",
    ["disconnected", "reused", "cycle", "stale", "unsupported", "zero", "slippage"],
)
def test_bad_routes(kind):
    v = json.loads((F / "route_buy_mainnet_20261002.json").read_text())
    age = 0
    if kind == "disconnected":
        v["legs"][1]["input_mint"] = v["legs"][0]["input_mint"]
    elif kind == "reused":
        v["legs"][1]["pool"] = v["legs"][0]["pool"]
    elif kind == "cycle":
        v["legs"][1]["output_mint"] = v["legs"][0]["input_mint"]
    elif kind == "stale":
        age = 1
    elif kind == "unsupported":
        next(a for a in v["accounts"] if a["pubkey"] == v["legs"][0]["pool"])[
            "owner"
        ] = "11111111111111111111111111111111"
    elif kind == "zero":
        v["amount"] = "0"
    elif kind == "slippage":
        v["slippage_bps"] = 10000
    with pytest.raises(ValueError):
        prepare(v, age)
