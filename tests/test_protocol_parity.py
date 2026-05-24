import pytest
from solders.pubkey import Pubkey

from src import SOL_TOKEN_ACCOUNT, TOKEN_PROGRAM, WSOL_TOKEN_ACCOUNT
from src.instruction.meteora_damm_v2_builder import (
    METEORA_DAMM_V2_PROGRAM_ID,
    SWAP2_DISCRIMINATOR,
    SWAP_MODE_PARTIAL_FILL,
    MeteoraDammV2Params,
    build_buy_instructions as build_meteora_buy_instructions,
)
from src.instruction.raydium_amm_v4_builder import (
    SWAP_BASE_OUT_DISCRIMINATOR,
    RaydiumAmmV4Params,
    build_buy_instructions as build_raydium_amm_v4_buy_instructions,
)


def pk(seed: int) -> Pubkey:
    return Pubkey(bytes([seed]) * 32)


def test_raydium_amm_v4_uses_market_account_order():
    ixs = build_raydium_amm_v4_buy_instructions(
        payer=pk(99),
        output_mint=pk(2),
        input_amount=100_000,
        fixed_output_amount=42,
        create_input_ata=False,
        create_output_ata=False,
        params=RaydiumAmmV4Params(
            amm=pk(1),
            coin_mint=WSOL_TOKEN_ACCOUNT,
            pc_mint=pk(2),
            token_coin=pk(3),
            token_pc=pk(4),
            amm_open_orders=pk(5),
            amm_target_orders=pk(6),
            serum_program=pk(7),
            serum_market=pk(8),
            serum_bids=pk(9),
            serum_asks=pk(10),
            serum_event_queue=pk(11),
            serum_coin_vault_account=pk(12),
            serum_pc_vault_account=pk(13),
            serum_vault_signer=pk(14),
            coin_reserve=1_000_000_000,
            pc_reserve=2_000_000_000,
        ),
    )
    ix = ixs[-1]

    assert len(ix.accounts) == 18
    assert bytes(ix.data)[0:1] == SWAP_BASE_OUT_DISCRIMINATOR
    assert ix.accounts[3].pubkey == pk(5)
    assert ix.accounts[4].pubkey == pk(6)
    assert ix.accounts[7].pubkey == pk(7)
    assert ix.accounts[14].pubkey == pk(14)


def test_raydium_amm_v4_rejects_buy_output_mint_mismatch():
    with pytest.raises(ValueError, match="output_mint"):
        build_raydium_amm_v4_buy_instructions(
            payer=pk(99),
            output_mint=pk(3),
            input_amount=100_000,
            fixed_output_amount=42,
            create_input_ata=False,
            create_output_ata=False,
            params=RaydiumAmmV4Params(
                amm=pk(1),
                coin_mint=WSOL_TOKEN_ACCOUNT,
                pc_mint=pk(2),
                token_coin=pk(3),
                token_pc=pk(4),
                amm_open_orders=pk(5),
                amm_target_orders=pk(6),
                serum_program=pk(7),
                serum_market=pk(8),
                serum_bids=pk(9),
                serum_asks=pk(10),
                serum_event_queue=pk(11),
                serum_coin_vault_account=pk(12),
                serum_pc_vault_account=pk(13),
                serum_vault_signer=pk(14),
                coin_reserve=1_000_000_000,
                pc_reserve=2_000_000_000,
            ),
        )


def test_meteora_damm_v2_uses_swap2_partial_fill():
    ixs = build_meteora_buy_instructions(
        payer=pk(99),
        input_mint=WSOL_TOKEN_ACCOUNT,
        output_mint=pk(2),
        input_amount=100_000,
        fixed_output_amount=42,
        create_input_ata=False,
        create_output_ata=False,
        params=MeteoraDammV2Params(
            pool=pk(1),
            token_a_mint=WSOL_TOKEN_ACCOUNT,
            token_b_mint=pk(2),
            token_a_vault=pk(3),
            token_b_vault=pk(4),
            token_a_program=TOKEN_PROGRAM,
            token_b_program=TOKEN_PROGRAM,
        ),
    )
    ix = ixs[-1]
    data = bytes(ix.data)

    assert len(ix.accounts) == 13
    assert data[:8] == SWAP2_DISCRIMINATOR
    assert data[24] == SWAP_MODE_PARTIAL_FILL
    assert ix.accounts[12].pubkey == METEORA_DAMM_V2_PROGRAM_ID


def test_meteora_damm_v2_accepts_sol_alias_for_wsol_input():
    ixs = build_meteora_buy_instructions(
        payer=pk(99),
        input_mint=SOL_TOKEN_ACCOUNT,
        output_mint=pk(2),
        input_amount=100_000,
        fixed_output_amount=42,
        create_input_ata=False,
        create_output_ata=False,
        params=MeteoraDammV2Params(
            pool=pk(1),
            token_a_mint=WSOL_TOKEN_ACCOUNT,
            token_b_mint=pk(2),
            token_a_vault=pk(3),
            token_b_vault=pk(4),
            token_a_program=TOKEN_PROGRAM,
            token_b_program=TOKEN_PROGRAM,
        ),
    )

    assert ixs[-1].accounts[6].pubkey == WSOL_TOKEN_ACCOUNT
