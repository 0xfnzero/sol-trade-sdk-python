"""
Gas Fee Strategy Factory
"""

from .types import GasFeeStrategy


def create_gas_fee_strategy() -> GasFeeStrategy:
    """Create a new gas fee strategy with default values"""
    strategy = GasFeeStrategy()
    strategy.set_global_fee_strategy(
        buy_cu_limit=200000,
        sell_cu_limit=200000,
        buy_cu_price=100000,
        sell_cu_price=100000,
        buy_tip=0.001,
        sell_tip=0.001,
    )
    return strategy
