"""
Raydium CPMM Trading Example

This example demonstrates how to trade on Raydium CPMM.
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
from sol_trade_sdk.trading.params import RaydiumCPMMParams
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
    pool_id = Pubkey()  # Pool ID
    amm_config = Pubkey()  # AMM config
    base_mint = Pubkey()  # Base token mint
    quote_mint = Pubkey()  # Quote token mint

    slippage_basis_points = 500
    recent_blockhash = await client.get_latest_blockhash()

    gas_fee_strategy = GasFeeStrategy()
    gas_fee_strategy.set_global_fee_strategy(150000, 150000, 500000, 500000, 0.001, 0.001)

    # Buy parameters
    buy_params = TradeBuyParams(
        dex_type=DexType.RAYDIUM_CPMM,
        input_token_type=TradeTokenType.SOL,
        mint=base_mint,
        input_token_amount=100_000,
        slippage_basis_points=slippage_basis_points,
        recent_blockhash=recent_blockhash,
        extension_params=RaydiumCPMMParams(
            pool_id=pool_id,
            amm_config=amm_config,
            base_mint=base_mint,
            quote_mint=quote_mint,
        ),
        wait_transaction_confirmed=True,
        create_input_token_ata=True,
        create_mint_ata=True,
        gas_fee_strategy=gas_fee_strategy,
    )

    print("Ready for Raydium CPMM trading...")


if __name__ == "__main__":
    asyncio.run(main())
