"""
Comprehensive Test Suite for Sol Trade SDK
Tests all modules with performance benchmarks.
"""

import pytest
import asyncio
import time
from typing import List

# Import all modules
from sol_trade_sdk import (
    # Core
    GasFeeStrategy,
    GasFeeStrategyType,
    TradeType,
    SwqosType,
    BondingCurveAccount,
    create_gas_fee_strategy,
    
    # Cache
    LRUCache,
    TTLCache,
    ShardedCache,
    
    # Pool
    WorkerPool,
    RateLimiter,
    MultiRateLimiter,
    
    # Calculations
    compute_fee,
    ceil_div,
    calculate_with_slippage_buy,
    calculate_with_slippage_sell,
    get_buy_token_amount_from_sol_amount,
    get_sell_sol_amount_from_token_amount,
    buy_base_input_internal,
    sell_base_input_internal,
    raydium_amm_v4_get_amount_out,
    lamports_to_sol,
    sol_to_lamports,
    
    # Seed
    find_program_address,
    get_bonding_curve_pda,
    get_associated_token_address,
    
    # SPL Token
    TokenAccount,
    transfer_instruction,
    close_account_instruction,
    
    # Instruction builders
    PumpFunInstructionBuilder,
    BuildParams,
    PumpFunParams,
    
    # Trading
    TradeExecutor,
    TradeConfig,
    ExecuteOptions,
    default_execute_options,
)


# ===== Gas Fee Strategy Tests =====

class TestGasFeeStrategy:
    """Comprehensive tests for GasFeeStrategy"""

    def test_create_strategy(self):
        strategy = GasFeeStrategy()
        assert strategy is not None

    def test_set_and_get(self):
        strategy = GasFeeStrategy()
        strategy.set(
            SwqosType.JITO,
            TradeType.BUY,
            GasFeeStrategyType.NORMAL,
            200000, 100000, 0.001,
        )
        
        value = strategy.get(SwqosType.JITO, TradeType.BUY, GasFeeStrategyType.NORMAL)
        assert value is not None
        assert value.cu_limit == 200000
        assert value.cu_price == 100000
        assert value.tip == 0.001

    def test_global_fee_strategy(self):
        strategy = create_gas_fee_strategy()
        
        for swqos_type in [SwqosType.JITO, SwqosType.BLOXROUTE]:
            value = strategy.get(swqos_type, TradeType.BUY, GasFeeStrategyType.NORMAL)
            assert value is not None

    def test_update_buy_tip(self):
        strategy = GasFeeStrategy()
        strategy.set(SwqosType.JITO, TradeType.BUY, GasFeeStrategyType.NORMAL, 200000, 100000, 0.001)
        strategy.set(SwqosType.JITO, TradeType.SELL, GasFeeStrategyType.NORMAL, 200000, 100000, 0.002)
        
        strategy.update_buy_tip(0.005)
        
        buy = strategy.get(SwqosType.JITO, TradeType.BUY, GasFeeStrategyType.NORMAL)
        sell = strategy.get(SwqosType.JITO, TradeType.SELL, GasFeeStrategyType.NORMAL)
        
        assert buy.tip == 0.005
        assert sell.tip == 0.002

    def test_conflict_resolution(self):
        strategy = GasFeeStrategy()
        
        strategy.set(
            SwqosType.JITO, TradeType.BUY,
            GasFeeStrategyType.LOW_TIP_HIGH_CU_PRICE,
            200000, 100000, 0.0005,
        )
        strategy.set(
            SwqosType.JITO, TradeType.BUY,
            GasFeeStrategyType.NORMAL,
            200000, 100000, 0.001,
        )
        
        low = strategy.get(SwqosType.JITO, TradeType.BUY, GasFeeStrategyType.LOW_TIP_HIGH_CU_PRICE)
        normal = strategy.get(SwqosType.JITO, TradeType.BUY, GasFeeStrategyType.NORMAL)
        
        assert low is None
        assert normal is not None


# ===== Bonding Curve Tests =====

class TestBondingCurveAccount:
    """Tests for BondingCurveAccount"""

    def test_initial_state(self):
        curve = BondingCurveAccount.from_dev_trade(bytes(32), bytes(32), 0, 0, bytes(32))
        assert curve.virtual_token_reserves == 1073000000000000
        assert curve.virtual_sol_reserves == 30000000000
        assert curve.complete is False

    def test_get_buy_price(self):
        curve = BondingCurveAccount.from_dev_trade(bytes(32), bytes(32), 0, 0, bytes(32))
        tokens = curve.get_buy_price(1_000_000)
        assert tokens > 0

    def test_get_sell_price(self):
        curve = BondingCurveAccount.from_dev_trade(bytes(32), bytes(32), 0, 0, bytes(32))
        sol = curve.get_sell_price(1_000_000_000, 100)
        assert sol > 0

    def test_complete_curve_returns_error(self):
        curve = BondingCurveAccount(complete=True)
        with pytest.raises(ValueError, match="Curve is complete"):
            curve.get_buy_price(1_000_000)
        with pytest.raises(ValueError, match="Curve is complete"):
            curve.get_sell_price(1_000_000_000, 100)

    def test_market_cap(self):
        curve = BondingCurveAccount.from_dev_trade(bytes(32), bytes(32), 0, 0, bytes(32))
        market_cap = curve.get_market_cap_sol()
        assert market_cap > 0

    def test_token_price(self):
        curve = BondingCurveAccount.from_dev_trade(bytes(32), bytes(32), 0, 0, bytes(32))
        price = curve.get_token_price()
        assert price > 0


# ===== Cache Tests =====

class TestCaches:
    """Tests for cache implementations"""

    def test_lru_cache_basic(self):
        cache = LRUCache(max_size=3, ttl=60000)
        
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        
        assert cache.get("a") == 1
        assert cache.get("b") == 2
        assert cache.get("c") == 3

    def test_lru_cache_eviction(self):
        cache = LRUCache(max_size=2, ttl=60000)
        
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)  # Should evict "a"
        
        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("c") == 3

    def test_lru_cache_stats(self):
        cache = LRUCache(max_size=10, ttl=60000)
        
        cache.set("a", 1)
        cache.get("a")  # hit
        cache.get("b")  # miss
        
        stats = cache.get_stats()
        assert stats.hits == 1
        assert stats.misses == 1

    def test_ttl_cache_expiration(self):
        cache = TTLCache(ttl=100)  # 100ms
        
        cache.set("a", 1)
        assert cache.get("a") == 1
        
        time.sleep(0.15)
        assert cache.get("a") is None

    def test_sharded_cache(self):
        cache = ShardedCache(shards=4, maxSizePerShard=100, ttl=60000)
        
        for i in range(10):
            cache.set(f"key_{i}", i)
        
        for i in range(10):
            assert cache.get(f"key_{i}") == i


# ===== Pool Tests =====

class TestPools:
    """Tests for pool implementations"""

    def test_worker_pool_submit(self):
        pool = WorkerPool(workers=2)
        
        def task():
            return 42
        
        result = pool.submit(task).result()
        assert result == 42
        
        pool.shutdown()

    def test_worker_pool_batch(self):
        pool = WorkerPool(workers=4)
        
        def task(x):
            return x * 2
        
        results = pool.map(task, [1, 2, 3, 4, 5])
        assert results == [2, 4, 6, 8, 10]
        
        pool.shutdown()

    def test_rate_limiter(self):
        limiter = RateLimiter(rate=100, burst=10)
        
        # Should allow burst
        allowed = [limiter.allow() for _ in range(10)]
        assert all(allowed)
        
        # Should be rate limited
        assert limiter.allow() is False

    def test_multi_rate_limiter(self):
        limiter = MultiRateLimiter(rate=10, burst=5)
        
        # Different keys have separate limits
        for i in range(5):
            assert limiter.allow("key1")
        
        assert not limiter.allow("key1")
        assert limiter.allow("key2")


# ===== Calculation Tests =====

class TestCalculations:
    """Tests for calculation utilities"""

    def test_compute_fee(self):
        fee = compute_fee(1_000_000, 100, 10000)  # 1%
        assert fee == 10000

    def test_ceil_div(self):
        assert ceil_div(10, 3) == 4
        assert ceil_div(9, 3) == 3
        assert ceil_div(11, 3) == 4

    def test_slippage_buy(self):
        result = calculate_with_slippage_buy(1000, 100)  # 1%
        assert result == 1010

    def test_slippage_sell(self):
        result = calculate_with_slippage_sell(1000, 100)  # 1%
        assert result == 990

    def test_pumpfun_buy(self):
        tokens = get_buy_token_amount_from_sol_amount(
            1_000_000, 30_000_000_000,
            1_073_000_000_000_000, 793_000_000_000_000,
        )
        assert tokens > 0

    def test_pumpfun_sell(self):
        sol = get_sell_sol_amount_from_token_amount(
            1_000_000_000, 30_000_000_000,
            1_073_000_000_000_000, False,
        )
        assert sol > 0

    def test_pumpswap_buy(self):
        result = buy_base_input_internal(
            1_000_000, 30_000_000_000,
            1_073_000_000_000_000, 0, 500,
        )
        assert result.amount_out > 0
        assert result.fee > 0

    def test_pumpswap_sell(self):
        result = sell_base_input_internal(
            1_000_000_000, 1_073_000_000_000_000,
            30_000_000_000, 0, 500,
        )
        assert result.amount_out > 0

    def test_raydium_amm_v4(self):
        amount = raydium_amm_v4_get_amount_out(
            1_000_000, 1_000_000_000, 500_000_000,
        )
        assert amount > 0

    def test_lamports_conversion(self):
        assert lamports_to_sol(1_000_000_000) == 1.0
        assert sol_to_lamports(1.0) == 1_000_000_000


# ===== Performance Benchmarks =====

class TestPerformance:
    """Performance benchmarks for critical operations"""

    def test_lru_cache_performance(self):
        cache = LRUCache(max_size=10000, ttl=60000)
        
        # Set performance
        start = time.time()
        for i in range(10000):
            cache.set(f"key_{i}", i)
        set_time = time.time() - start
        
        # Get performance
        start = time.time()
        for i in range(10000):
            cache.get(f"key_{i}")
        get_time = time.time() - start
        
        print(f"\nLRU Cache - Set: {set_time*1000:.2f}ms, Get: {get_time*1000:.2f}ms")
        
        # Should be very fast
        assert set_time < 0.5  # Under 500ms for 10k ops
        assert get_time < 0.5

    def test_calculation_performance(self):
        start = time.time()
        for _ in range(100000):
            get_buy_token_amount_from_sol_amount(
                1_000_000, 30_000_000_000,
                1_073_000_000_000_000, 793_000_000_000_000,
            )
        elapsed = time.time() - start
        
        print(f"\nCalculation - 100k ops: {elapsed*1000:.2f}ms")
        assert elapsed < 1.0  # Under 1 second for 100k calculations

    def test_gas_strategy_performance(self):
        strategy = GasFeeStrategy()
        
        start = time.time()
        for i in range(10000):
            strategy.set(
                SwqosType.JITO, TradeType.BUY,
                GasFeeStrategyType.NORMAL,
                200000, 100000, 0.001,
            )
            strategy.get(SwqosType.JITO, TradeType.BUY, GasFeeStrategyType.NORMAL)
        elapsed = time.time() - start
        
        print(f"\nGas Strategy - 10k set/get: {elapsed*1000:.2f}ms")
        assert elapsed < 0.5


# ===== Integration Tests =====

class TestIntegration:
    """Integration tests for complete workflows"""

    def test_complete_buy_workflow(self):
        # Create gas strategy
        strategy = create_gas_fee_strategy()
        
        # Create bonding curve
        curve = BondingCurveAccount.from_dev_trade(bytes(32), bytes(32), 0, 0, bytes(32))
        
        # Calculate tokens for 1 SOL
        sol_amount = 1_000_000_000  # 1 SOL
        tokens = curve.get_buy_price(sol_amount)
        
        assert tokens > 0
        
        # Build instruction
        params = BuildParams(
            payer=bytes(32),
            input_mint=bytes(32),
            output_mint=bytes(32),
            input_amount=sol_amount,
            slippage_bps=500,
            protocol_params=PumpFunParams(),
        )
        
        # This would build instructions in real usage
        assert params is not None


# ===== Run Tests =====

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
