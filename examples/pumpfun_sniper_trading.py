"""
PumpFun Sniper Trading Example

This example demonstrates how to snipe new tokens on PumpFun.
Listen for creator first buy events and execute a buy + sell.
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
from sol_trade_sdk.trading.params import PumpFunParams
from solders.keypair import Keypair
from solders.pubkey import Pubkey


async def create_client():
    """Create SolanaTrade client"""
    payer = Keypair()  # Use your keypair here
    rpc_url = os.getenv("RPC_URL", "https://api.mainnet-beta.solana.com")

    swqos_configs = [
        SwqosConfig(type=SwqosType.DEFAULT, url=rpc_url),
        SwqosConfig(type=SwqosType.JITO, uuid="your_uuid", region=SwqosRegion.FRANKFURT),
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


async def pumpfun_sniper_trade(
    client: TradingClient,
    mint: Pubkey,
    bonding_curve: Pubkey,
    associated_bonding_curve: Pubkey,
    creator: Pubkey,
    creator_vault: Pubkey,
    fee_recipient: Pubkey,
    virtual_token_reserves: int,
    virtual_sol_reserves: int,
    real_token_reserves: int,
    real_sol_reserves: int,
    is_cashback_coin: bool = False,
):
    """Execute a snipe trade on PumpFun"""
    slippage_basis_points = 300
    recent_blockhash = await client.get_latest_blockhash()

    # Configure gas fee strategy
    gas_fee_strategy = GasFeeStrategy()
    gas_fee_strategy.set_global_fee_strategy(150000, 150000, 500000, 500000, 0.001, 0.001)

    # Buy parameters
    buy_sol_amount = 100_000  # 0.0001 SOL

    buy_params = TradeBuyParams(
        dex_type=DexType.PUMPFUN,
        input_token_type=TradeTokenType.SOL,
        mint=mint,
        input_token_amount=buy_sol_amount,
        slippage_basis_points=slippage_basis_points,
        recent_blockhash=recent_blockhash,
        extension_params=PumpFunParams(
            bonding_curve=bonding_curve,
            associated_bonding_curve=associated_bonding_curve,
            mint=mint,
            creator=creator,
            creator_vault=creator_vault,
            virtual_token_reserves=virtual_token_reserves,
            virtual_sol_reserves=virtual_sol_reserves,
            real_token_reserves=real_token_reserves,
            real_sol_reserves=real_sol_reserves,
            has_creator=True,
            fee_recipient=fee_recipient,
            is_cashback_coin=is_cashback_coin,
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
    token_balance = await client.get_token_balance(mint)
    print(f"Token balance: {token_balance}")

    # Sell parameters
    sell_params = TradeSellParams(
        dex_type=DexType.PUMPFUN,
        output_token_type=TradeTokenType.SOL,
        mint=mint,
        input_token_amount=token_balance,
        slippage_basis_points=slippage_basis_points,
        recent_blockhash=recent_blockhash,
        extension_params=PumpFunParams(
            bonding_curve=bonding_curve,
            associated_bonding_curve=associated_bonding_curve,
            mint=mint,
            creator=creator,
            creator_vault=creator_vault,
            virtual_token_reserves=virtual_token_reserves,
            virtual_sol_reserves=virtual_sol_reserves,
            real_token_reserves=real_token_reserves,
            real_sol_reserves=real_sol_reserves,
            has_creator=True,
            fee_recipient=fee_recipient,
            is_cashback_coin=is_cashback_coin,
        ),
        wait_transaction_confirmed=True,
        create_output_token_ata=True,
        close_output_token_ata=True,
        gas_fee_strategy=gas_fee_strategy,
    )

    # Execute sell
    sell_result = await client.sell(sell_params)
    print(f"Sell signature: {sell_result.signature}")
    print("Snipe buy + sell completed!")


async def main():
    client = await create_client()
    print(f"Client created: {client.payer_pubkey}")
    print("Waiting for PumpFun events...")

    # In a real scenario, you would subscribe to gRPC events
    # and call pumpfun_sniper_trade when a snipe opportunity is detected


if __name__ == "__main__":
    asyncio.run(main())
