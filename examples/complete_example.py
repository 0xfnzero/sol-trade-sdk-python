import asyncio

from sol_trade_sdk import DexType, TradeType, recommended_sender_thread_core_indices
from _shared import (
    create_example_client,
    default_swqos_configs,
    describe_dry_run,
    example_buy_params,
    example_sell_params,
    low_latency_gas_strategy,
)


async def main() -> None:
    client = create_example_client(max_swqos_submit_concurrency=8)
    gas_strategy = low_latency_gas_strategy()
    buy_params = example_buy_params(DexType.PUMPFUN)
    sell_params = example_sell_params(DexType.PUMPFUN)

    describe_dry_run("Complete Python SDK example")
    print("Wallet:", client.get_payer())
    print("SWQoS providers:", [cfg.type.value for cfg in default_swqos_configs()])
    print("Recommended sender cores:", recommended_sender_thread_core_indices(3, available_cores=8))
    print("Buy strategy rows:", gas_strategy.get_strategies(TradeType.BUY)[:2])
    print("Buy params:", buy_params.dex_type, buy_params.input_token_amount)
    print("Sell params:", sell_params.dex_type, sell_params.input_token_amount)
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
