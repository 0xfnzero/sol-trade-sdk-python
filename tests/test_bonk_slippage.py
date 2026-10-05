"""Bonk slippage clamp parity with Rust 5.0.2."""

from src.calc.bonk import (
    MAX_SLIPPAGE_BASIS_POINTS,
    DEFAULT_VIRTUAL_BASE,
    DEFAULT_VIRTUAL_QUOTE,
    clamp_slippage_basis_points,
    get_buy_token_amount_from_sol_amount,
    get_sell_sol_amount_from_token_amount,
)


def test_clamp_slippage_basis_points():
    assert clamp_slippage_basis_points(0) == 0
    assert clamp_slippage_basis_points(100) == 100
    assert clamp_slippage_basis_points(10_000) == MAX_SLIPPAGE_BASIS_POINTS


def test_buy_slippage_at_10000_bps_does_not_zero_min_out():
    with_max = get_buy_token_amount_from_sol_amount(
        1_000_000, DEFAULT_VIRTUAL_BASE, DEFAULT_VIRTUAL_QUOTE, 0, 0, 10_000
    )
    with_cap = get_buy_token_amount_from_sol_amount(
        1_000_000,
        DEFAULT_VIRTUAL_BASE,
        DEFAULT_VIRTUAL_QUOTE,
        0,
        0,
        MAX_SLIPPAGE_BASIS_POINTS,
    )
    assert with_max == with_cap
    assert with_max > 0


def test_sell_slippage_above_10000_bps_does_not_underflow():
    with_overflow = get_sell_sol_amount_from_token_amount(
        1_000_000_000, DEFAULT_VIRTUAL_BASE, DEFAULT_VIRTUAL_QUOTE, 0, 0, 50_000
    )
    with_cap = get_sell_sol_amount_from_token_amount(
        1_000_000_000,
        DEFAULT_VIRTUAL_BASE,
        DEFAULT_VIRTUAL_QUOTE,
        0,
        0,
        MAX_SLIPPAGE_BASIS_POINTS,
    )
    assert with_overflow == with_cap
    assert with_overflow > 0
