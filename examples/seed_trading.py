import asyncio

from sol_trade_sdk import DexType
from _shared import create_example_client, describe_dry_run, example_buy_params, example_sell_params


async def main() -> None:
    client = create_example_client(use_seed_optimize=True)
    buy_params = example_buy_params(DexType.PUMPSWAP)
    sell_params = example_sell_params(DexType.PUMPSWAP)

    describe_dry_run("Seed-optimized PumpSwap example")
    print("Wallet:", client.get_payer())
    print("Seed optimization:", client.config.use_seed_optimize)
    print("Prepared params:", buy_params.dex_type, sell_params.dex_type)
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
