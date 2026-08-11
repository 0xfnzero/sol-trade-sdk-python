from dataclasses import asdict

import pytest

from src import calc as typed_calc
from src.calc import pumpswap as dict_calc
from src.instruction.pumpswap_builder import (
    LEGACY_POOL_SIZE,
    POOL_DISCRIMINATOR,
    POOL_SIZE,
    decode_pool,
    decode_pool_account,
)

FEE_VALUES = (20, 5, 30)
BASE_RESERVE = 800_000_000_000_000
QUOTE_RESERVE = 100_000_000_000
VIRTUAL_QUOTE_RESERVES = 5_000_000_000
SLIPPAGE_BASIS_POINTS = 125


@pytest.mark.parametrize(
    "effective_quote_reserves",
    [typed_calc.effective_quote_reserves, dict_calc.effective_quote_reserves],
)
def test_effective_quote_reserves_supports_signed_i128(effective_quote_reserves):
    assert effective_quote_reserves(1_000, 250) == 1_250
    assert effective_quote_reserves(1_000, -250) == 750

    for raw, virtual in ((1_000, -1_000), (100, -101), ((1 << 64) - 1, 1)):
        with pytest.raises(ValueError, match="Invalid effective quote reserves"):
            effective_quote_reserves(raw, virtual)

    with pytest.raises(TypeError, match="signed i128"):
        effective_quote_reserves(1_000, True)
    with pytest.raises(ValueError, match="Invalid i128"):
        effective_quote_reserves(1_000, 1 << 127)


def test_dict_quotes_match_rust_integer_vectors():
    fees = dict_calc.PumpSwapFeeBasisPoints(*FEE_VALUES)

    assert dict_calc.buy_base_input_internal_with_fees(
        123_456_789_000,
        SLIPPAGE_BASIS_POINTS,
        BASE_RESERVE,
        QUOTE_RESERVE,
        VIRTUAL_QUOTE_RESERVES,
        fees,
    ) == {
        "internal_quote_amount": 16_206_205,
        "ui_quote": 16_295_341,
        "max_quote": 16_499_032,
    }
    assert dict_calc.buy_quote_input_internal_with_fees(
        1_500_000_000,
        SLIPPAGE_BASIS_POINTS,
        BASE_RESERVE,
        QUOTE_RESERVE,
        VIRTUAL_QUOTE_RESERVES,
        fees,
    ) == {
        "base": 11_206_836_149_304,
        "internal_quote_without_fees": 1_491_795_125,
        "max_quote": 1_518_750_000,
    }
    assert dict_calc.sell_base_input_internal_with_fees(
        123_456_789_000,
        SLIPPAGE_BASIS_POINTS,
        BASE_RESERVE,
        QUOTE_RESERVE,
        VIRTUAL_QUOTE_RESERVES,
        fees,
    ) == {
        "ui_quote": 16_112_095,
        "min_quote": 15_910_694,
        "internal_quote_amount_out": 16_201_203,
    }
    assert dict_calc.sell_quote_input_internal_with_fees(
        500_000_000,
        SLIPPAGE_BASIS_POINTS,
        BASE_RESERVE,
        QUOTE_RESERVE,
        VIRTUAL_QUOTE_RESERVES,
        fees,
    ) == {
        "internal_raw_quote": 502_765_209,
        "base": 3_849_022_110_532,
        "min_quote": 493_750_000,
    }


def test_typed_quotes_match_rust_integer_vectors():
    fees = typed_calc.PumpSwapFeeBasisPoints(*FEE_VALUES)

    assert asdict(typed_calc.buy_base_input_internal_with_fees(
        123_456_789_000,
        SLIPPAGE_BASIS_POINTS,
        BASE_RESERVE,
        QUOTE_RESERVE,
        VIRTUAL_QUOTE_RESERVES,
        fees,
    )) == {
        "internal_quote_amount": 16_206_205,
        "ui_quote": 16_295_341,
        "max_quote": 16_499_032,
    }
    assert asdict(typed_calc.buy_quote_input_internal_with_fees(
        1_500_000_000,
        SLIPPAGE_BASIS_POINTS,
        BASE_RESERVE,
        QUOTE_RESERVE,
        VIRTUAL_QUOTE_RESERVES,
        fees,
    )) == {
        "base": 11_206_836_149_304,
        "internal_quote_without_fees": 1_491_795_125,
        "max_quote": 1_518_750_000,
    }
    assert asdict(typed_calc.sell_base_input_internal_with_fees(
        123_456_789_000,
        SLIPPAGE_BASIS_POINTS,
        BASE_RESERVE,
        QUOTE_RESERVE,
        VIRTUAL_QUOTE_RESERVES,
        fees,
    )) == {
        "ui_quote": 16_112_095,
        "min_quote": 15_910_694,
        "internal_quote_amount_out": 16_201_203,
    }
    assert asdict(typed_calc.sell_quote_input_internal_with_fees(
        500_000_000,
        SLIPPAGE_BASIS_POINTS,
        BASE_RESERVE,
        QUOTE_RESERVE,
        VIRTUAL_QUOTE_RESERVES,
        fees,
    )) == {
        "internal_raw_quote": 502_765_209,
        "base": 3_849_022_110_532,
        "min_quote": 493_750_000,
    }


@pytest.mark.parametrize(
    "sell_base, fees",
    [
        (dict_calc.sell_base_input_internal_with_fees, dict_calc.PumpSwapFeeBasisPoints(0, 0, 0)),
        (typed_calc.sell_base_input_internal_with_fees, typed_calc.PumpSwapFeeBasisPoints(0, 0, 0)),
    ],
)
def test_sell_rejects_virtual_liquidity_not_backed_by_real_vault(sell_base, fees):
    with pytest.raises(ValueError, match="Insufficient real quote reserves"):
        sell_base(1_000_000, 0, 1, 1, 1_000_000, fees)


def _pool_payload(virtual_quote_reserves: int) -> bytes:
    data = bytearray([7])
    data.extend((42).to_bytes(2, "little"))
    for seed in range(1, 7):
        data.extend(bytes([seed]) * 32)
    data.extend((123_456).to_bytes(8, "little"))
    data.extend(bytes([7]) * 32)
    data.extend(bytes([1, 0]))
    data.extend(virtual_quote_reserves.to_bytes(16, "little", signed=True))
    assert len(data) == POOL_SIZE
    return bytes(data)


def test_pool_decoder_supports_current_signed_and_legacy_layouts():
    current = _pool_payload(-123_456)
    decoded = decode_pool(current)
    assert decoded is not None
    assert decoded.virtual_quote_reserves == -123_456
    assert decoded.is_mayhem_mode is True

    legacy = current[:POOL_SIZE - 16] + bytes(7)
    assert len(legacy) == LEGACY_POOL_SIZE
    decoded_legacy = decode_pool(legacy)
    assert decoded_legacy is not None
    assert decoded_legacy.virtual_quote_reserves == 0

    for size in range(LEGACY_POOL_SIZE + 1, POOL_SIZE):
        assert decode_pool(current[:size]) is None


def test_pool_account_decoder_validates_discriminator_and_padded_allocations():
    current = _pool_payload(-123_456)
    account = POOL_DISCRIMINATOR + current
    assert decode_pool_account(account).virtual_quote_reserves == -123_456
    assert decode_pool_account(account + bytes(300 - len(account))).virtual_quote_reserves == -123_456
    assert decode_pool_account(bytes(8) + current) is None
