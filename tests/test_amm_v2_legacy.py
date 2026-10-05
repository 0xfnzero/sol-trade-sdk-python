import pytest
from solders.pubkey import Pubkey
from src import RaydiumAmmV4Params
from src.instruction import RaydiumAmmV4InstructionBuilder
from src.instruction.raydium_amm_v4_builder import (
    build_buy_instructions as buy,
    build_sell_instructions as sell,
)
from src.instruction.common import (
    get_associated_token_address,
    TOKEN_PROGRAM,
    WSOL_TOKEN_ACCOUNT,
    USDC_TOKEN_ACCOUNT,
)

pk = lambda n: Pubkey(bytes([n]) * 32)


def params(**kw):
    return RaydiumAmmV4Params(
        amm=pk(1),
        coin_mint=pk(2),
        pc_mint=pk(3),
        token_coin=pk(4),
        token_pc=pk(5),
        coin_reserve=10000,
        pc_reserve=20000,
        swap_fee_numerator=1,
        swap_fee_denominator=3,
        **kw,
    )


@pytest.mark.parametrize("coin_in", [True, False])
@pytest.mark.asyncio
async def test_public_fee_direction_without_market(coin_in):
    p = params()
    im, om = (p.coin_mint, p.pc_mint) if coin_in else (p.pc_mint, p.coin_mint)
    b = await RaydiumAmmV4InstructionBuilder().build_buy_instructions(
        pk(99), im, om, 1001, 100, p, create_input_ata=False, create_output_ata=False
    )
    s = await RaydiumAmmV4InstructionBuilder().build_sell_instructions(
        pk(99), im, om, 1001, 100, p, create_output_ata=False
    )
    expected = (
        (20000 if coin_in else 10000) * 667 // ((10000 if coin_in else 20000) + 667) * 9900 // 10000
    )
    assert bytes(b[0].data) == bytes(s[0].data)
    assert b[0].data[0] == 16 and int.from_bytes(b[0].data[9:], "little") == expected
    assert len(b[0].accounts) == 8 and not b[0].accounts[7].is_writable
    assert b[0].accounts[5].pubkey == get_associated_token_address(pk(99), im, TOKEN_PROGRAM)
    with pytest.raises(ValueError, match="input_mint"):
        await RaydiumAmmV4InstructionBuilder().build_buy_instructions(
            pk(99), om, om, 1001, 100, p, create_input_ata=False
        )


def test_canonical_pair_and_exact_out():
    p = params()
    p.coin_mint = WSOL_TOKEN_ACCOUNT
    p.pc_mint = USDC_TOKEN_ACCOUNT
    ix = buy(
        pk(99),
        p.coin_mint,
        1001,
        p,
        create_input_ata=False,
        create_output_ata=False,
        fixed_output_amount=42,
    )[0]
    assert (
        ix.data[0] == 17
        and int.from_bytes(ix.data[1:9], "little") == 1001
        and int.from_bytes(ix.data[9:], "little") == 42
    )
    assert ix.accounts[5].pubkey == get_associated_token_address(
        pk(99), USDC_TOKEN_ACCOUNT, TOKEN_PROGRAM
    )


def test_invalid_amount_fee():
    p = params()
    with pytest.raises(ValueError):
        buy(pk(99), p.pc_mint, 0, p)
    p.swap_fee_denominator = 0
    with pytest.raises(ValueError):
        sell(pk(99), p.coin_mint, 1, p)
