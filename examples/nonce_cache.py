import asyncio
import os

from solders.pubkey import Pubkey
from sol_trade_sdk import DexType
from sol_trade_sdk.nonce_cache import fetch_nonce_info
from _shared import create_example_client, describe_dry_run, example_buy_params


async def main() -> None:
    client = create_example_client()
    buy_params = example_buy_params(DexType.PUMPFUN)

    describe_dry_run("Durable nonce example for multi-SWQoS submission")
    if os.getenv("NONCE_ACCOUNT"):
        nonce_account = Pubkey.from_string(os.environ["NONCE_ACCOUNT"])
        nonce = await fetch_nonce_info(client.client, nonce_account)
        if nonce:
            buy_params.recent_blockhash = None
            buy_params.durable_nonce = nonce
            print("Fetched durable nonce:", nonce.nonce_hash)

    print("Wallet:", client.get_payer())
    print("Durable nonce attached:", buy_params.durable_nonce is not None)
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
