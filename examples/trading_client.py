"""
TradingClient Creation Example

This example demonstrates two ways to create a TradingClient:
1. Simple method: TradingClient() - creates client with its own infrastructure
2. Shared method: TradingClient.from_infrastructure() - reuses existing infrastructure

For multi-wallet scenarios, see the shared_infrastructure example.
"""

import asyncio
import os
from sol_trade_sdk import (
    TradeConfig,
    SwqosConfig,
    SwqosType,
    SwqosRegion,
    TradingClient,
    InfrastructureConfig,
    TradingInfrastructure,
)
from solders.keypair import Keypair


async def create_trading_client_simple():
    """
    Method 1: Create TradingClient using TradeConfig (simple, self-contained)

    Use this when you have a single wallet or don't need to share infrastructure.
    """
    payer = Keypair()  # Use your keypair here
    rpc_url = os.getenv("RPC_URL", "https://api.mainnet-beta.solana.com")

    swqos_configs = [
        SwqosConfig(type=SwqosType.DEFAULT, url=rpc_url),
        SwqosConfig(type=SwqosType.JITO, uuid="your_uuid", region=SwqosRegion.FRANKFURT),
        SwqosConfig(type=SwqosType.BLOXROUTE, api_token="your_api_token", region=SwqosRegion.FRANKFURT),
        SwqosConfig(type=SwqosType.ZEROSLOT, api_token="your_api_token", region=SwqosRegion.FRANKFURT),
        SwqosConfig(type=SwqosType.TEMPORAL, api_token="your_api_token", region=SwqosRegion.FRANKFURT),
    ]

    trade_config = (
        TradeConfig.builder(rpc_url)
        .swqos_configs(swqos_configs)
        # .log_enabled(False)       # disable logging
        # .check_min_tip(True)      # enforce minimum tip check
        # .mev_protection(True)     # enable MEV protection (sandwichMitigation / port 9000)
        .build()
    )

    # Creates new infrastructure internally
    client = await TradingClient.new(payer, trade_config)
    print(f"Method 1: Created TradingClient with new()")
    print(f"  Wallet: {client.payer_pubkey}")
    return client


async def create_trading_client_from_infrastructure():
    """
    Method 2: Create TradingClient from shared infrastructure

    Use this when you have multiple wallets sharing the same configuration.
    The infrastructure (RPC client, SWQOS clients) is created once and shared.
    """
    payer = Keypair()  # Use your keypair here
    rpc_url = os.getenv("RPC_URL", "https://api.mainnet-beta.solana.com")

    swqos_configs = [
        SwqosConfig(type=SwqosType.DEFAULT, url=rpc_url),
        SwqosConfig(type=SwqosType.JITO, uuid="your_uuid", region=SwqosRegion.FRANKFURT),
    ]

    # Create infrastructure separately (can be shared across multiple wallets)
    infra_config = InfrastructureConfig(
        rpc_url=rpc_url,
        swqos_configs=swqos_configs,
    )
    infrastructure = await TradingInfrastructure.new(infra_config)

    # Create client from existing infrastructure (fast, no async needed)
    client = TradingClient.from_infrastructure(payer, infrastructure, use_seed_optimize=True)
    print(f"Method 2: Created TradingClient with from_infrastructure()")
    print(f"  Wallet: {client.payer_pubkey}")
    return client


async def main():
    # Method 1: Simple - TradingClient.new() (recommended for single wallet)
    client1 = await create_trading_client_simple()

    # Method 2: From infrastructure (recommended for multiple wallets)
    client2 = await create_trading_client_from_infrastructure()


if __name__ == "__main__":
    asyncio.run(main())



async def create_trading_client_from_infrastructure():
    """
    Method 2: Create TradingClient from shared infrastructure

    Use this when you have multiple wallets sharing the same configuration.
    The infrastructure (RPC client, SWQOS clients) is created once and shared.
    """
    payer = Keypair()  # Use your keypair here
    rpc_url = os.getenv("RPC_URL", "https://api.mainnet-beta.solana.com")

    swqos_configs = [
        SwqosConfig(type=SwqosType.DEFAULT, url=rpc_url),
        SwqosConfig(type=SwqosType.JITO, uuid="your_uuid", region=SwqosRegion.FRANKFURT),
    ]

    # Create infrastructure separately (can be shared across multiple wallets)
    infra_config = InfrastructureConfig(
        rpc_url=rpc_url,
        swqos_configs=swqos_configs,
    )
    infrastructure = await TradingInfrastructure.new(infra_config)

    # Create client from existing infrastructure (fast, no async needed)
    client = TradingClient.from_infrastructure(payer, infrastructure, use_seed_optimize=True)
    print(f"Method 2: Created TradingClient with from_infrastructure()")
    print(f"  Wallet: {client.payer_pubkey}")
    return client


async def main():
    # Method 1: Simple - TradingClient.new() (recommended for single wallet)
    client1 = await create_trading_client_simple()

    # Method 2: From infrastructure (recommended for multiple wallets)
    client2 = await create_trading_client_from_infrastructure()


if __name__ == "__main__":
    asyncio.run(main())
