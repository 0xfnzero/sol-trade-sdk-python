import asyncio

from sol_trade_sdk import TradeType
from _shared import low_latency_gas_strategy


async def main() -> None:
    strategy = low_latency_gas_strategy()
    print("Buy strategy rows:", strategy.get_strategies(TradeType.BUY))
    print("Sell strategy rows:", strategy.get_strategies(TradeType.SELL))


if __name__ == "__main__":
    asyncio.run(main())
