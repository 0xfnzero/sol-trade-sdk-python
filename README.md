# Sol Trade SDK for Python

<p align="center">
    <strong>A high-performance Python SDK for low-latency Solana DEX trading</strong>
</p>

<p align="center">
    <a href="https://pypi.org/project/sol-trade-sdk">
        <img src="https://img.shields.io/pypi/v/sol-trade-sdk.svg" alt="PyPI">
    </a>
    <a href="https://pypi.org/project/sol-trade-sdk">
        <img src="https://img.shields.io/pypi/pyversions/sol-trade-sdk.svg" alt="Python Versions">
    </a>
    <a href="LICENSE">
        <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License">
    </a>
</p>

<p align="center">
    <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
    <img src="https://img.shields.io/badge/Solana-9945FF?style=for-the-badge&logo=solana&logoColor=white" alt="Solana">
    <img src="https://img.shields.io/badge/DEX-4B8BBE?style=for-the-badge&logo=bitcoin&logoColor=white" alt="DEX Trading">
</p>

<p align="center">
    <a href="README_CN.md">中文</a> |
    <a href="https://fnzero.dev/">Website</a> |
    <a href="https://t.me/fnzero_group">Telegram</a> |
    <a href="https://discord.gg/vuazbGkqQE">Discord</a>
</p>

---

A comprehensive, high-performance Python SDK for Solana DEX trading with support for multiple protocols and MEV providers.

## Features

- **Multiple DEX Support**: PumpFun, PumpSwap, Bonk, Raydium AMM V4, Raydium CPMM, Meteora DAMM V2
- **SWQoS Integration**: Multiple MEV providers for transaction submission
- **High Performance**: LRU/TTL/Sharded caching, connection pooling, parallel execution
- **Low Latency**: Optimized for sub-second trade execution
- **Security First**: Integer overflow protection, secure key storage, input validation
- **Zero-RPC Hot Path**: All RPC calls happen BEFORE trading execution
- **Modular Design**: Use only what you need

## Installation

### Direct Clone (Recommended)

Clone this project to your project directory:

```bash
cd your_project_root_directory
git clone https://github.com/0xfnzero/sol-trade-sdk-python
```

Install dependencies:

```bash
cd sol-trade-sdk-python
pip install -e .
```

Or add to your `requirements.txt`:

```
sol-trade-sdk @ ./sol-trade-sdk-python
```

Or add to your `pyproject.toml`:

```toml
[project]
dependencies = [
    "sol-trade-sdk @ ./sol-trade-sdk-python",
]
```

### Use PyPI

```bash
pip install sol-trade-sdk
```

## Quick Start

### Basic Trading

```python
import asyncio
from sol_trade_sdk import (
    create_gas_fee_strategy,
    TradeExecutor,
    TradeConfig,
    SwqosType,
    TradeType,
)

async def main():
    # Create gas strategy
    gas_strategy = create_gas_fee_strategy()

    # Create trade executor
    config = TradeConfig(
        rpc_url="https://api.mainnet-beta.solana.com",
        swqos_configs=[{"type": SwqosType.JITO}],
        gas_fee_strategy=gas_strategy,
    )

    executor = TradeExecutor(config)

    # Execute trade
    result = await executor.execute(
        trade_type=TradeType.BUY,
        transaction=serialized_tx,
    )
    print(f"Transaction signature: {result.signature}")

asyncio.run(main())
```

### PumpFun Trading

```python
from sol_trade_sdk.instruction.pumpfun import PumpFunInstructionBuilder
from sol_trade_sdk.calc.pumpfun import getBuyTokenAmountFromSolAmount

# Calculate tokens received for SOL input
tokens = getBuyTokenAmountFromSolAmount(
    virtual_token_reserves=1_073_000_000_000_000,
    virtual_sol_reserves=30_000_000_000,
    real_token_reserves=793_000_000_000_000,
    has_creator=True,
    amount=1_000_000_000,  # 1 SOL
)

# Build buy instructions
instructions = PumpFunInstructionBuilder.build_buy_instructions(
    payer=payer_pubkey,
    output_mint=token_mint,
    input_amount=1_000_000_000,
    slippage_basis_points=500,  # 5%
    bonding_curve=bonding_curve_pubkey,
    creator_vault=creator_vault_pubkey,
    associated_bonding_curve=abc_pubkey,
)
```

### Hot Path Execution (Zero-RPC Trading)

```python
from sol_trade_sdk.hotpath.executor import HotPathExecutor
from sol_trade_sdk.hotpath.state import HotPathState

# Initialize hot path state with pre-fetched data
state = HotPathState()
await state.prefetch_blockhash(rpc_client)
await state.cache_account(token_account_pubkey)

# Execute without any RPC calls during trading
executor = HotPathExecutor(state)
result = await executor.execute_trade(transaction)
```

## Usage Examples Summary

| Description | File | Run Command |
|-------------|------|-------------|
| Create and configure TradingClient instance | [trading_client.py](examples/trading_client.py) | `python examples/trading_client.py` |
| Share infrastructure across multiple wallets | [shared_infrastructure.py](examples/shared_infrastructure.py) | `python examples/shared_infrastructure.py` |
| PumpFun token sniping trading | [pumpfun_sniper_trading.py](examples/pumpfun_sniper_trading.py) | `python examples/pumpfun_sniper_trading.py` |
| PumpFun token copy trading | [pumpfun_copy_trading.py](examples/pumpfun_copy_trading.py) | `python examples/pumpfun_copy_trading.py` |
| PumpSwap trading operations | [pumpswap_trading.py](examples/pumpswap_trading.py) | `python examples/pumpswap_trading.py` |
| PumpSwap direct trading (via RPC) | [pumpswap_direct_trading.py](examples/pumpswap_direct_trading.py) | `python examples/pumpswap_direct_trading.py` |
| Raydium CPMM trading operations | [raydium_cpmm_trading.py](examples/raydium_cpmm_trading.py) | `python examples/raydium_cpmm_trading.py` |
| Raydium AMM V4 trading operations | [raydium_amm_v4_trading.py](examples/raydium_amm_v4_trading.py) | `python examples/raydium_amm_v4_trading.py` |
| Meteora DAMM V2 trading operations | [meteora_damm_v2_trading.py](examples/meteora_damm_v2_trading.py) | `python examples/meteora_damm_v2_trading.py` |
| Bonk token sniping trading | [bonk_sniper_trading.py](examples/bonk_sniper_trading.py) | `python examples/bonk_sniper_trading.py` |
| Bonk token copy trading | [bonk_copy_trading.py](examples/bonk_copy_trading.py) | `python examples/bonk_copy_trading.py` |
| Custom instruction middleware example | [middleware_system.py](examples/middleware_system.py) | `python examples/middleware_system.py` |
| Address lookup table example | [address_lookup.py](examples/address_lookup.py) | `python examples/address_lookup.py` |
| Nonce cache (durable nonce) example | [nonce_cache.py](examples/nonce_cache.py) | `python examples/nonce_cache.py` |
| Wrap/unwrap SOL to/from WSOL example | [wsol_wrapper.py](examples/wsol_wrapper.py) | `python examples/wsol_wrapper.py` |
| Seed trading example | [seed_trading.py](examples/seed_trading.py) | `python examples/seed_trading.py` |
| Gas fee strategy example | [gas_fee_strategy.py](examples/gas_fee_strategy.py) | `python examples/gas_fee_strategy.py` |

## Security Features

```python
from sol_trade_sdk.security import SecureKeyStorage, validate_rpc_url, validate_amount

# Secure key storage with memory encryption
storage = SecureKeyStorage.from_keypair(keypair, password="optional_password")
with storage.unlock() as kp:
    signature = kp.sign(message)

# Input validation
validate_rpc_url("https://api.mainnet-beta.solana.com")
validate_amount(1_000_000_000, "amount", allow_zero=False)
```

## Address Lookup Tables

```python
from sol_trade_sdk.address_lookup import fetch_address_lookup_table_account

# Fetch ALT from chain
alt = await fetch_address_lookup_table_account(rpc, alt_address)
print(f"ALT contains {len(alt.addresses)} addresses")
```

## Architecture

| Module | Description |
|--------|-------------|
| `cache` | LRU, TTL, and sharded caches |
| `calc` | AMM calculations for all DEXes |
| `common` | Core types, gas strategies, bonding curves |
| `execution` | Branch optimization, prefetching |
| `hotpath` | Zero-RPC hot path execution |
| `instruction` | Instruction builders for all DEXes |
| `middleware` | Instruction middleware system |
| `perf` | Performance optimizations (SIMD, kernel bypass, etc.) |
| `pool` | Connection and worker pools |
| `rpc` | High-performance RPC clients |
| `security` | Secure key storage, validators |
| `seed` | PDA derivation for all protocols |
| `swqos` | MEV provider clients |
| `trading` | High-performance trade executor |

## Performance Optimizations

### SIMD Vectorization
```python
from sol_trade_sdk.perf.simd import vectorized_hash
hashes = vectorized_hash(data_list)
```

### Kernel Bypass (Linux io_uring)
```python
from sol_trade_sdk.perf.kernel_bypass import AsyncIOUring
uring = AsyncIOUring(queue_depth=256)
```

### Zero-Copy I/O
```python
from sol_trade_sdk.perf.zero_copy_io import ZeroCopyBuffer
buffer = ZeroCopyBuffer.allocate(1024)
```

## Supported Protocols

### PumpFun
- Bonding curve calculations with creator fee support
- Buy/Sell instruction building
- PDA derivation for bonding curve and associated accounts

### PumpSwap
- Pool calculations with LP/protocol/creator fees
- Buy/Sell instruction building
- Mayhem mode support

### Bonk
- Virtual/real reserve calculations
- Protocol fee handling

### Raydium
- AMM V4 calculations with constant product
- CPMM calculations
- Authority PDA derivation

### Meteora
- DAMM V2 swap calculations
- Pool PDA derivation

## Middleware System

```python
from sol_trade_sdk.middleware import MiddlewareManager, LoggingMiddleware, ValidationMiddleware

manager = MiddlewareManager()
manager.add_middleware(ValidationMiddleware(max_instructions=100))
manager.add_middleware(LoggingMiddleware())

# Apply middlewares to instructions
processed = manager.apply_middlewares_process_protocol_instructions(
    instructions, "PumpFun", is_buy=True
)
```

## Requirements

- Python >= 3.9
- solders >= 0.18.0
- solana >= 0.30.0
- aiohttp >= 3.8.0

## License

MIT License

## Contact

- Official Website: https://fnzero.dev/
- Project Repository: https://github.com/0xfnzero/sol-trade-sdk-python
- Telegram Group: https://t.me/fnzero_group
- Discord: https://discord.gg/vuazbGkqQE
