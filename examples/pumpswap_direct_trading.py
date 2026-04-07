"""
PumpSwap Direct Trading Example

This example demonstrates direct trading on PumpSwap without gRPC.
Fetch params via RPC and execute buy + sell.
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


async def pumpswap_direct_trade(
    client: TradingClient,
    pool: Pubkey,
    mint: Pubkey,
):
    """Execute a direct trade on PumpSwap via RPC"""
    print("Testing PumpSwap direct trading...")

    slippage_basis_points = 100
    recent_blockhash = await client.get_latest_blockhash()

    # Configure gas fee strategy
    gas_fee_strategy = GasFeeStrategy()
    gas_fee_strategy.set_global_fee_strategy(150000, 150000, 500000, 500000, 0.001, 0.001)

    # Fetch params via RPC
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

    # Get token balance for sell
    token_balance = await client.get_token_balance(mint)
    print(f"Token balance: {token_balance}")

    # Fetch fresh params for sell
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
    print("PumpSwap direct trade completed!")


async def main():
    client = await create_client()
    print(f"Client created: {client.payer_pubkey}")
    print("Testing PumpSwap direct trading...")

    # Example pool and mint addresses
    pool = Pubkey.from_string("9qKxzRejsV6Bp2zkefXWCbGvg61c3hHei7ShXJ4FythA")
    mint = Pubkey.from_string("2zMMhcVQEXDtdE6vsFS7S7D5oUodfJHE8vd1gnBouauv")

    # Execute trade
    await pumpswap_direct_trade(client, pool, mint)


if __name__ == "__main__":
    asyncio.run(main())
