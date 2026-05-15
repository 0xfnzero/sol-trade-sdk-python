import asyncio
import os

from solders.pubkey import Pubkey
from sol_trade_sdk.address_lookup import AddressLookupTableCache, fetch_address_lookup_table_account
from solana.rpc.async_api import AsyncClient
from _shared import rpc_url


async def main() -> None:
    rpc = AsyncClient(rpc_url())
    cache = AddressLookupTableCache()
    alt_address = Pubkey.from_string(os.environ["ALT_ADDRESS"]) if os.getenv("ALT_ADDRESS") else None

    print("Address Lookup Table example prepared.")
    if not alt_address:
        print("Set ALT_ADDRESS to fetch and cache a real lookup table.")
        await rpc.close()
        return

    direct = await fetch_address_lookup_table_account(rpc, alt_address)
    cached = await cache.get_lookup_table(rpc, alt_address)
    print("Direct ALT size:", len(direct.addresses) if direct else 0)
    print("Cached ALT size:", len(cached.addresses) if cached else 0)
    await rpc.close()


if __name__ == "__main__":
    asyncio.run(main())
