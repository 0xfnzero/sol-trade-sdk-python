from solders.pubkey import Pubkey

from src import PumpFunParams, PumpSwapParams, TOKEN_PROGRAM, USDC_TOKEN_ACCOUNT


def test_pumpfun_params_from_parser_trade_uses_quote_reserves():
    event = {
        "mint": "11111111111111111111111111111111",
        "bonding_curve": "11111111111111111111111111111111",
        "associated_bonding_curve": "11111111111111111111111111111111",
        "creator": "11111111111111111111111111111111",
        "creator_vault": "11111111111111111111111111111111",
        "fee_recipient": "11111111111111111111111111111111",
        "token_program": str(TOKEN_PROGRAM),
        "quote_mint": str(USDC_TOKEN_ACCOUNT),
        "virtual_token_reserves": 1_000_000,
        "virtual_sol_reserves": 30_000_000_000,
        "virtual_quote_reserves": 4_292_000_000,
        "real_token_reserves": 900_000,
        "real_sol_reserves": 20_000_000_000,
        "real_quote_reserves": 123_456,
        "is_cashback_coin": True,
        "mayhem_mode": False,
    }

    params = PumpFunParams.from_parser_trade_event(event)

    assert params.quote_mint == USDC_TOKEN_ACCOUNT
    assert params.bonding_curve.virtual_sol_reserves == 4_292_000_000
    assert params.bonding_curve.real_sol_reserves == 123_456
    assert params.bonding_curve.is_cashback_coin is True


def test_pumpfun_params_from_parser_trade_preserves_zero_quote_reserves():
    event = {
        "mint": "11111111111111111111111111111111",
        "bonding_curve": "11111111111111111111111111111111",
        "associated_bonding_curve": "11111111111111111111111111111111",
        "creator": "11111111111111111111111111111111",
        "creator_vault": "11111111111111111111111111111111",
        "fee_recipient": "11111111111111111111111111111111",
        "token_program": str(TOKEN_PROGRAM),
        "quote_mint": str(USDC_TOKEN_ACCOUNT),
        "virtual_token_reserves": 1_000_000,
        "virtual_sol_reserves": 30_000_000_000,
        "virtual_quote_reserves": 0,
        "real_token_reserves": 900_000,
        "real_sol_reserves": 20_000_000_000,
        "real_quote_reserves": 0,
    }

    params = PumpFunParams.from_parser_trade_event(event)

    assert params.bonding_curve.virtual_sol_reserves == 0
    assert params.bonding_curve.real_sol_reserves == 0


def test_pumpswap_params_from_parser_event_uses_creator_vault_accounts():
    vault = Pubkey.new_unique()
    authority = Pubkey.new_unique()
    event = {
        "pool": str(Pubkey.new_unique()),
        "base_mint": str(Pubkey.new_unique()),
        "quote_mint": str(USDC_TOKEN_ACCOUNT),
        "pool_base_token_account": str(Pubkey.new_unique()),
        "pool_quote_token_account": str(Pubkey.new_unique()),
        "pool_base_token_reserves": 10,
        "pool_quote_token_reserves": 20,
        "coin_creator_vault_ata": str(vault),
        "coin_creator_vault_authority": str(authority),
        "base_token_program": str(TOKEN_PROGRAM),
        "quote_token_program": str(TOKEN_PROGRAM),
    }

    params = PumpSwapParams.from_parser_event(event)

    assert params.coin_creator_vault_ata == vault
    assert params.coin_creator_vault_authority == authority
