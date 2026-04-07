"""
Seed Trading Example

This example demonstrates how to trade using seed optimization
for faster ATA derivation and account operations.
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
from sol_trade_sdk.trading.params import PumpSwapParams
from solders.keypair import Keypair
from solders.pubkey import Pubkey


async def create_client():
    """Create SolanaTrade client with seed optimization enabled"""
    payer = Keypair()  # Use your keypair here
    rpc_url = os.getenv("RPC_URL", "https://api.mainnet-beta.solana.com")

    swqos_configs = [
        SwqosConfig(type=SwqosType.DEFAULT, url=rpc_url),
    ]

    trade_config = (
        TradeConfig.builder(rpc_url)
        .swqos_configs(swqos_configs)
        .use_seed_optimize(True)  # Enable seed optimization
        # .mev_protection(True)   # Enable MEV protection (BlockRazor: sandwichMitigation, Astralane: port 9000)
        .build()
    )

    return await TradingClient.new(payer, trade_config)


async def seed_trading_example(
    client: TradingClient,
    pool: Pubkey,
    mint: Pubkey,
):
    """
    Execute a trade using seed optimization

    Seed optimization uses 'use seed' method for ATA derivation,
    which is faster than the standard method.
    """
    print("Testing PumpSwap trading with seed optimization...")

    slippage_basis_points = 100
    recent_blockhash = await client.get_latest_blockhash()

    # Configure gas fee strategy
    gas_fee_strategy = GasFeeStrategy()
    gas_fee_strategy.set_global_fee_strategy(150000, 150000, 500000, 500000, 0.001, 0.001)

    # Fetch pool params via RPC
    pumpswap_params = await PumpSwapParams.from_pool_address_by_rpc(
        client.infrastructure.rpc, pool
    )

    # Buy parameters
    buy_sol_amount = 100_000  # 0.0001 WSOL

    buy_params = TradeBuyParams(
        dex_type=DexType.PUMPSWAP,
        input_token_type=TradeTokenType.WSOL,
        mint=mint,
        input_token_amount=buy_sol_amount,
        slippage_basis_points=slippage_basis_points,
        recent_blockhash=recent_blockhash,
        extension_params=pumpswap_params,
        wait_transaction_confirmed=True,
        create_input_token_ata=True,
        close_input_token_ata=True,
        create_mint_ata=True,
        gas_fee_strategy=gas_fee_strategy,
    )

    # Execute buy
    print("Buying tokens from PumpSwap...")
    buy_result = await client.buy(buy_params)
    print(f"Buy signature: {buy_result.signature}")

    # Wait for confirmation
    await asyncio.sleep(4)

    # Get token balance for sell (uses seed optimization internally)
    token_balance = await client.get_token_balance(mint)
    print(f"Token balance: {token_balance}")

    # Sell parameters - fetch fresh params
    pumpswap_params = await PumpSwapParams.from_pool_address_by_rpc(
        client.infrastructure.rpc, pool
    )

    sell_params = TradeSellParams(
        dex_type=DexType.PUMPSWAP,
        output_token_type=TradeTokenType.WSOL,
        mint=mint,
        input_token_amount=token_balance,
        slippage_basis_points=slippage_basis_points,
        recent_blockhash=recent_blockhash,
        extension_params=pumpswap_params,
        wait_transaction_confirmed=True,
        create_output_token_ata=True,
        close_output_token_ata=True,
        close_mint_token_ata=False,
        gas_fee_strategy=gas_fee_strategy,
    )

    # Execute sell
    print("Selling tokens...")
    sell_result = await client.sell(sell_params)
    print(f"Sell signature: {sell_result.signature}")
    print("Seed trading example completed!")


async def main():
    # Create client with seed optimization
    client = await create_client()
    print(f"Client created: {client.payer_pubkey}")
    print(f"Seed optimization enabled: {client.use_seed_optimize}")

    # Example pool and mint addresses
    pool = Pubkey.from_string("9qKxzRejsV6Bp2zkefXWCbGvg61c3hHei7ShXJ4FythA")
    mint = Pubkey.from_string("2zMMhcVQEXDtdE6vsFS7S7D5oUodfJHE8vd1gnBouauv")

    # In a real scenario, you would call seed_trading_example
    # with actual pool and mint addresses


if __name__ == "__main__":
    asyncio.run(main())
