"""
Nonce Cache Example

This example demonstrates how to use durable nonce for transaction submission.
Use durable nonce to implement transaction replay protection and optimize
transaction processing when using multiple MEV services.
"""

import asyncio
import os
from sol_trade_sdk import (
    TradeConfig,
    SwqosConfig,
    SwqosType,
    TradingClient,
    TradeBuyParams,
    DexType,
    TradeTokenType,
    GasFeeStrategy,
)
from sol_trade_sdk.trading.params import PumpFunParams
from sol_trade_sdk.common.nonce_cache import fetch_nonce_info
from solders.keypair import Keypair
from solders.pubkey import Pubkey


async def create_client():
    """Create SolanaTrade client"""
    payer = Keypair()  # Use your keypair here
    rpc_url = os.getenv("RPC_URL", "https://api.mainnet-beta.solana.com")

    swqos_configs = [
        SwqosConfig(type=SwqosType.DEFAULT, url=rpc_url),
        SwqosConfig(type=SwqosType.JITO, uuid="your_uuid"),
        SwqosConfig(type=SwqosType.BLOXROUTE, api_token="your_api_token"),
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


async def trade_with_nonce(
    client: TradingClient,
    nonce_account: Pubkey,
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
    """
    Execute a trade using durable nonce

    When using multiple MEV services, you need to use durable nonce.
    Use fetch_nonce_info to get the latest nonce value.
    """
    # Fetch nonce info
    durable_nonce = await fetch_nonce_info(client.infrastructure.rpc, nonce_account)

    if durable_nonce is None:
        print("Failed to fetch nonce info")
        return

    print(f"Nonce authority: {durable_nonce.authority}")
    print(f"Nonce value: {durable_nonce.nonce}")

    # Configure gas fee strategy
    gas_fee_strategy = GasFeeStrategy()
    gas_fee_strategy.set_global_fee_strategy(150000, 150000, 500000, 500000, 0.001, 0.001)

    # Buy parameters - note we use durable_nonce instead of recent_blockhash
    buy_sol_amount = 100_000  # 0.0001 SOL

    buy_params = TradeBuyParams(
        dex_type=DexType.PUMPFUN,
        input_token_type=TradeTokenType.SOL,
        mint=mint,
        input_token_amount=buy_sol_amount,
        slippage_basis_points=100,
        recent_blockhash=None,  # Not used when durable_nonce is provided
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
        create_input_token_ata=False,
        close_input_token_ata=False,
        create_mint_ata=True,
        durable_nonce=durable_nonce,
        gas_fee_strategy=gas_fee_strategy,
    )

    # Execute buy with nonce
    buy_result = await client.buy(buy_params)
    print(f"Buy signature: {buy_result.signature}")
    print("Trade with nonce completed!")


async def main():
    client = await create_client()
    print(f"Client created: {client.payer_pubkey}")

    # Nonce account must be created beforehand
    nonce_account = Pubkey.from_string("use_your_nonce_account_here")
    print(f"Using nonce account: {nonce_account}")

    # In a real scenario, you would:
    # 1. Subscribe to gRPC events
    # 2. Fetch nonce info
    # 3. Execute trade with durable_nonce


if __name__ == "__main__":
    asyncio.run(main())
