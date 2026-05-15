import asyncio

from solana.rpc.async_api import AsyncClient
from sol_trade_sdk import HotPathConfig, HotPathExecutor, TradeType
from _shared import rpc_url


async def main() -> None:
    rpc = AsyncClient(rpc_url())
    config = HotPathConfig(blockhash_refresh_interval=1.5, cache_ttl=4.0, enable_prefetch=True)
    executor = HotPathExecutor(rpc, config=config)

    print("Hot path executor prepared.")
    print("Trade type enum:", TradeType.BUY)
    print("Start executor and prefetch accounts before submitting signed bytes.")
    await rpc.close()


if __name__ == "__main__":
    asyncio.run(main())
