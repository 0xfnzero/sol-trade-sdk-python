# Sol Trade SDK Python Examples

Examples are updated for the current Python SDK API. Protocol examples contain synthetic accounts and are intentionally dry-run only; setting `RUN_LIVE_EXAMPLES=1` makes them fail closed.

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
