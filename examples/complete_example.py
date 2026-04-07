"""
Complete Trading Example for Sol Trade SDK
Demonstrates all features with performance optimizations.
"""

import asyncio
from typing import Optional

from sol_trade_sdk import (
    # Core types
    GasFeeStrategy,
    GasFeeStrategyType,
    TradeType,
    SwqosType,
    BondingCurveAccount,
    create_gas_fee_strategy,
    
    # Cache
    LRUCache,
    ShardedCache,
    
    # Pool
    WorkerPool,
    RateLimiter,
    
    # RPC
    AsyncRPCClient,
    RPCConfig,
    RPCError,
    
    # Calculations
    get_buy_token_amount_from_sol_amount,
    get_sell_sol_amount_from_token_amount,
    lamports_to_sol,
    sol_to_lamports,
    
    # Seed
    get_bonding_curve_pda,
    get_associated_token_address,
    
    # SPL Token
    transfer_instruction,
    wrap_sol_instructions,
    unwrap_sol_instructions,
    WSOL_MINT,
    
    # Instruction builders
    PumpFunInstructionBuilder,
    BuildParams,
    PumpFunParams,
    
    # SWQOS
    create_swqos_client,
    JitoClient,
    
    # Trading
    TradeExecutor,
    TradeConfig,
    ExecuteOptions,
    SwqosConfig,
)


async def main():
    """Main example demonstrating SDK usage"""
    
    print("=" * 60)
    print("Sol Trade SDK - Complete Example")
    print("=" * 60)
    
    # ===== Configuration =====
    
    RPC_URL = "https://api.mainnet-beta.solana.com"
    JITO_AUTH_TOKEN = "your-jito-auth-token"  # Replace with actual token
    
    # ===== Create Gas Fee Strategy =====
    
    print("\n1. Creating Gas Fee Strategy...")
    gas_strategy = create_gas_fee_strategy()
    
    # Customize for aggressive buy
    gas_strategy.set(
        SwqosType.JITO,
        TradeType.BUY,
        GasFeeStrategyType.HIGH_TIP_LOW_CU_PRICE,
        cu_limit=200000,
        cu_price=1000000,  # Higher priority
        tip=0.01,  # 0.01 SOL tip
    )
    
    print(f"   - Buy gas config: {gas_strategy.get(SwqosType.JITO, TradeType.BUY, GasFeeStrategyType.NORMAL)}")
    
    # ===== Create Caches =====
    
    print("\n2. Setting up caches...")
    
    # LRU cache for account data
    account_cache = ShardedCache[str, bytes](
        shards=16,
        max_size_per_shard=500,
        ttl=10.0,  # 10 seconds
    )
    
    # Cache for blockhashes
    from sol_trade_sdk import TTLCache
    blockhash_cache = TTLCache[str, str](ttl=2.0)
    
    print("   - Account cache: ShardedCache(16 shards, 500 each)")
    print("   - Blockhash cache: TTLCache(2s TTL)")
    
    # ===== Create RPC Client =====
    
    print("\n3. Creating RPC client...")
    
    rpc_config = RPCConfig(
        endpoint=RPC_URL,
        timeout=30.0,
        max_retries=3,
        max_connections=100,
    )
    
    rpc_client = AsyncRPCClient(rpc_config)
    
    try:
        # Get latest blockhash
        blockhash = await rpc_client.get_latest_blockhash()
        print(f"   - Latest blockhash: {blockhash.blockhash[:20]}...")
        blockhash_cache.set("latest", blockhash.blockhash)
        
        # Check balance (example - replace with actual pubkey)
        # balance = await rpc_client.get_balance("YourPubkeyHere")
        # print(f"   - Balance: {lamports_to_sol(balance)} SOL")
        
    except RPCError as e:
        print(f"   - RPC Error: {e}")
    finally:
        await rpc_client.close()
    
    # ===== Create SWQOS Clients =====
    
    print("\n4. Creating SWQOS clients...")
    
    jito_client = create_swqos_client(
        swqos_type=SwqosType.JITO,
        rpc_url=RPC_URL,
        auth_token=JITO_AUTH_TOKEN,
        region="amsterdam",
    )
    
    print(f"   - Jito client created")
    print(f"   - Tip account: {jito_client.get_tip_account()}")
    print(f"   - Min tip: {jito_client.min_tip_sol()} SOL")
    
    # ===== Bonding Curve Calculations =====
    
    print("\n5. Bonding curve calculations...")
    
    curve = BondingCurveAccount()
    
    # Calculate tokens for 1 SOL buy
    sol_amount = sol_to_lamports(1.0)
    tokens = curve.get_buy_price(sol_amount)
    print(f"   - 1 SOL buys: {tokens:,.0f} tokens")
    
    # Calculate SOL for 1B tokens sell
    token_amount = 1_000_000_000
    sol_out = curve.get_sell_price(token_amount, 100)
    print(f"   - 1B tokens sells for: {lamports_to_sol(sol_out):.6f} SOL")
    
    # Market cap
    market_cap = curve.get_market_cap_sol()
    print(f"   - Market cap: {lamports_to_sol(market_cap):,.2f} SOL")
    
    # Token price
    price = curve.get_token_price()
    print(f"   - Token price: {price:.10f} SOL")
    
    # ===== PDA Derivations =====
    
    print("\n6. PDA derivations...")
    
    mint = "ExampleMintAddressHere"  # Replace with actual mint
    
    try:
        bonding_curve_pda = get_bonding_curve_pda(mint)
        print(f"   - Bonding curve PDA bump: {bonding_curve_pda.bump}")
        
        ata = get_associated_token_address(
            wallet="ExampleWalletAddress",
            mint=mint,
        )
        print(f"   - ATA: {ata.hex()[:20]}...")
    except Exception as e:
        print(f"   - PDA derivation requires valid addresses: {e}")
    
    # ===== Instruction Building =====
    
    print("\n7. Instruction building...")
    
    # Create build params for a buy
    params = BuildParams(
        payer=bytes(32),  # Replace with actual payer
        input_mint=bytes(32),  # WSOL mint
        output_mint=bytes(32),  # Token mint
        input_amount=sol_to_lamports(0.1),  # 0.1 SOL
        slippage_bps=500,  # 5% slippage
        protocol_params=PumpFunParams(
            is_mayhem_mode=False,
            is_cashback_coin=False,
        ),
    )
    
    print(f"   - Build params created")
    print(f"   - Input amount: {lamports_to_sol(params.input_amount)} SOL")
    print(f"   - Slippage: {params.slippage_bps / 100}%")
    
    # ===== Create Trade Executor =====
    
    print("\n8. Creating trade executor...")
    
    trade_config = (
        TradeConfig.builder(RPC_URL)
        .swqos_configs([
            SwqosConfig(type=SwqosType.JITO, api_key=JITO_AUTH_TOKEN),
        ])
        .gas_fee_strategy(gas_strategy)
        .max_workers(10)
        .rate_limit_per_second(100.0)
        # .mev_protection(True)   # Enable MEV protection (BlockRazor: sandwichMitigation, Astralane: port 9000)
        .build()
    )
    
    executor = TradeExecutor(trade_config)
    
    print(f"   - Executor created with {len(executor._clients)} SWQOS clients")
    
    # ===== Rate Limiting =====
    
    print("\n9. Rate limiting example...")
    
    limiter = RateLimiter(rate=10, burst=5)
    
    # Burst of requests
    allowed = 0
    for _ in range(10):
        if limiter.allow():
            allowed += 1
    
    print(f"   - Allowed {allowed}/10 requests (burst)")
    
    # ===== Worker Pool =====
    
    print("\n10. Worker pool example...")
    
    pool = WorkerPool(workers=4, queue_size=100)
    
    def task(n):
        return n * 2
    
    results = pool.map(task, [1, 2, 3, 4, 5])
    print(f"   - Pool results: {results}")
    
    pool.shutdown()
    
    # ===== Metrics =====
    
    print("\n11. Executor metrics...")
    
    metrics = executor.get_metrics()
    print(f"   - Total trades: {metrics['total_trades']}")
    print(f"   - Success rate: {metrics['success_rate'] * 100:.1f}%")
    print(f"   - Avg latency: {metrics['avg_latency_ms']:.2f}ms")
    
    # ===== Cleanup =====
    
    print("\n12. Cleanup...")
    
    executor.close()
    print("   - Executor closed")
    
    print("\n" + "=" * 60)
    print("Example completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
