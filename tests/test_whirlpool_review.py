import json
from pathlib import Path
import pytest
from sol_trade_sdk.calc.whirlpool import (
    ClmmPool, ClmmTick, WhirlpoolAdaptiveFee, whirlpool_swap_exact_in,
    whirlpool_sqrt_price_at_tick,
)

VECTORS = json.loads((Path(__file__).parent / "fixtures/whirlpool_review_reference_20261005.json").read_text())


@pytest.mark.parametrize("order", ["shuffled", "ascending", "descending"])
@pytest.mark.parametrize("v", VECTORS, ids=lambda v: v["name"])
def test_full_state_matches_previous_native_algorithm(v, order):
    p = v["pool"]
    pool = ClmmPool(int(p["price"]), int(p["liquidity"]), p["tick"], p["spacing"], p["fee"])
    ticks = [ClmmTick(t["tick"], int(t["net"]), 10) for t in v["ticks"]]
    if order != "shuffled":
        ticks.sort(key=lambda t: t.tick, reverse=order == "descending")
    before = repr((pool, ticks))
    result = whirlpool_swap_exact_in(
        pool, ticks, v["starts"], int(v["amount"]), v["timestamp"], v["down"],
        WhirlpoolAdaptiveFee(**v["adaptive"]) if v["adaptive"] else None, int(v["limit"]),
    )
    assert {k: str(value) for k, value in result.__dict__.items()} == v["expected"]
    assert repr((pool, ticks)) == before


@pytest.mark.parametrize("start", [-443784, 443696, -2147483616, 2147483616])
def test_rejects_arrays_outside_protocol_range(start):
    pool = ClmmPool(whirlpool_sqrt_price_at_tick(0), 1000000, 0, 1, 3000)
    with pytest.raises(ValueError, match="array sequence"):
        whirlpool_swap_exact_in(pool, [], [start], 100, 105, True)


@pytest.mark.parametrize("limit", [False, 0.0, None])
def test_rejects_untyped_zero_price_limit(limit):
    pool = ClmmPool(whirlpool_sqrt_price_at_tick(0), 1000000, 0, 1, 3000)
    with pytest.raises(ValueError):
        whirlpool_swap_exact_in(pool, [], [-88, 0], 100, 105, True, limit=limit)


def test_duplicate_tick_rejected_after_sorting():
    pool = ClmmPool(whirlpool_sqrt_price_at_tick(0), 1000000, 0, 1, 3000)
    ticks = [ClmmTick(2, 0, 10), ClmmTick(0, 0, 10), ClmmTick(2, 0, 10)]
    with pytest.raises(ValueError, match="Duplicate"):
        whirlpool_swap_exact_in(pool, ticks, [-88, 0], 100, 105, True)


@pytest.mark.parametrize("tick,start,down", [(-443635, -443696, True), (443635, 443608, False)])
def test_accepts_partial_boundary_array(tick, start, down):
    pool = ClmmPool(whirlpool_sqrt_price_at_tick(tick), 0, tick, 1, 3000)
    assert whirlpool_swap_exact_in(pool, [], [start], 100, 105, down).consumed == 0
