import asyncio

from solders.keypair import Keypair
from sol_trade_sdk import TradingClient
from _shared import default_swqos_configs, trade_config


async def main() -> None:
    config = trade_config(
        swqos_configs=default_swqos_configs(),
        max_swqos_submit_concurrency=8,
    )
    client = TradingClient(Keypair(), config)

    print("TradingClient created with current SDK constructor.")
    print("Wallet:", client.get_payer())
    print("SWQoS providers:", [cfg.type.value for cfg in config.swqos_configs])
    print("Sender core order from end:", config.swqos_cores_from_end)
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
