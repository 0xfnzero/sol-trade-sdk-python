import json
from pathlib import Path
import pytest
from solders.pubkey import Pubkey
from sol_trade_sdk.instruction.stonkfun import *

CASES = json.loads((Path(__file__).parent / "fixtures/launchlab_rust_5_0_6.json").read_text())[
    "cases"
]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["name"])
def test_current_launchlab_rust_golden(case):
    p = dict(case["state"])
    for field in ["base_transfer_fee", "quote_transfer_fee"]:
        fee = p[field]
        p[field] = TokenTransferFee(fee["basis_points"], int(fee["maximum_fee"]))
    for k in p:
        if isinstance(p[k], str):
            p[k] = int(p[k])
    state = LaunchLabQuoteState(**p)
    for buy in (True, False):
        expected = case["buy" if buy else "sell"]
        assert quote_launchlab_exact_in(
            state, int(case["amount"]), buy, case["slippage_bps"]
        ) == LaunchLabQuote(int(expected["amount_in"]), int(expected["minimum_amount_out"]))


def test_stock_quote_token2022_instruction():
    pk = lambda n: Pubkey.from_bytes(bytes([n]) * 32)
    token = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
    token2022 = Pubkey.from_string("TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb")
    p = StonkFunCurveAccounts(
        pk(1),
        pk(2),
        pk(3),
        pk(4),
        pk(5),
        pk(6),
        Pubkey.from_string(next(iter(CONFIGS))),
        token,
        token2022,
        pk(7),
        pk(8),
    )
    for buy in (True, False):
        ix = build_stonkfun_curve_exact_in(p, pk(9), 100, 5, buy)
        assert len(ix.accounts) == 18
        assert ix.accounts[10].pubkey == pk(3)
        assert ix.accounts[12].pubkey == token2022
        assert ix.accounts[6].pubkey == get_associated_token_address(pk(9), pk(3), token2022)
        assert struct.unpack_from("<QQ", ix.data, 8) == (100, 5)
    with pytest.raises(ValueError):
        build_stonkfun_curve_exact_in(p, pk(9), 0, 5, True)


@pytest.mark.parametrize("direction", [0, 1, "false", None])
def test_rejects_untyped_directions(direction):
    p = LaunchLabQuoteState(1000000, 2000000, 0, 0, 0, 0, 2500, 0, 0)
    with pytest.raises(ValueError, match="direction"):
        quote_launchlab_exact_in(p, 100, direction)
    with pytest.raises(ValueError, match="direction"):
        build_launchlab_curve_exact_in(None, Pubkey.new_unique(), 100, 1, direction)
    with pytest.raises(ValueError, match="direction"):
        TokenTransferFee(100, 100).calculate(100, direction)


@pytest.mark.parametrize("field,value", [("curve_type", False), ("curve_type", 0.0), ("slippage", True), ("slippage", False)])
def test_rejects_boolean_or_float_integer_metadata(field, value):
    from dataclasses import replace
    p = LaunchLabQuoteState(1000000, 2000000, 0, 0, 0, 0, 2500, 0, 0)
    with pytest.raises(ValueError):
        quote_launchlab_exact_in(replace(p, curve_type=value) if field == "curve_type" else p, 100, True, value if field == "slippage" else 0)
