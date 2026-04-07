"""
WSOL Wrapper Example

This example demonstrates how to:
1. Wrap SOL to WSOL
2. Partially unwrap WSOL back to SOL using seed account
3. Close WSOL account and unwrap remaining balance
"""

import asyncio
import os
from sol_trade_sdk import (
    TradeConfig,
    SwqosConfig,
    SwqosType,
    TradingClient,
)
from solders.keypair import Keypair


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


async def main():
    print("WSOL Wrapper Example")
    print("This example demonstrates:")
    print("1. Wrapping SOL to WSOL")
    print("2. Partial unwrapping WSOL back to SOL")
    print("3. Closing WSOL account and unwrapping remaining balance")

    # Initialize client
    client = await create_client()
    print(f"\nClient created: {client.payer_pubkey}")

    # Example 1: Wrap SOL to WSOL
    print("\n--- Example 1: Wrapping SOL to WSOL ---")
    wrap_amount = 1_000_000  # 0.001 SOL in lamports
    print(f"Wrapping {wrap_amount} lamports (0.001 SOL) to WSOL...")

    try:
        signature = await client.wrap_sol_to_wsol(wrap_amount)
        print(f"Successfully wrapped SOL to WSOL!")
        print(f"Transaction signature: {signature}")
        print(f"Explorer: https://solscan.io/tx/{signature}")
    except Exception as e:
        print(f"Failed to wrap SOL to WSOL: {e}")
        return

    # Wait before partial unwrapping
    print("\nWaiting 3 seconds before partial unwrapping...")
    await asyncio.sleep(3)

    # Example 2: Unwrap half of the WSOL back to SOL using seed account
    print("\n--- Example 2: Unwrapping half of WSOL back to SOL ---")
    unwrap_amount = wrap_amount // 2  # Half of the wrapped amount
    print(f"Unwrapping {unwrap_amount} lamports (0.0005 SOL) back to SOL...")

    try:
        signature = await client.wrap_wsol_to_sol(unwrap_amount)
        print(f"Successfully unwrapped half of WSOL back to SOL!")
        print(f"Transaction signature: {signature}")
        print(f"Explorer: https://solscan.io/tx/{signature}")
    except Exception as e:
        print(f"Failed to unwrap WSOL to SOL: {e}")

    # Wait before final unwrapping
    print("\nWaiting 3 seconds before final unwrapping...")
    await asyncio.sleep(3)

    # Example 3: Close WSOL account and unwrap all remaining balance
    print("\n--- Example 3: Closing WSOL account ---")
    print("Closing WSOL account and unwrapping all remaining balance to SOL...")

    try:
        signature = await client.close_wsol()
        print(f"Successfully closed WSOL account and unwrapped remaining balance!")
        print(f"Transaction signature: {signature}")
        print(f"Explorer: https://solscan.io/tx/{signature}")
    except Exception as e:
        print(f"Failed to close WSOL account: {e}")

    print("\nWSOL Wrapper example completed!")


if __name__ == "__main__":
    asyncio.run(main())
