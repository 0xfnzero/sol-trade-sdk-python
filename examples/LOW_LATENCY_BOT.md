# Low-latency bot guide / 低延迟机器人指南

`low_latency_bot.py` defines a version-neutral boundary between `sol-parser-sdk`, `solana-streamer`, and this SDK. Convert decoded events to `ParsedPoolEvent`, schedule `handle_parsed_event` from the streamer callback, and implement the balance/state callbacks with real RPC data. Do not block the subscription reader while awaiting a trade.

该模板用于隔离三个 SDK 的版本差异。把解析事件转换为 `ParsedPoolEvent`，从 streamer 回调调度 `handle_parsed_event`，余额和池状态必须来自真实 RPC。不要在订阅读循环中同步等待整笔交易。

## Safe state machine / 安全状态机

1. Filter by event age, mint, and pool before doing RPC work.
2. Query the user's ATA with the mint's actual SPL Token or Token-2022 program.
3. Use current decoded state and a fresh blockhash for the buy.
4. Require buy confirmation before an automatic sell.
5. Sell only the checked `after_balance - before_balance` delta.
6. Refresh pool state and fetch another blockhash for the sell.

这六步不能通过固定 sleep、固定买入输出或复用同一个 blockhash 代替。

## `min_base_amount_out` / Custom(6040)

6040 (`BuySlippageBelowMinBaseAmountOut`) is a protection failure: actual base-token output is below the explicit minimum. Usually the quote became stale because reserves changed before execution.

- Prefer `BuyAmount.with_max_input(...)` or SDK slippage-derived protection for ordinary exact-input buys when supported.
- Set `fixed_output_token_amount` only from a fresh, protocol-specific quote. Example constants are not quotes.
- Do not disable the minimum merely to suppress 6040. That changes a failed protected trade into a potentially bad fill.
- On 6040, refresh state and blockhash, requote, and retry only within a small configured limit and the original event-age/price budget.
- The SDK accepts slippage only from 0 through 9999 basis points.

6040 说明保护条件没有满足，而不是 SDK 随机失败。普通 exact-input 买入优先使用 `BuyAmount.with_max_input(...)` 或 SDK 的动态滑点保护；显式最低输出只能来自实时 quote。失败后应有限次重新报价，事件过期或价格越界就停止。

## Operational notes / 运行注意事项

Pre-create hot-path token accounts, keep parser filters in memory, cap SWQoS submission concurrency, and set `wait_tx_confirmed=True` when the sell depends on the buy. Waiting for every provider improves diagnostics but increases tail latency. Never log private-key material.
