"""
PumpFun trading example.
Demonstrates buy and sell operations on PumpFun DEX.
"""

import asyncio
from sol_trade_sdk import TradingClient, TradeConfig
from sol_trade_sdk.trading.params import PumpFunParams, DexType
from sol_trade_sdk.common.bonding_curve import BondingCurveAccount


async def main():
    # Initialize trading client
    config = (
        TradeConfig.builder("https://api.mainnet-beta.solana.com")
        .swqos_configs([])
        # .mev_protection(True)   # Enable MEV protection (BlockRazor: sandwichMitigation, Astralane: port 9000)
        .build()
    )

    # Create client (simplified - would need actual keypair)
    # payer = Keypair.from_bytes(...)
    # client = await TradingClient.new(payer, config)

    print("PumpFun Trading Example")
    print("=" * 50)

    # Example: Buy tokens on PumpFun
    print("\n1. Buying tokens on PumpFun")
    print("-" * 30)

    # Create bonding curve account from trade data
    bonding_curve = BondingCurveAccount.from_trade(
        bonding_curve=bytes(32),  # Would be actual PDA
        mint=bytes(32),  # Would be actual mint
        creator=bytes(32),
        virtual_token_reserves=1_000_000_000_000,
        virtual_sol_reserves=30_000_000_000,
        real_token_reserves=793_100_000_000_000,
        real_sol_reserves=1_000_000_000,
    )

    # Create PumpFun params
    pumpfun_params = PumpFunParams(
        bonding_curve=bonding_curve,
        associated_bonding_curve=bytes(32),
        creator_vault=bytes(32),
        token_program=bytes(32),  # Token program
    )

    print(f"Bonding Curve: {bonding_curve.account.hex()[:16]}...")
    print(f"Virtual Token Reserves: {bonding_curve.virtual_token_reserves}")
    print(f"Virtual SOL Reserves: {bonding_curve.virtual_sol_reserves}")

    # Calculate buy price
    sol_amount = 1_000_000_000  # 1 SOL
    token_amount = bonding_curve.get_buy_price(sol_amount)
    print(f"\nFor {sol_amount / 1e9} SOL, you get {token_amount} tokens")

    # Example: Sell tokens on PumpFun
    print("\n2. Selling tokens on PumpFun")
    print("-" * 30)

    sell_token_amount = 1_000_000_000  # 1 billion tokens
    sol_received = bonding_curve.get_sell_price(sell_token_amount)
    print(f"For {sell_token_amount} tokens, you get {sol_received / 1e9} SOL")

    # Example: Market cap calculation
    print("\n3. Market Cap Calculation")
    print("-" * 30)
    market_cap = bonding_curve.get_market_cap_sol()
    print(f"Current Market Cap: {market_cap} SOL")

    print("\n" + "=" * 50)
    print("Example completed!")


if __name__ == "__main__":
    asyncio.run(main())
