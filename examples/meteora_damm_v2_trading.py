"""
Meteora DAMM V2 Trading Example

This example demonstrates how to trade on Meteora DAMM V2.
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
from sol_trade_sdk.trading.params import MeteoraDammV2Params
from solders.keypair import Keypair
from solders.pubkey import Pubkey


async def main():
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

    client = await TradingClient.new(payer, trade_config)
    print(f"Client created: {client.payer_pubkey}")

    # Example pool parameters (replace with actual values)
    pool_address = Pubkey()  # Pool address
    token_a_mint = Pubkey()  # Token A mint
    token_b_mint = Pubkey()  # Token B mint
    token_a_vault = Pubkey()  # Token A vault
    token_b_vault = Pubkey()  # Token B vault

    slippage_basis_points = 500
    recent_blockhash = await client.get_latest_blockhash()

    gas_fee_strategy = GasFeeStrategy()
    gas_fee_strategy.set_global_fee_strategy(150000, 150000, 500000, 500000, 0.001, 0.001)

    # Buy parameters
    buy_params = TradeBuyParams(
        dex_type=DexType.METEORA_DAMM_V2,
        input_token_type=TradeTokenType.SOL,
        mint=token_a_mint,
        input_token_amount=100_000,
        slippage_basis_points=slippage_basis_points,
        recent_blockhash=recent_blockhash,
        extension_params=MeteoraDammV2Params(
            pool_address=pool_address,
            token_a_mint=token_a_mint,
            token_b_mint=token_b_mint,
            token_a_vault=token_a_vault,
            token_b_vault=token_b_vault,
        ),
        wait_transaction_confirmed=True,
        create_input_token_ata=True,
        create_mint_ata=True,
        gas_fee_strategy=gas_fee_strategy,
    )

    print("Ready for Meteora DAMM V2 trading...")


if __name__ == "__main__":
    asyncio.run(main())
