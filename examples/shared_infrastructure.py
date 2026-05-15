import asyncio

from solders.keypair import Keypair
from sol_trade_sdk import TradingClient
from _shared import trade_config


async def main() -> None:
    shared_config = trade_config(max_swqos_submit_concurrency=8)
    clients = [TradingClient(Keypair(), shared_config) for _ in range(3)]

    print("Shared configuration prepared for multiple wallets.")
    for index, client in enumerate(clients, start=1):
        print(f"Client {index}:", client.get_payer())
        await client.close()
    print("Reuse one TradeConfig/gas strategy, while each client keeps its own signer.")


if __name__ == "__main__":
    asyncio.run(main())
