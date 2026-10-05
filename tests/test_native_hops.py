import json
from pathlib import Path
import pytest
from sol_trade_sdk.instruction.native_hops import *

CASES = json.loads((Path(__file__).parent / "fixtures/hops_rust_5_0_6.json").read_text())["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["name"])
def test_native_hop_matches_rust(case):
    pk = lambda n: Pubkey.from_bytes(bytes([n]) * 32)
    name = case["name"]
    args = SwapV2Args(1000, 500)
    if name.startswith("clmm"):
        pda = Pubkey.find_program_address(
            [b"pool_tick_array_bitmap_extension", bytes(pk(3))], CLMM
        )[0]
        ticks = (pk(13), pda, pk(14)) if "bitmap" in name else (pk(13), pk(14))
        a = RaydiumClmmSwapV2Accounts(*(pk(n) for n in range(1, 13)), ticks)
        ix = build_raydium_clmm_swap_v2(a, SwapV2Args(1000, 500, 4295048017))
    elif name.startswith("whirlpool"):
        _, supp, dir = name.split("_")
        ticks = tuple(pk(n) for n in range(11, 15 if supp == "true" else 14))
        a = WhirlpoolSwapV2Accounts(*(pk(n) for n in range(1, 11)), ticks)
        ix = build_whirlpool_swap_v2(a, args, dir == "true")
    else:
        a = MeteoraDlmmSwap2Accounts(
            *(pk(n) for n in range(1, 12)), (pk(13), pk(14)), pk(12) if "bitmap" in name else None
        )
        ix = build_meteora_dlmm_swap2(a, 1000, 500)
    assert str(ix.program_id) == case["program"]
    assert list(ix.data) == case["data"]
    assert [
        dict(pubkey=str(a.pubkey), is_signer=a.is_signer, is_writable=a.is_writable)
        for a in ix.accounts
    ] == case["accounts"]
