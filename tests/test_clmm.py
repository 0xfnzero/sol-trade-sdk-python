"""Golden vectors from released Rust 5.0.6 and Raydium math 0.3.0."""

import json
from pathlib import Path
import pytest
from sol_trade_sdk.calc.clmm import (
    ClmmPool,
    ClmmTick,
    clmm_sqrt_price_at_tick,
    clmm_tick_at_sqrt_price,
    clmm_swap_step,
    clmm_swap_exact_in,
    MAX_SQRT_PRICE,
)

VECTORS = json.loads(
    (Path(__file__).parent / "fixtures/clmm_rust_5_0_6.json").read_text()
)


@pytest.mark.parametrize("vector", VECTORS, ids=lambda v: v["case"]["kind"])
def test_rust_golden(vector):
    c, expected = vector["case"], vector["expected"]

    def run():
        if c["kind"] == "tick":
            price = clmm_sqrt_price_at_tick(c["tick"])
            if price < MAX_SQRT_PRICE:
                assert clmm_tick_at_sqrt_price(price) == c["tick"]
            return dict(price=str(price))
        if c["kind"] == "step":
            r = clmm_swap_step(
                int(c["current"]),
                int(c["target"]),
                int(c["liquidity"]),
                int(c["amount"]),
                c["fee"],
                c["down"],
            )
            return dict(
                price=str(r.sqrt_price),
                input=str(r.amount_in),
                output=str(r.amount_out),
                fee=str(r.fee),
            )
        p = ClmmPool(
            int(c["current"]), int(c["liquidity"]), c["tick"], c["spacing"], c["fee"]
        )
        ticks = [
            ClmmTick(
                t["tick"],
                int(t["net"]),
                int(t["gross"]),
                int(t["orders"]),
                int(t["partial"]),
            )
            for t in c["ticks"]
        ]
        before = repr(ticks)
        r = clmm_swap_exact_in(
            p,
            ticks,
            int(c["amount"]),
            int(c["limit"]),
            c["fee_on"],
            bytes(c["dynamic"]),
            c["timestamp"],
            c["down"],
        )
        assert repr(ticks) == before
        return dict(consumed=str(r.consumed), output=str(r.amount_out))

    if "error" in expected:
        with pytest.raises(ValueError):
            run()
    else:
        assert run() == expected
