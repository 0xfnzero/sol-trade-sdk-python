import asyncio

from sol_trade_sdk import DexType
from _shared import RUN_LIVE, create_example_client, describe_dry_run, example_buy_params, log_result


async def main() -> None:
    client = create_example_client(use_pumpfun_v2=True)
    buy_params = example_buy_params(DexType.PUMPFUN)

    describe_dry_run("Complete PumpFun buy flow")
    print("Wallet:", client.get_payer())
    print("PumpFun v2 enabled:", client.config.use_pumpfun_v2)
    print("Cashback flag:", buy_params.extension_params.bonding_curve.is_cashback_coin)

    if RUN_LIVE:
        blockhash = await client.get_latest_blockhash()
        buy_params.recent_blockhash = str(blockhash.blockhash)
        log_result("buy", await client.buy(buy_params))
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
