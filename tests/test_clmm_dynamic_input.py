import pytest
from sol_trade_sdk.calc.clmm import ClmmPool, clmm_swap_exact_in, clmm_sqrt_price_at_tick


@pytest.mark.parametrize("dynamic", [80, True, [0] * 80])
def test_rejects_implicit_dynamic_bytes(dynamic):
    pool = ClmmPool(clmm_sqrt_price_at_tick(0), 1000000, 0, 1, 3000)
    with pytest.raises(ValueError, match="dynamic fee bytes"):
        clmm_swap_exact_in(pool, [], 100, clmm_sqrt_price_at_tick(-60), 0, dynamic, 100, True)


def test_byte_buffers_keep_identical_quotes():
    pool = ClmmPool(clmm_sqrt_price_at_tick(0), 1000000, 0, 1, 3000)
    results = [clmm_swap_exact_in(pool, [], 100, clmm_sqrt_price_at_tick(-60), 0, data, 100, True)
               for data in (bytes(80), bytearray(80), memoryview(bytes(80)))]
    assert results[0] == results[1] == results[2]
