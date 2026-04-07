"""
Raydium AMM V4 Trading Example

This example demonstrates how to trade on Raydium AMM V4.
Subscribe to swap events via gRPC and execute a buy + sell.
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
from sol_trade_sdk.trading.params import RaydiumAmmV4Params
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


async def raydium_amm_v4_trade(
    client: TradingClient,
    amm: Pubkey,
    coin_mint: Pubkey,
    pc_mint: Pubkey,
    token_coin: Pubkey,
    token_pc: Pubkey,
    coin_reserve: int,
    pc_reserve: int,
):
    """Execute a trade on Raydium AMM V4"""
    slippage_basis_points = 100
    recent_blockhash = await client.get_latest_blockhash()

    # Configure gas fee strategy
    gas_fee_strategy = GasFeeStrategy()
    gas_fee_strategy.set_global_fee_strategy(150000, 150000, 500000, 500000, 0.001, 0.001)

    # Determine token type (WSOL or USDC)
    WSOL_TOKEN_ACCOUNT = Pubkey.from_string("So11111111111111111111111111111111111111112")
    USDC_TOKEN_ACCOUNT = Pubkey.from_string("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")

    is_wsol = pc_mint == WSOL_TOKEN_ACCOUNT or coin_mint == WSOL_TOKEN_ACCOUNT
    input_token_type = TradeTokenType.WSOL if is_wsol else TradeTokenType.USDC

    # Determine mint to trade
    mint_pubkey = coin_mint if pc_mint in [WSOL_TOKEN_ACCOUNT, USDC_TOKEN_ACCOUNT] else pc_mint

    # Build params
    params = RaydiumAmmV4Params(
        amm=amm,
        coin_mint=coin_mint,
        pc_mint=pc_mint,
        token_coin=token_coin,
        token_pc=token_pc,
        coin_reserve=coin_reserve,
        pc_reserve=pc_reserve,
    )

    # Buy parameters
    input_token_amount = 100_000  # 0.0001 SOL or USDC

    buy_params = TradeBuyParams(
        dex_type=DexType.RAYDIUM_AMM_V4,
        input_token_type=input_token_type,
        mint=mint_pubkey,
        input_token_amount=input_token_amount,
        slippage_basis_points=slippage_basis_points,
        recent_blockhash=recent_blockhash,
        extension_params=params,
        wait_transaction_confirmed=True,
        create_input_token_ata=is_wsol,
        close_input_token_ata=is_wsol,
        create_mint_ata=True,
        gas_fee_strategy=gas_fee_strategy,
    )

    # Execute buy
    buy_result = await client.buy(buy_params)
    print(f"Buy signature: {buy_result.signature}")

    # Get token balance for sell
    token_balance = await client.get_token_balance(mint_pubkey)
    print(f"Token balance: {token_balance}")

    # Fetch fresh params for sell (reserves may have changed)
    sell_params = TradeSellParams(
        dex_type=DexType.RAYDIUM_AMM_V4,
        output_token_type=input_token_type,
        mint=mint_pubkey,
        input_token_amount=token_balance,
        slippage_basis_points=slippage_basis_points,
        recent_blockhash=recent_blockhash,
        extension_params=params,  # In real scenario, fetch fresh params via RPC
        wait_transaction_confirmed=True,
        create_output_token_ata=is_wsol,
        close_output_token_ata=is_wsol,
        close_mint_token_ata=False,
        gas_fee_strategy=gas_fee_strategy,
    )

    # Execute sell
    sell_result = await client.sell(sell_params)
    print(f"Sell signature: {sell_result.signature}")
    print("Raydium AMM V4 trade completed!")


async def main():
    client = await create_client()
    print(f"Client created: {client.payer_pubkey}")
    print("Ready for Raydium AMM V4 trading...")

    # In a real scenario, you would:
    # 1. Subscribe to gRPC events for Raydium AMM V4 swaps
    # 2. Fetch AMM info via RPC using fetch_amm_info
    # 3. Call raydium_amm_v4_trade with the parameters


if __name__ == "__main__":
    asyncio.run(main())
