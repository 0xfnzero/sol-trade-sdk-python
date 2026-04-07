"""
Bonk Sniper Trading Example

This example demonstrates how to snipe new tokens on Bonk.
Listen for developer token creation events and execute a buy + sell.
Uses ShredStream for ultra-low latency.
"""

import asyncio
import os
from sol_trade_sdk import (
    TradeConfig,
    SwqosConfig,
    SwqosType,
    TradingClient,
    TradeBuyParams,
    TradeSellParams,
    DexType,
    TradeTokenType,
    GasFeeStrategy,
)
from sol_trade_sdk.trading.params import BonkParams
from solders.keypair import Keypair
from solders.pubkey import Pubkey


async def create_client():
    """Create SolanaTrade client"""
    payer = Keypair()  # Use your keypair here
    rpc_url = os.getenv("RPC_URL", "https://api.mainnet-beta.solana.com")

    swqos_configs = [
        SwqosConfig(type=SwqosType.DEFAULT, url=rpc_url),
    ]

    trade_config = (
        TradeConfig.builder(rpc_url)
        .swqos_configs(swqos_configs)
        # .log_enabled(False)       # disable logging
        # .check_min_tip(True)      # enforce minimum tip check
        # .mev_protection(True)     # enable MEV protection (sandwichMitigation / port 9000)
        .build()
    )

    return await TradingClient.new(payer, trade_config)


async def bonk_sniper_trade(
    client: TradingClient,
    base_token_mint: Pubkey,
    quote_token_mint: Pubkey,
    pool_state: Pubkey,
    base_vault: Pubkey,
    quote_vault: Pubkey,
    base_token_program: Pubkey,
    platform_config: Pubkey,
    platform_associated_account: Pubkey,
    creator_associated_account: Pubkey,
    global_config: Pubkey,
    exact_in: bool = True,
    amount_in: int = 0,
    amount_out: int = 0,
):
    """
    Execute a snipe trade on Bonk for developer-created tokens

    This is called when a dev_create_token_trade event is detected.
    """
    slippage_basis_points = 300
    recent_blockhash = await client.get_latest_blockhash()

    # Configure gas fee strategy
    gas_fee_strategy = GasFeeStrategy()
    gas_fee_strategy.set_global_fee_strategy(150000, 150000, 500000, 500000, 0.001, 0.001)

    # Determine token type
    USD1_TOKEN_ACCOUNT = Pubkey.from_string("B9C6PQJqM9vLZHMvPMJUfzHvPrPxYT4rL5hXhgS3nYVr")
    token_type = TradeTokenType.USD1 if quote_token_mint == USD1_TOKEN_ACCOUNT else TradeTokenType.SOL

    # Buy parameters
    buy_sol_amount = 100_000  # 0.0001 SOL or USD1

    buy_params = TradeBuyParams(
        dex_type=DexType.BONK,
        input_token_type=token_type,
        mint=base_token_mint,
        input_token_amount=buy_sol_amount,
        slippage_basis_points=slippage_basis_points,
        recent_blockhash=recent_blockhash,
        extension_params=BonkParams.from_dev_trade(
            exact_in=exact_in,
            amount_in=amount_in,
            amount_out=amount_out,
            pool_state=pool_state,
            base_vault=base_vault,
            quote_vault=quote_vault,
            base_token_program=base_token_program,
            platform_config=platform_config,
            platform_associated_account=platform_associated_account,
            creator_associated_account=creator_associated_account,
            global_config=global_config,
        ),
        wait_transaction_confirmed=True,
        create_input_token_ata=True,
        close_input_token_ata=True,
        create_mint_ata=True,
        gas_fee_strategy=gas_fee_strategy,
    )

    # Execute buy
    buy_result = await client.buy(buy_params)
    print(f"Buy signature: {buy_result.signature}")

    # Get token balance for sell
    token_balance = await client.get_token_balance(base_token_mint)
    print(f"Token balance: {token_balance}")

    # Sell parameters
    sell_params = TradeSellParams(
        dex_type=DexType.BONK,
        output_token_type=token_type,
        mint=base_token_mint,
        input_token_amount=token_balance,
        slippage_basis_points=slippage_basis_points,
        recent_blockhash=recent_blockhash,
        extension_params=BonkParams.immediate_sell(
            base_token_program=base_token_program,
            platform_config=platform_config,
            platform_associated_account=platform_associated_account,
            creator_associated_account=creator_associated_account,
            global_config=global_config,
        ),
        wait_transaction_confirmed=True,
        create_output_token_ata=True,
        close_output_token_ata=True,
        close_mint_token_ata=False,
        gas_fee_strategy=gas_fee_strategy,
    )

    # Execute sell
    sell_result = await client.sell(sell_params)
    print(f"Sell signature: {sell_result.signature}")
    print("Bonk snipe buy + sell completed!")


async def main():
    client = await create_client()
    print(f"Client created: {client.payer_pubkey}")
    print("Waiting for Bonk events...")

    # In a real scenario, you would:
    # 1. Subscribe to ShredStream for Bonk events
    # 2. Filter for is_dev_create_token_trade events
    # 3. Call bonk_sniper_trade with the event parameters


if __name__ == "__main__":
    asyncio.run(main())
