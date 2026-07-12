import asyncio
import os
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Any, Callable, Optional

from _shared import (
    checked_position_delta,
    create_live_client,
    is_event_fresh,
    matches_target,
    validate_trade_intent,
)
from solders.pubkey import Pubkey

from sol_trade_sdk import DexType, TradeBuyParams, TradeSellParams, TradeTokenType, TradingClient


@dataclass(frozen=True)
class ParsedPoolEvent:
    """Small adapter contract for decoded sol-parser-sdk events."""

    received_at_ms: int
    dex_type: DexType
    mint: Pubkey
    pool: Pubkey
    token_program: Pubkey
    buy_state: Any


ReadBalance = Callable[[Pubkey, Pubkey, Pubkey], Awaitable[int]]
RefreshSellState = Callable[[ParsedPoolEvent], Awaitable[Any]]

MAX_EVENT_AGE_MS = int(os.getenv("MAX_EVENT_AGE_MS", "500"))
INPUT_AMOUNT = int(os.getenv("INPUT_AMOUNT", "100000"))
SLIPPAGE_BPS = int(os.getenv("SLIPPAGE_BPS", "300"))


async def handle_parsed_event(
    client: TradingClient,
    read_balance: ReadBalance,
    refresh_sell_state: RefreshSellState,
    event: ParsedPoolEvent,
    target_mint: Optional[Pubkey] = None,
    target_pool: Optional[Pubkey] = None,
) -> None:
    """Register this coroutine from the solana-streamer event callback."""
    if not is_event_fresh(event.received_at_ms, MAX_EVENT_AGE_MS):
        return
    if not matches_target(event.mint, target_mint) or not matches_target(event.pool, target_pool):
        return
    validate_trade_intent(INPUT_AMOUNT, SLIPPAGE_BPS)

    owner = client.get_payer()
    before = await read_balance(owner, event.mint, event.token_program)
    buy_blockhash = await client.get_latest_blockhash()
    buy = TradeBuyParams(
        dex_type=event.dex_type,
        input_token_type=TradeTokenType.WSOL,
        mint=event.mint,
        input_token_amount=INPUT_AMOUNT,
        slippage_basis_points=SLIPPAGE_BPS,
        recent_blockhash=str(buy_blockhash.blockhash),
        extension_params=event.buy_state,
        wait_tx_confirmed=True,
    )
    bought = await client.buy(buy)
    if not bought.success:
        raise RuntimeError(f"buy was not confirmed: {bought.error}")

    after = await read_balance(owner, event.mint, event.token_program)
    acquired = checked_position_delta(before, after)

    # Confirmation changes both the pool state and the usable blockhash window.
    sell_state = await refresh_sell_state(event)
    sell_blockhash = await client.get_latest_blockhash()
    sell = TradeSellParams(
        dex_type=event.dex_type,
        output_token_type=TradeTokenType.WSOL,
        mint=event.mint,
        input_token_amount=acquired,
        slippage_basis_points=SLIPPAGE_BPS,
        recent_blockhash=str(sell_blockhash.blockhash),
        extension_params=sell_state,
        wait_tx_confirmed=True,
    )
    sold = await client.sell(sell)
    if not sold.success:
        raise RuntimeError(f"sell failed: {sold.error}")


async def main() -> None:
    client = create_live_client()
    print("Live client ready:", client.get_payer())
    print("Register handle_parsed_event with solana-streamer and provide real parser/RPC adapters.")
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
