import asyncio

from sol_trade_sdk import DexType
from _shared import RUN_LIVE, create_example_client, describe_dry_run, example_buy_params, example_sell_params, log_result


async def main() -> None:
    client = create_example_client()
    buy_params = example_buy_params(DexType.PUMPSWAP)
    sell_params = example_sell_params(DexType.PUMPSWAP)

    describe_dry_run("PumpSwap direct trading example with current pool params")
    print("Wallet:", client.get_payer())
    print("Buy params:", buy_params.dex_type, buy_params.input_token_amount)
    print("Sell params:", sell_params.dex_type, sell_params.input_token_amount)

    if RUN_LIVE:
        blockhash = await client.get_latest_blockhash()
        buy_params.recent_blockhash = str(blockhash.blockhash)
        sell_params.recent_blockhash = str(blockhash.blockhash)
        log_result("buy", await client.buy(buy_params))
        log_result("sell", await client.sell(sell_params))
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
