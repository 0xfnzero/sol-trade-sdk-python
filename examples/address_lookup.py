"""
Address Lookup Table Example

This example demonstrates how to use Address Lookup Tables (ALT)
to optimize transaction size and reduce fees.
"""

import asyncio
import os
from sol_trade_sdk import TradeConfig, SwqosConfig, SwqosType, TradingClient
from sol_trade_sdk.address_lookup import (
    fetch_address_lookup_table_account,
    AddressLookupTableCache,
)
from solders.keypair import Keypair
from solders.pubkey import Pubkey


async def main():
    # Create client
    payer = Keypair()
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

    # Example ALT address
    alt_address = Pubkey.from_string("your_alt_address_here")

    # Method 1: Fetch ALT directly
    alt = await fetch_address_lookup_table_account(client.rpc, alt_address)
    print(f"ALT contains {len(alt.addresses)} addresses")

    # Method 2: Use cache for performance
    cache = AddressLookupTableCache(client.rpc)

    # Prefetch multiple ALTs
    alt_addresses = [
        Pubkey.from_string("alt_address_1"),
        Pubkey.from_string("alt_address_2"),
        Pubkey.from_string("alt_address_3"),
    ]
    await cache.prefetch(alt_addresses)

    # Get cached ALT
    cached_alt = cache.get(alt_address)
    if cached_alt:
        print(f"Cached ALT contains {len(cached_alt.addresses)} addresses")

    # Use ALT in trading
    # buy_params = TradeBuyParams(
    #     ...
    #     address_lookup_table_account=alt,
    # )


if __name__ == "__main__":
    asyncio.run(main())
