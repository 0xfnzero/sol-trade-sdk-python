"""Offline API smoke tests; detailed protocol regressions live in focused tests."""

def test_calc_pumpfun():
    """Test PumpFun calculations"""

    # Direct import from calc module (avoiding __init__.py)
    from pumpfun import (
        get_buy_token_amount_from_sol_amount,
        get_sell_sol_amount_from_token_amount,
        calculate_with_slippage_buy,
        calculate_with_slippage_sell,
        FEE_BASIS_POINTS,
        INITIAL_VIRTUAL_TOKEN_RESERVES,
        INITIAL_VIRTUAL_SOL_RESERVES,
    )

    # Verify constants
    assert FEE_BASIS_POINTS == 95
    assert INITIAL_VIRTUAL_TOKEN_RESERVES == 1_073_000_000_000_000
    assert INITIAL_VIRTUAL_SOL_RESERVES == 30_000_000_000

    # Test buy calculation
    creator = bytes(32)
    sol_amount = 1_000_000_000  # 1 SOL
    tokens = get_buy_token_amount_from_sol_amount(
        INITIAL_VIRTUAL_TOKEN_RESERVES,
        INITIAL_VIRTUAL_SOL_RESERVES,
        INITIAL_VIRTUAL_TOKEN_RESERVES - 793_100_000_000_000,
        creator,
        sol_amount,
    )
    assert tokens > 0

    # Test sell calculation
    sol_received = get_sell_sol_amount_from_token_amount(
        INITIAL_VIRTUAL_TOKEN_RESERVES,
        INITIAL_VIRTUAL_SOL_RESERVES,
        creator,
        tokens,
    )
    assert sol_received >= 0

    # Test slippage calculations
    max_cost = calculate_with_slippage_buy(sol_amount, 100)  # 1% slippage
    assert max_cost > sol_amount

    min_out = calculate_with_slippage_sell(tokens, 100)
    assert min_out < tokens


def test_bonding_curve():
    """Test BondingCurveAccount"""

    from sol_trade_sdk.common.bonding_curve import BondingCurveAccount
    from pumpfun import INITIAL_VIRTUAL_TOKEN_RESERVES

    # Create default bonding curve
    bc = BondingCurveAccount.from_dev_trade(bytes(32), bytes(32), 0, 0, bytes(32))
    assert bc.virtual_token_reserves > 0
    assert bc.virtual_sol_reserves > 0
    assert bc.token_total_supply == 1_000_000_000_000_000

    # Test buy price
    sol_amount = 1_000_000_000
    tokens = bc.get_buy_price(sol_amount)
    assert tokens >= 0

    # Test sell price
    sol_out = bc.get_sell_price(tokens)
    assert sol_out >= 0

    # Test market cap
    market_cap = bc.get_market_cap_sol()
    assert market_cap >= 0

    # Test from_dev_trade
    bc2 = BondingCurveAccount.from_dev_trade(
        bonding_curve=bytes(32),
        mint=bytes(32),
        dev_token_amount=1_000_000,
        dev_sol_amount=100_000_000,
        creator=bytes(32),
    )
    assert bc2.virtual_token_reserves < INITIAL_VIRTUAL_TOKEN_RESERVES


def test_middleware():
    """Test middleware system"""

    from traits import MiddlewareManager
    from builtin import LoggingMiddleware

    # Create manager
    manager = MiddlewareManager()
    assert len(manager.middlewares) == 0

    # Add middleware
    manager.add_middleware(LoggingMiddleware())
    assert len(manager.middlewares) == 1

    # Test processing
    instructions = [{"test": "data"}, {"test": "data2"}]
    result = manager.apply_middlewares_process_protocol_instructions(
        instructions, "test_protocol", True
    )
    assert len(result) == 2


def test_trading_params():
    """Test trading parameters"""

    from sol_trade_sdk.trading.params import (
        PumpFunParams,
        PumpSwapParams,
        BonkParams,
        RaydiumCpmmParams,
        RaydiumAmmV4Params,
        MeteoraDammV2Params,
        DexType,
        TradeType,
    )

    # Test PumpFun params
    pumpfun = PumpFunParams()
    assert pumpfun.bonding_curve.virtual_token_reserves == 0

    # Test PumpSwap params
    pumpswap = PumpSwapParams()
    assert pumpswap.pool == bytes(32)

    # Test Bonk params
    bonk = BonkParams()
    assert bonk.virtual_base == 0

    # Test Raydium CPMM params
    raydium_cpmm = RaydiumCpmmParams()
    assert raydium_cpmm.pool_state == bytes(32)

    # Test Raydium AMM V4 params
    raydium_amm = RaydiumAmmV4Params()
    assert raydium_amm.amm == bytes(32)

    # Test Meteora params
    meteora = MeteoraDammV2Params()
    assert meteora.pool == bytes(32)

    # Test enums
    assert DexType.PUMP_FUN.value == "PumpFun"
    assert TradeType.BUY.value == "Buy"


def test_serialization():
    """Test serialization"""

    from serialization import ZeroAllocSerializer

    serializer = ZeroAllocSerializer(buffer_size=1024, pool_size=10)

    # Test buffer acquisition
    buf1 = serializer.acquire_buffer()
    assert len(buf1) == 1024

    buf2 = serializer.acquire_buffer()
    assert len(buf2) == 1024

    # Test buffer release
    serializer.release_buffer(buf1)
    serializer.release_buffer(buf2)

    # Test serialization
    test_data = {"test": "value", "number": 123}
    serialized = serializer.serialize(test_data)
    assert isinstance(serialized, bytes)


def test_compute_budget():
    """Test compute budget manager"""

    from compute_budget_manager import ComputeBudgetManager

    manager = ComputeBudgetManager()

    # Get compute budget instructions
    ixs = manager.get_compute_budget_instructions(cu_limit=100_000, cu_price=10_000)
    assert len(ixs) == 2

    # Verify caching
    ixs2 = manager.get_compute_budget_instructions(cu_limit=100_000, cu_price=10_000)
    assert len(ixs2) == 2

    # Test with tip
    ixs_with_tip = manager.get_compute_budget_instructions_with_tip(
        cu_limit=100_000, cu_price=10_000, tip=1_000_000
    )
    assert len(ixs_with_tip) == 3


def test_hotpath():
    """Test hot path components"""

    from state import HotPathState, AccountStateCache, PoolStateCache
    from executor import HotPathExecutor

    # Create state
    state = HotPathState()
    assert state is not None

    # Create caches
    account_cache = AccountStateCache()
    assert account_cache is not None

    pool_cache = PoolStateCache()
    assert pool_cache is not None

    # Create executor
    executor = HotPathExecutor(state)
    assert executor is not None


def test_execution():
    """Test execution optimizations"""

    from execution import (
        BranchOptimizer,
        Prefetch,
        InstructionProcessor,
    )

    # Test branch optimization
    result = BranchOptimizer.likely(True)
    assert result is True

    result = BranchOptimizer.unlikely(False)
    assert result is False

    # Test prefetch (placeholder)
    instructions = [b"test1", b"test2"]
    Prefetch.instructions(instructions)  # Should not raise

    # Test instruction processor
    processor = InstructionProcessor()
    assert processor is not None
