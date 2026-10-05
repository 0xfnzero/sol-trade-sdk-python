# Sol Trade SDK Python Examples

Examples are updated for the current Python SDK API. Basic protocol demonstrations contain synthetic accounts and are intentionally dry-run only; setting `RUN_LIVE_EXAMPLES=1` makes them fail closed.

## Run

```bash
pip install -e .
python examples/trading_client.py
```

For a live bot, start from [low_latency_bot.py](low_latency_bot.py), read [LOW_LATENCY_BOT.md](LOW_LATENCY_BOT.md), and provide real parser, balance, quote, and state-refresh adapters. `PRIVATE_KEY` accepts a base58 64-byte secret key or a JSON array containing 64 bytes.

## Coverage

| Area | Example |
| --- | --- |
| Trading client and low-latency config | [trading_client.py](trading_client.py) |
| Parser + streamer guarded bot workflow | [low_latency_bot.py](low_latency_bot.py) |
| Shared config across wallets | [shared_infrastructure.py](shared_infrastructure.py) |
| PumpFun v2 fee recipient and cashback | [pumpfun_sniper_trading.py](pumpfun_sniper_trading.py), [pumpfun_copy_trading.py](pumpfun_copy_trading.py), [pumpfun_trading.py](pumpfun_trading.py) |
| PumpSwap cashback-aware params | [pumpswap_trading.py](pumpswap_trading.py), [pumpswap_direct_trading.py](pumpswap_direct_trading.py) |
| Bonk / USD1 routing | [bonk_sniper_trading.py](bonk_sniper_trading.py), [bonk_copy_trading.py](bonk_copy_trading.py) |
| Raydium CPMM / AMM v4 | [raydium_cpmm_trading.py](raydium_cpmm_trading.py), [raydium_amm_v4_trading.py](raydium_amm_v4_trading.py) |
| Meteora DAMM v2 | [meteora_damm_v2_trading.py](meteora_damm_v2_trading.py) |
| Durable nonce | [nonce_cache.py](nonce_cache.py) |
| Hot path / zero-RPC preparation | [hot_path_trading.py](hot_path_trading.py) |
| Address lookup tables | [address_lookup.py](address_lookup.py) |
| Middleware | [middleware_system.py](middleware_system.py) |
| WSOL helpers | [wsol_wrapper.py](wsol_wrapper.py) |


### 第二批审查的 CPMM 样本（2026-10-03）

`fixtures/batch2_cpmm_buy_20261003.json` 和 `batch2_cpmm_sell_20261003.json` 是完整冷启动快照，可交给本仓 `cached_cpmm` 示例离线构建独立买入/卖出；三语言 wire 一致。对应 `batch2_cpmm_simulations_20261003.json` 保存两笔成功主网模拟，可供 parser 的 `simulation_routes` 示例读取。没有真实发送。保存快照仅供复现，执行新交易前须由冷启动/订阅提供当前状态；构建与报价不调用 RPC。

缓存 CPMM 现检查 vault 的 token authority，prepare 拒绝零最小到账。CLMM/DLMM 可扫描完整合法稀疏范围；bitmap 证明空区间不需要虚构账户，已初始化 array 缺少订阅数据仍明确拒绝。实时账户输入通过 sol-parser-sdk 的 gRPC 接入；见 [GRPC_CACHE.md](GRPC_CACHE.md)。新 array 发现、静态账户 freshness 和分叉一致性仍由 gRPC 订阅集成策略处理。

当前银行模拟与跨语言成交检查见 [SIMULATION_MATRIX.md](SIMULATION_MATRIX.md)，包含 `--simulation-out` 保存证据和 parser 离线验收流程。
