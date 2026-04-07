"""
PumpSwap Trading Example

This example demonstrates how to trade on PumpSwap (Pump AMM).
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


async def pumpswap_trade(
    client: TradingClient,
    pool: Pubkey,
    base_mint: Pubkey,
    quote_mint: Pubkey,
    pool_base_token_account: Pubkey,
    pool_quote_token_account: Pubkey,
    pool_base_token_reserves: int,
    pool_quote_token_reserves: int,
    protocol_fee_recipient: Pubkey,
    base_token_program: Pubkey,
    quote_token_program: Pubkey,
    is_cashback_coin: bool = False,
):
    """Execute a trade on PumpSwap"""
    slippage_basis_points = 500
    recent_blockhash = await client.get_latest_blockhash()

    # Configure gas fee strategy
    gas_fee_strategy = GasFeeStrategy()
    gas_fee_strategy.set_global_fee_strategy(150000, 150000, 500000, 500000, 0.001, 0.001)

    # Determine if SOL is involved
    is_sol = True  # Assuming WSOL is involved

    # Buy parameters
    buy_token_amount = 300_000  # 0.0003 SOL

    buy_params = TradeBuyParams(
        dex_type=DexType.PUMPSWAP,
        input_token_type=TradeTokenType.SOL if is_sol else TradeTokenType.USDC,
        mint=quote_mint,  # The token we're buying
        input_token_amount=buy_token_amount,
        slippage_basis_points=slippage_basis_points,
        recent_blockhash=recent_blockhash,
        extension_params=PumpSwapParams(
            pool=pool,
            base_mint=base_mint,
            quote_mint=quote_mint,
            pool_base_token_account=pool_base_token_account,
            pool_quote_token_account=pool_quote_token_account,
            pool_base_token_reserves=pool_base_token_reserves,
            pool_quote_token_reserves=pool_quote_token_reserves,
            protocol_fee_recipient=protocol_fee_recipient,
            base_token_program=base_token_program,
            quote_token_program=quote_token_program,
            is_cashback_coin=is_cashback_coin,
        ),
        wait_transaction_confirmed=True,
        create_input_token_ata=is_sol,
        close_input_token_ata=is_sol,
        create_mint_ata=True,
        gas_fee_strategy=gas_fee_strategy,
    )

    # Execute buy
    buy_result = await client.buy(buy_params)
    print(f"Buy signature: {buy_result.signature}")

    # Get token balance for sell
    token_balance = await client.get_token_balance(quote_mint)
    print(f"Token balance: {token_balance}")

    # Sell parameters
    sell_params = TradeSellParams(
        dex_type=DexType.PUMPSWAP,
        output_token_type=TradeTokenType.SOL if is_sol else TradeTokenType.USDC,
        mint=quote_mint,
        input_token_amount=token_balance,
        slippage_basis_points=slippage_basis_points,
        recent_blockhash=recent_blockhash,
        extension_params=PumpSwapParams(
            pool=pool,
            base_mint=base_mint,
            quote_mint=quote_mint,
            pool_base_token_account=pool_base_token_account,
            pool_quote_token_account=pool_quote_token_account,
            pool_base_token_reserves=pool_base_token_reserves,
            pool_quote_token_reserves=pool_quote_token_reserves,
            protocol_fee_recipient=protocol_fee_recipient,
            base_token_program=base_token_program,
            quote_token_program=quote_token_program,
            is_cashback_coin=is_cashback_coin,
        ),
        wait_transaction_confirmed=True,
        create_output_token_ata=is_sol,
        close_output_token_ata=is_sol,
        gas_fee_strategy=gas_fee_strategy,
    )

    # Execute sell
    sell_result = await client.sell(sell_params)
    print(f"Sell signature: {sell_result.signature}")
    print("PumpSwap trade completed!")


async def main():
    client = await create_client()
    print(f"Client created: {client.payer_pubkey}")
    print("Ready for PumpSwap trading...")


if __name__ == "__main__":
    asyncio.run(main())
