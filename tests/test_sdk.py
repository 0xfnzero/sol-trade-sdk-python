"""
Tests for Sol Trade SDK - Python
"""

import asyncio
import pytest
from sol_trade_sdk.common.types import (
    GasFeeStrategy,
    GasFeeStrategyType,
    TradeType,
    SwqosType,
    BondingCurveAccount,
    NonceCache,
    DurableNonceInfo,
)
from sol_trade_sdk.common.gas_fee_strategy import create_gas_fee_strategy
from sol_trade_sdk import calc
from sol_trade_sdk import (
    TradeConfig as RootTradeConfig,
    SwqosConfig as RootSwqosConfig,
    SwqosRegion as RootSwqosRegion,
    SwqosType as RootSwqosType,
    create_trade_config,
)
from sol_trade_sdk.trading.executor import (
    TradeConfig as ExecutorTradeConfig,
    TradeExecutor,
)
from sol_trade_sdk.trading.core.async_executor import (
    AsyncTradeExecutor,
    ExecutionConfig,
    SubmitMode,
)
from sol_trade_sdk.swqos.providers import (
    SwqosConfig as ProviderSwqosConfig,
    SwqosManager,
    SwqosType as ProviderSwqosType,
    TransactionResult,
)


class _FakeSwqosClient:
    def __init__(self, signature: str, delay: float, fail: bool = False):
        self.signature = signature
        self.delay = delay
        self.fail = fail

    async def send_transaction(self, trade_type, transaction, wait_confirmation):
        await asyncio.sleep(self.delay)
        if self.fail:
            raise RuntimeError("submit failed")
        return self.signature


class _FakeProviderClient:
    def __init__(self, swqos_type: ProviderSwqosType, signature: str, delay: float = 0.0):
        self.config = ProviderSwqosConfig(swqos_type=swqos_type)
        self.signature = signature
        self.delay = delay
        self.calls = 0

    async def submit_transaction(self, transaction: bytes, tip: int = 0):
        self.calls += 1
        await asyncio.sleep(self.delay)
        return TransactionResult(
            success=True,
            signature=self.signature,
            provider=self.config.swqos_type.value,
        )


class TestGasFeeStrategy:
    """Tests for GasFeeStrategy class"""

    def test_create_strategy(self):
        """Test creating a gas fee strategy"""
        strategy = GasFeeStrategy()
        assert strategy is not None

    def test_set_and_get(self):
        """Test setting and getting gas fee strategies"""
        strategy = GasFeeStrategy()
        strategy.set(
            SwqosType.JITO,
            TradeType.BUY,
            GasFeeStrategyType.NORMAL,
            200000,
            100000,
            0.001,
        )

        value = strategy.get(SwqosType.JITO, TradeType.BUY, GasFeeStrategyType.NORMAL)
        assert value is not None
        assert value.cu_limit == 200000
        assert value.cu_price == 100000
        assert value.tip == 0.001

    def test_global_fee_strategy(self):
        """Test setting global fee strategy"""
        strategy = create_gas_fee_strategy()
        
        # Check that all SWQOS types have strategies set
        for swqos_type in [SwqosType.JITO, SwqosType.BLOXROUTE, SwqosType.ZERO_SLOT]:
            value = strategy.get(swqos_type, TradeType.BUY, GasFeeStrategyType.NORMAL)
            assert value is not None

    def test_update_buy_tip(self):
        """Test updating buy tip for all strategies"""
        strategy = GasFeeStrategy()
        strategy.set(SwqosType.JITO, TradeType.BUY, GasFeeStrategyType.NORMAL, 200000, 100000, 0.001)
        strategy.set(SwqosType.JITO, TradeType.SELL, GasFeeStrategyType.NORMAL, 200000, 100000, 0.002)

        strategy.update_buy_tip(0.005)

        buy_value = strategy.get(SwqosType.JITO, TradeType.BUY, GasFeeStrategyType.NORMAL)
        sell_value = strategy.get(SwqosType.JITO, TradeType.SELL, GasFeeStrategyType.NORMAL)

        assert buy_value.tip == 0.005
        assert sell_value.tip == 0.002

    def test_delete(self):
        """Test deleting strategies"""
        strategy = GasFeeStrategy()
        strategy.set(SwqosType.JITO, TradeType.BUY, GasFeeStrategyType.NORMAL, 200000, 100000, 0.001)

        strategy.delete(SwqosType.JITO, TradeType.BUY, GasFeeStrategyType.NORMAL)

        value = strategy.get(SwqosType.JITO, TradeType.BUY, GasFeeStrategyType.NORMAL)
        assert value is None

    def test_conflict_resolution(self):
        """Test that Normal strategy removes high/low variants"""
        strategy = GasFeeStrategy()
        
        # Set high/low strategies first
        strategy.set(
            SwqosType.JITO, TradeType.BUY, GasFeeStrategyType.LOW_TIP_HIGH_CU_PRICE,
            200000, 100000, 0.0005
        )
        strategy.set(
            SwqosType.JITO, TradeType.BUY, GasFeeStrategyType.HIGH_TIP_LOW_CU_PRICE,
            200000, 100000, 0.002
        )

        # Set Normal strategy (should remove high/low)
        strategy.set(
            SwqosType.JITO, TradeType.BUY, GasFeeStrategyType.NORMAL,
            200000, 100000, 0.001
        )

        # Check that high/low are gone
        low = strategy.get(SwqosType.JITO, TradeType.BUY, GasFeeStrategyType.LOW_TIP_HIGH_CU_PRICE)
        high = strategy.get(SwqosType.JITO, TradeType.BUY, GasFeeStrategyType.HIGH_TIP_LOW_CU_PRICE)
        normal = strategy.get(SwqosType.JITO, TradeType.BUY, GasFeeStrategyType.NORMAL)

        assert low is None
        assert high is None
        assert normal is not None


class TestTradeConfig:
    """Tests for trade configuration normalization"""

    def test_adds_default_rpc_when_swqos_configured(self):
        cfg = create_trade_config(
            "https://x",
            [
                RootSwqosConfig(
                    type=RootSwqosType.JITO,
                    region=RootSwqosRegion.FRANKFURT,
                    api_key="uuid",
                )
            ],
        )

        assert [c.type for c in cfg.swqos_configs] == [
            RootSwqosType.JITO,
            RootSwqosType.DEFAULT,
        ]

    def test_does_not_add_default_rpc_when_no_swqos_configured(self):
        cfg = RootTradeConfig(rpc_url="https://x")
        assert cfg.swqos_configs == []


class TestParallelExecutor:
    """Tests for first-success parallel submit behavior"""

    @pytest.mark.asyncio
    async def test_parallel_submit_waits_past_first_failure(self):
        executor = TradeExecutor(ExecutorTradeConfig(rpc_url="https://x"))
        executor._clients = {
            SwqosType.JITO: _FakeSwqosClient("", 0.001, fail=True),
            SwqosType.BLOXROUTE: _FakeSwqosClient("sig-ok", 0.01),
        }

        results = await executor.execute_parallel(
            TradeType.BUY,
            [b"tx"],
            wait_confirmation=False,
        )

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].signature == "sig-ok"

    @pytest.mark.asyncio
    async def test_parallel_submit_keeps_one_result_per_transaction(self):
        executor = TradeExecutor(ExecutorTradeConfig(rpc_url="https://x"))
        executor._clients = {
            SwqosType.JITO: _FakeSwqosClient("sig-ok", 0.001),
        }

        results = await executor.execute_parallel(
            TradeType.BUY,
            [b"tx1", b"tx2"],
            wait_confirmation=False,
        )

        assert len(results) == 2
        assert all(result.success for result in results)

    @pytest.mark.asyncio
    async def test_core_parallel_executor_submits_all_providers(self):
        manager = SwqosManager()
        clients = [
            _FakeProviderClient(ProviderSwqosType.JITO, "sig-jito", 0.001),
            _FakeProviderClient(ProviderSwqosType.BLOXROUTE, "sig-blox", 0.01),
            _FakeProviderClient(ProviderSwqosType.HELIUS, "sig-helius", 0.01),
            _FakeProviderClient(ProviderSwqosType.DEFAULT, "sig-default", 0.01),
        ]
        for client in clients:
            manager.add_client(client)

        executor = AsyncTradeExecutor(manager)
        result = await executor.execute(
            b"tx",
            ExecutionConfig(
                submit_mode=SubmitMode.PARALLEL,
                parallel_submit_count=1,
                timeout_ms=1000,
            ),
        )
        await asyncio.sleep(0.03)

        assert result.success is True
        assert all(client.calls == 1 for client in clients)


class TestBondingCurveAccount:
    """Tests for BondingCurveAccount class"""

    def test_initial_state(self):
        """Test initial bonding curve state"""
        curve = BondingCurveAccount()
        
        assert curve.virtual_token_reserves == 1073000000000000
        assert curve.virtual_sol_reserves == 30000000000
        assert curve.real_token_reserves == 793000000000000
        assert curve.complete is False

    def test_get_buy_price(self):
        """Test calculating buy price"""
        curve = BondingCurveAccount()
        
        # Buy with 0.001 SOL (1_000_000 lamports)
        tokens = curve.get_buy_price(1_000_000)
        assert tokens > 0

    def test_get_sell_price(self):
        """Test calculating sell price"""
        curve = BondingCurveAccount()
        
        # Sell some tokens
        sol = curve.get_sell_price(1_000_000_000)  # 1 million tokens
        assert sol > 0

    def test_get_market_cap_sol(self):
        """Test calculating market cap"""
        curve = BondingCurveAccount()
        
        market_cap = curve.get_market_cap_sol()
        assert market_cap > 0

    def test_get_token_price(self):
        """Test calculating token price"""
        curve = BondingCurveAccount()
        
        price = curve.get_token_price()
        assert price > 0

    def test_complete_curve_returns_zero(self):
        """Test that complete curves return zero for buy/sell"""
        curve = BondingCurveAccount(complete=True)
        
        assert curve.get_buy_price(1_000_000) == 0
        assert curve.get_sell_price(1_000_000) == 0


class TestNonceCache:
    """Tests for NonceCache class"""

    def test_set_and_get(self):
        """Test setting and getting nonce info"""
        cache = NonceCache()
        
        pubkey = b"test_pubkey_32_bytes_long_enough_xx"
        info = DurableNonceInfo(
            nonce_account=b"nonce_account_32_bytes_long_enough",
            authority=b"authority_32_bytes_long_enough_xx",
            nonce_hash=b"hash_32_bytes_long_enough_for_hash!",
            recent_blockhash=b"blockhash_32_bytes_long_enough!",
        )
        
        cache.set(pubkey, info)
        result = cache.get(pubkey)
        
        assert result is not None
        assert result.nonce_account == info.nonce_account

    def test_delete(self):
        """Test deleting nonce info"""
        cache = NonceCache()
        
        pubkey = b"test_pubkey_32_bytes_long_enough_xx"
        info = DurableNonceInfo(
            nonce_account=b"nonce_account_32_bytes_long_enough",
            authority=b"authority_32_bytes_long_enough_xx",
            nonce_hash=b"hash_32_bytes_long_enough_for_hash!",
            recent_blockhash=b"blockhash_32_bytes_long_enough!",
        )
        
        cache.set(pubkey, info)
        cache.delete(pubkey)
        
        result = cache.get(pubkey)
        assert result is None


class TestCalculations:
    """Tests for calculation utilities"""

    def test_compute_fee(self):
        """Test fee calculation"""
        fee = calc.compute_fee(1_000_000, 100, 10000)  # 1%
        assert fee == 10000

    def test_ceil_div(self):
        """Test ceiling division"""
        assert calc.ceil_div(10, 3) == 4
        assert calc.ceil_div(9, 3) == 3
        assert calc.ceil_div(11, 3) == 4

    def test_calculate_with_slippage_buy(self):
        """Test slippage calculation for buy"""
        result = calc.calculate_with_slippage_buy(1000, 100)  # 1% slippage
        assert result == 1010

    def test_calculate_with_slippage_sell(self):
        """Test slippage calculation for sell"""
        result = calc.calculate_with_slippage_sell(1000, 100)  # 1% slippage
        assert result == 990

    def test_get_buy_token_amount_from_sol_amount(self):
        """Test PumpFun buy calculation"""
        tokens = calc.get_buy_token_amount_from_sol_amount(
            sol_amount=1_000_000,
            virtual_sol_reserves=30_000_000_000,
            virtual_token_reserves=1_073_000_000_000_000,
            real_token_reserves=793_000_000_000_000,
        )
        assert tokens > 0

    def test_get_sell_sol_amount_from_token_amount(self):
        """Test PumpFun sell calculation"""
        sol = calc.get_sell_sol_amount_from_token_amount(
            token_amount=1_000_000_000,
            virtual_sol_reserves=30_000_000_000,
            virtual_token_reserves=1_073_000_000_000_000,
            real_sol_reserves=1_000_000_000,
        )
        assert sol > 0

    def test_buy_base_input_internal(self):
        """Test PumpSwap buy calculation"""
        result = calc.buy_base_input_internal(
            amount_in=1_000_000,
            reserve_in=30_000_000_000,
            reserve_out=1_073_000_000_000_000,
            slippage_bps=500,
        )
        assert result.amount_out > 0
        assert result.fee > 0

    def test_sell_base_input_internal(self):
        """Test PumpSwap sell calculation"""
        result = calc.sell_base_input_internal(
            amount_in=1_000_000_000,
            reserve_in=1_073_000_000_000_000,
            reserve_out=30_000_000_000,
            slippage_bps=500,
        )
        assert result.amount_out > 0
        assert result.fee > 0

    def test_raydium_amm_v4_calculations(self):
        """Test Raydium AMM V4 calculations"""
        amount_out = calc.raydium_amm_v4_get_amount_out(
            amount_in=1_000_000,
            reserve_in=1_000_000_000,
            reserve_out=500_000_000,
        )
        assert amount_out > 0

    def test_raydium_cpmm_calculations(self):
        """Test Raydium CPMM calculations"""
        amount_out = calc.raydium_cpmm_get_amount_out(
            amount_in=1_000_000,
            reserve_in=1_000_000_000,
            reserve_out=500_000_000,
        )
        assert amount_out > 0

    def test_bonk_calculations(self):
        """Test Bonk calculations"""
        amount_out = calc.get_bonk_amount_out(
            amount_in=1_000_000,
            reserve_in=1_000_000_000,
            reserve_out=500_000_000,
        )
        assert amount_out > 0

    def test_lamports_conversions(self):
        """Test lamports to SOL conversions"""
        assert calc.lamports_to_sol(1_000_000_000) == 1.0
        assert calc.sol_to_lamports(1.0) == 1_000_000_000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
