"""Meteora DAMM v2 optional accounts parity with Rust 5.0.6."""

from solders.keypair import Keypair
from solders.pubkey import Pubkey

from src.instruction.common import TOKEN_PROGRAM, WSOL_TOKEN_ACCOUNT
from src.instruction.meteora_damm_v2_builder import (
    SWAP_MODE_EXACT_OUT,
    SWAP_MODE_PARTIAL_FILL,
    SYSVAR_INSTRUCTIONS,
    MeteoraDammV2Params,
    build_buy_instructions,
)


def test_meteora_account_layout_options():
    payer = Keypair().pubkey()
    mint = Keypair().pubkey()
    pool = Keypair().pubkey()
    referral = Keypair().pubkey()

    params = MeteoraDammV2Params(
        pool=pool,
        token_a_mint=WSOL_TOKEN_ACCOUNT,
        token_b_mint=mint,
        token_a_vault=Keypair().pubkey(),
        token_b_vault=Keypair().pubkey(),
        token_a_program=TOKEN_PROGRAM,
        token_b_program=TOKEN_PROGRAM,
    )

    ixs = build_buy_instructions(
        payer=payer,
        output_mint=mint,
        input_amount=1_000_000,
        params=params,
        create_input_ata=False,
        create_output_ata=False,
        fixed_output_amount=123,
        input_mint=WSOL_TOKEN_ACCOUNT,
    )
    swap = ixs[-1]
    assert len(swap.accounts) == 14
    assert swap.data[24] == SWAP_MODE_PARTIAL_FILL

    params.referral_token_account = referral
    params.include_rate_limiter_sysvar = True
    params.swap_mode = SWAP_MODE_EXACT_OUT
    ixs = build_buy_instructions(
        payer=payer,
        output_mint=mint,
        input_amount=1_000_000,
        params=params,
        create_input_ata=False,
        create_output_ata=False,
        fixed_output_amount=123,
        input_mint=WSOL_TOKEN_ACCOUNT,
    )
    swap = ixs[-1]
    assert len(swap.accounts) == 15
    assert swap.accounts[11].pubkey == referral
    assert swap.accounts[11].is_writable is True
    assert swap.accounts[14].pubkey == SYSVAR_INSTRUCTIONS
    assert swap.data[24] == SWAP_MODE_EXACT_OUT
    amount0 = int.from_bytes(swap.data[8:16], "little")
    amount1 = int.from_bytes(swap.data[16:24], "little")
    assert amount0 == 123
    assert amount1 == 1_000_000


def test_sol_usdc_direction_uses_explicit_mints_for_both_pool_orderings():
    from src.instruction.common import USDC_TOKEN_ACCOUNT, get_associated_token_address
    from src.instruction.meteora_damm_v2_builder import build_sell_instructions
    import pytest
    payer = Keypair().pubkey()
    for a, b in ((WSOL_TOKEN_ACCOUNT, USDC_TOKEN_ACCOUNT), (USDC_TOKEN_ACCOUNT, WSOL_TOKEN_ACCOUNT)):
        pool = MeteoraDammV2Params(pool=Keypair().pubkey(), token_a_mint=a, token_b_mint=b,
            token_a_vault=Keypair().pubkey(), token_b_vault=Keypair().pubkey(),
            token_a_program=TOKEN_PROGRAM, token_b_program=TOKEN_PROGRAM)
        for sell in (False, True):
            src, dst = (USDC_TOKEN_ACCOUNT, WSOL_TOKEN_ACCOUNT) if sell else (WSOL_TOKEN_ACCOUNT, USDC_TOKEN_ACCOUNT)
            builder = build_sell_instructions if sell else build_buy_instructions
            args = dict(payer=payer, input_mint=src, output_mint=dst, input_amount=10000,
                fixed_output_amount=1, params=pool, create_output_ata=False)
            if not sell: args['create_input_ata'] = False
            swap = builder(**args)[-1]
            assert swap.accounts[2].pubkey == get_associated_token_address(payer, src, TOKEN_PROGRAM)
            assert swap.accounts[3].pubkey == get_associated_token_address(payer, dst, TOKEN_PROGRAM)
            with pytest.raises(ValueError):
                builder(**{**args, 'output_mint': src})
