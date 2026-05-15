import asyncio

from _shared import RUN_LIVE, create_example_client, describe_dry_run


async def main() -> None:
    client = create_example_client()
    amount_lamports = 1_000_000

    describe_dry_run("WSOL wrap and close example")
    print("Wallet:", client.get_payer())
    print("Wrap amount:", amount_lamports)

    if RUN_LIVE:
        wrap_sig = await client.wrap_sol_to_wsol(amount_lamports)
        print("wrap_sol_to_wsol signature:", wrap_sig)
        close_sig = await client.close_wsol()
        print("close_wsol signature:", close_sig)
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
