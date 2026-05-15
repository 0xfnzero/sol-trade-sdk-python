# Sol Trade SDK Python Examples

Examples are updated for the current Python SDK API. They run in dry-run mode by default so they do not send mainnet transactions accidentally.

## Run

```bash
pip install -e .
python examples/trading_client.py
```

Set `RUN_LIVE_EXAMPLES=1` only after replacing placeholder params with real RPC/parser data and funding the signer.

## Coverage

| Area | Example |
| --- | --- |
| Trading client and low-latency config | [trading_client.py](trading_client.py) |
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
