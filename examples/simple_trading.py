import asyncio

from sol_trade_sdk import (
    AccountPolicy,
    BuyAmount,
    DexType,
    TradeTokenType,
    simple_buy_params_to_trade_buy_params,
)
from _shared import RUN_LIVE, create_example_client, describe_dry_run, example_buy_params, log_result


async def main() -> None:
    client = create_example_client()
    template = example_buy_params(DexType.PUMPFUN)

    simple = (
        SimpleBuyParams.new(
            DexType.PUMPFUN,
            TradeTokenType.WSOL,
            template.mint,
            BuyAmount.with_max_input(template.input_token_amount),
            template.extension_params,
            template.recent_blockhash,
            template.gas_fee_strategy,
        )
        .set_slippage_basis_points(template.slippage_basis_points or 500)
        .set_account_policy(AccountPolicy.AUTO)
        .set_wait_tx_confirmed(False)
        .set_wait_for_all_submits(False)
    )

    low_level = simple_buy_params_to_trade_buy_params(simple)

    describe_dry_run("Simple buy intent API")
    print("Wallet:", client.get_payer())
    print("pay_with:", simple.pay_with)
    print("amount intent:", simple.amount)
    print("create_input_token_ata:", low_level.create_input_token_ata)
    print("create_mint_ata:", low_level.create_mint_ata)

    if RUN_LIVE:
        blockhash = await client.get_latest_blockhash()
        simple.recent_blockhash = str(blockhash.blockhash)
        log_result("buy_simple", await client.buy_simple(simple))
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
