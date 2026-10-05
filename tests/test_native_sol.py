import base64, json
from pathlib import Path
import pytest
from solders.pubkey import Pubkey
from sol_trade_sdk import (
    CachedAccount,
    CacheReadContext,
    PoolTradeHint,
    SubscriptionAccountCache,
    settle_cached_route_with_native_sol,
)
from sol_trade_sdk.instruction.common import (
    get_associated_token_address,
    WSOL_TOKEN_ACCOUNT,
    TOKEN_PROGRAM,
)

F = Path(__file__).parents[1] / "examples/fixtures"


@pytest.mark.parametrize("kind", ["count", "swap", "protection", "credit", "zero"])
def test_rejects_modified_quote_and_instruction_bundle(kind):
    from dataclasses import replace
    v, payer, route = prepare("buy")
    if kind == "count": route = replace(route, swap_instructions=route.swap_instructions[:-1])
    if kind == "swap": route = replace(route, swap_instructions=tuple(reversed(route.swap_instructions)))
    if kind == "protection": route = replace(route, minimum_net_amount_out=route.minimum_net_amount_out+1)
    if kind == "credit":
        legs = list(route.legs)
        legs[1] = replace(legs[1], amount_in=legs[0].minimum_net_amount_out+1)
        route = replace(route, legs=tuple(legs))
    if kind == "zero":
        route = replace(route, legs=(replace(route.legs[0], amount_in=0),)+route.legs[1:])
    with pytest.raises(ValueError):
        settle_cached_route_with_native_sol(route, payer, v["temporary_wsol_seed"], int(v["rent_lamports"]), True, False)


def prepare(direction, venue="whirlpool"):
    v = json.loads(
        (
            F / f"{'dlmm_' if venue == 'dlmm' else ''}sol_route_{direction}_mainnet_20261002.json"
        ).read_text()
    )
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
        PoolTradeHint(*(Pubkey.from_string(h[k]) for k in ("pool", "input_mint", "output_mint")))
        for h in v["legs"]
    ]
    payer = Pubkey.from_string(v["payer"])
    r = cache.snapshot().prepare_route(
        hints,
        CacheReadContext(int(v["read_slot"]), int(v["epoch"]), 0),
        int(v["unix_timestamp"]),
        payer,
        int(v["amount"]),
        100,
        8,
    )
    return v, payer, r


@pytest.mark.parametrize("direction", ["buy", "sell"])
@pytest.mark.parametrize("venue", ["whirlpool", "dlmm"])
def test_native_endpoint(direction, venue):
    v, payer, r = prepare(direction, venue)
    old = get_associated_token_address(payer, WSOL_TOKEN_ACCOUNT, TOKEN_PROGRAM)
    before = repr(r)
    n = settle_cached_route_with_native_sol(
        r,
        payer,
        v["temporary_wsol_seed"],
        int(v["rent_lamports"]),
        v["native_input"],
        v["native_output"],
    )
    assert repr(r) == before
    assert n.required_lamports == int(v["rent_lamports"]) + (
        r.legs[0].amount_in if direction == "buy" else 0
    )
    assert n.temporary_wsol_account != old
    assert all(a.pubkey != old for ix in n.instructions for a in ix.accounts)
    assert (
        n.instructions[-1].data == bytes([9])
        and n.instructions[-1].accounts[0].pubkey == n.temporary_wsol_account
    )
    assert n.instructions[0].accounts[0].is_signer
    assert n.instructions[1].data == bytes([18]) + bytes(payer)
    assert n.instructions[2].data == bytes([17])
    assert str(r.minimum_net_amount_out) == v["expected"]["minimum_amount_out"]
    assert (
        len(r.legs) == 3
        and r.legs[1].amount_in <= r.legs[0].minimum_net_amount_out
        and r.legs[2].amount_in <= r.legs[1].minimum_net_amount_out
    )
    # Plain WSOL settlement retains ATA and never closes it.
    assert any(a.pubkey == old for ix in r.swap_instructions for a in ix.accounts)
    assert not any(
        ix.program_id == TOKEN_PROGRAM and ix.data == bytes([9]) for ix in r.swap_instructions
    )


@pytest.mark.parametrize(
    "kind",
    [
        "empty_seed",
        "long_utf8",
        "rent",
        "overflow",
        "wrong_wallet",
        "both",
        "neither",
        "wrong_asset",
    ],
)
def test_invalid_native_settlement(kind):
    v, payer, r = prepare("buy")
    seed = v["temporary_wsol_seed"]
    rent = int(v["rent_lamports"])
    input = True
    output = False
    if kind == "empty_seed":
        seed = ""
    if kind == "long_utf8":
        seed = "界" * 11
    if kind == "rent":
        rent = 0
    if kind == "overflow":
        rent = 2**64 - 1
    if kind == "wrong_wallet":
        payer = Pubkey.new_unique()
    if kind == "both":
        output = True
    if kind == "neither":
        input = False
    if kind == "wrong_asset":
        input = False
        output = True
    with pytest.raises(ValueError):
        settle_cached_route_with_native_sol(r, payer, seed, rent, input, output)
