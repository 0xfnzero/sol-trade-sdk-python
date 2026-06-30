<div align="center">
    <h1>🚀 Sol Trade SDK for Python</h1>
    <h3><em>A comprehensive Python SDK for seamless Solana DEX trading</em></h3>
</div>

<p align="center">
    <strong>A high-performance Python SDK for low-latency Solana DEX trading bots. Built for speed and efficiency, it enables seamless, high-throughput interaction with PumpFun, Pump AMM (PumpSwap), Bonk, Meteora DAMM v2, Raydium AMM v4, and Raydium CPMM for latency-critical trading strategies.</strong>
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
    <a href="https://github.com/0xfnzero/sol-trade-sdk-python/blob/main/README_CN.md">中文</a> |
    <a href="https://github.com/0xfnzero/sol-trade-sdk-python/blob/main/README.md">English</a> |
    <a href="https://fnzero.dev/">Website</a> |
    <a href="https://t.me/fnzero_group">Telegram</a> |
    <a href="https://discord.gg/vuazbGkqQE">Discord</a>
</p>

> ☕ **Support This Project**
>
> This SDK is completely free and open source. However, maintaining and continuously updating it requires significant AI computing resources and token consumption. If this SDK helps with your development, consider making a monthly SOL donation — any amount is appreciated and helps keep this project alive!
>
> **Donation Wallet:** `6oW7AXz1yRb57pYSxysuXnMs2aR1ha5rzGzReZ1MjPV8`

## 📋 Table of Contents

- [✨ Features](#-features)
- [📦 Installation](#-installation)
- [🛠️ Usage Examples](#️-usage-examples)
  - [📋 Example Usage](#-example-usage)
  - [⚡ Trading Parameters](#-trading-parameters)
  - [📊 Usage Examples Summary Table](#-usage-examples-summary-table)
  - [⚙️ SWQoS Service Configuration](#️-swqos-service-configuration)
  - [🔧 Middleware System](#-middleware-system)
  - [🔍 Address Lookup Tables](#-address-lookup-tables)
  - [🔍 Nonce Cache](#-nonce-cache)
- [💰 Cashback Support (PumpFun / PumpSwap)](#-cashback-support-pumpfun--pumpswap)
- [🛡️ MEV Protection Services](#️-mev-protection-services)
- [📁 Project Structure](#-project-structure)
- [📄 License](#-license)
- [💬 Contact](#-contact)
- [⚠️ Important Notes](#️-important-notes)

---

## 📦 SDK Versions

This SDK is available in multiple languages:

| Language | Repository | Description |
|----------|------------|-------------|
| **Rust** | [sol-trade-sdk](https://github.com/0xfnzero/sol-trade-sdk) | Ultra-low latency with zero-copy optimization |
| **Node.js** | [sol-trade-sdk-nodejs](https://github.com/0xfnzero/sol-trade-sdk-nodejs) | TypeScript/JavaScript for Node.js |
| **Python** | [sol-trade-sdk-python](https://github.com/0xfnzero/sol-trade-sdk-python) | Async/await native support |
| **Go** | [sol-trade-sdk-golang](https://github.com/0xfnzero/sol-trade-sdk-golang) | Concurrent-safe with goroutine support |

## What This SDK Is For

`sol-trade-sdk-python` brings the FnZero Solana trading SDK to Python. It is built for async trading bots, copy-trading pipelines, sniper bots, research automation, and backend services that need low-latency Solana DEX trade construction with Rust SDK behavior parity.

| Area | Coverage |
|------|----------|
| DEX protocols | PumpFun, PumpSwap, Bonk, Meteora DAMM v2, Raydium AMM v4, Raydium CPMM |
| Submit lanes | Default Solana RPC plus Jito, ZeroSlot, Temporal, Bloxroute, FlashBlock, BlockRazor, Node1, Astralane, Stellium, Lightspeed, Soyas, Speedlanding, Helius, and Solami; NextBlock remains Rust-blacklisted by default |
| Trading workflows | `buy_simple` / `sell_simple`, legacy buy/sell params, copy trading, sniper trading, address lookup tables, durable nonce, middleware, shared infrastructure |
| Runtime | Python 3.9+, async services, research scripts, and latency-sensitive bot infrastructure |

## 🔖 Current Release

**PyPI package:** `sol-trade-sdk==0.1.5`

This release refreshes PumpFun V2 and USDC quote-pool handling, keeps the default RPC submit lane active alongside SWQoS lanes, and aligns Raydium CPMM fixed-output swaps with the on-chain `swap_base_out` instruction. Trade execution requires a caller-supplied `recent_blockhash` or durable nonce; hot-path execution does not query RPC for blockhash, account, or balance data.

## Rust v4.0.21 Parity

This SDK now tracks the Rust SDK `v4.0.21` public behavior for high-level trade intent APIs and SWQoS provider coverage. New code can use `buy_simple` / `sell_simple` with `AccountPolicy`, `BuyAmount`, and `SellAmount`; these convert to the existing `buy` / `sell` params without removing the legacy API. SWQoS coverage includes the Rust `Solami` type and defaults (`beam.solami.dev:11000`, min tip `0.0001 SOL`); live Solami submit uses the main QUIC client path and requires the same base58 Solana keypair api token model as Rust. Explicit SWQoS routes still keep the default RPC lane appended. NextBlock is still filtered by the Rust parity blacklist unless Rust changes that behavior. Legacy extended provider classes such as `Triton`, `QuickNode`, `Syndica`, `Figment`, and `Alchemy` are kept only for source compatibility and are not part of Rust `v4.0.21` trading provider parity.

## ✨ Features

1. **PumpFun Trading**: Unified `buy`, `sell`, and `buy_exact_quote_in` flow with automatic legacy or V2 instruction selection for SOL and USDC quote pools
2. **PumpSwap Trading**: Support for PumpSwap pool trading operations
3. **Bonk Trading**: Support for Bonk trading operations
4. **Raydium CPMM Trading**: Support for Raydium CPMM (Concentrated Pool Market Maker) trading operations
5. **Raydium AMM V4 Trading**: Support for Raydium AMM V4 (Automated Market Maker) trading operations
6. **Meteora DAMM V2 Trading**: Support for Meteora DAMM V2 (Dynamic AMM) trading operations
7. **Multiple MEV Protection**: Support for the Rust v4.0.21 SWQoS set, including Jito, ZeroSlot, Temporal, Bloxroute, FlashBlock, BlockRazor, Node1, Astralane, Stellium, Lightspeed, Soyas, Speedlanding, Helius, Solami, and Default RPC
8. **Concurrent Trading**: Submit through every configured SWQoS provider plus the default RPC lane; the first accepted result can return early while slower routes continue submitting
9. **Unified Trading Interface**: Use unified trading protocol types for trading operations, including Rust-parity `buy_simple` / `sell_simple` intent params
10. **Middleware System**: Support for custom instruction middleware to modify, add, or remove instructions before transaction execution
11. **Shared Infrastructure**: Share expensive RPC and SWQoS clients across multiple wallets for reduced resource usage
12. **Hot-Path RPC Boundary**: Trade execution uses caller-supplied blockhash or durable nonce and never queries RPC for blockhash, account, or balance data

## 📦 Installation

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
pip install sol-trade-sdk==0.1.5
```

## 🛠️ Usage Examples

### 📋 Example Usage

For the high-level intent API, see [Simple Trading](examples/simple_trading.py). It shows `SimpleBuyParams.new`, `BuyAmount.with_max_input`, `AccountPolicy.AUTO`, and the conversion to legacy `TradeBuyParams`.

#### 1. Create TradingClient Instance

You can refer to [Example: Create TradingClient Instance](examples/trading_client.py).

**Method 1: Simple (single wallet)**
```python
import asyncio
from sol_trade_sdk import TradingClient, TradeConfig, SwqosConfig, SwqosRegion

async def main():
    # Wallet
    payer = Keypair.from_secret_key(/* your keypair */)
    
    # RPC URL
    rpc_url = "https://mainnet.helius-rpc.com/?api-key=xxxxxx"
    
    # Multiple SWQoS services can be configured
    swqos_configs = [
        SwqosConfig(type="Default", rpc_url=rpc_url),
        SwqosConfig(type="Jito", uuid="your_uuid", region=SwqosRegion.FRANKFURT),
        SwqosConfig(type="Bloxroute", api_token="your_api_token", region=SwqosRegion.FRANKFURT),
        SwqosConfig(type="Astralane", api_key="your_api_key", region=SwqosRegion.FRANKFURT),
    ]
    
    # Create TradeConfig instance
    trade_config = TradeConfig(rpc_url, swqos_configs)
    
    # Create TradingClient
    client = TradingClient(payer, trade_config)

asyncio.run(main())
```

**Method 2: Shared infrastructure (multiple wallets)**

For multi-wallet scenarios, create the infrastructure once and share it across wallets.
See [Example: Shared Infrastructure](examples/shared_infrastructure.py).

```python
from sol_trade_sdk import TradingInfrastructure, InfrastructureConfig

# Create infrastructure once (expensive)
infra_config = InfrastructureConfig(rpc_url, swqos_configs)
infrastructure = TradingInfrastructure(infra_config)

# Create multiple clients sharing the same infrastructure (fast)
client1 = TradingClient.from_infrastructure(payer1, infrastructure)
client2 = TradingClient.from_infrastructure(payer2, infrastructure)
```

#### 2. Configure Gas Fee Strategy

```python
from sol_trade_sdk import GasFeeStrategy

# Create GasFeeStrategy instance
gas_fee_strategy = GasFeeStrategy()
# Set global strategy
gas_fee_strategy.set_global_fee_strategy(150000, 150000, 500000, 500000, 0.001, 0.001)
```

#### 3. Build Trading Parameters

```python
from sol_trade_sdk import (
    AccountPolicy,
    BuyAmount,
    DexType,
    SimpleBuyParams,
    TradeTokenType,
    simple_buy_params_to_trade_buy_params,
)

simple = (
    SimpleBuyParams.new(
        DexType.PUMPSWAP,
        TradeTokenType.WSOL,
        mint_pubkey,
        BuyAmount.with_max_input(buy_sol_amount),
        {"type": "PumpSwap", "params": pumpswap_params},
        recent_blockhash,
        gas_fee_strategy,
    )
    .set_slippage_basis_points(500)
    .set_account_policy(AccountPolicy.AUTO)
)
buy_params = simple_buy_params_to_trade_buy_params(simple)
    create_mint_ata=True,
    durable_nonce=None,
    fixed_output_token_amount=None,
    gas_fee_strategy=gas_fee_strategy,
    simulate=False,
)
```

#### 4. Execute Trading

```python
result = await client.buy(buy_params)
print(f"Transaction signature: {result.signature}")
```

### ⚡ Trading Parameters

For comprehensive information about all trading parameters including `TradeBuyParams` and `TradeSellParams`, see the Trading Parameters documentation.

#### About ShredStream

When using shred to subscribe to events, due to the nature of shreds, you cannot get complete information about transaction events.
Please ensure that the parameters your trading logic depends on are available in shreds when using them.

### 📊 Usage Examples Summary Table

| Description | Run Command | Source Code |
|-------------|-------------|-------------|
| Create and configure TradingClient instance | `python examples/trading_client.py` | [examples/trading_client.py](https://github.com/0xfnzero/sol-trade-sdk-python/blob/main/examples/trading_client.py) |
| Share infrastructure across multiple wallets | `python examples/shared_infrastructure.py` | [examples/shared_infrastructure.py](https://github.com/0xfnzero/sol-trade-sdk-python/blob/main/examples/shared_infrastructure.py) |
| PumpFun token sniping trading | `python examples/pumpfun_sniper_trading.py` | [examples/pumpfun_sniper_trading.py](https://github.com/0xfnzero/sol-trade-sdk-python/blob/main/examples/pumpfun_sniper_trading.py) |
| PumpFun token copy trading | `python examples/pumpfun_copy_trading.py` | [examples/pumpfun_copy_trading.py](https://github.com/0xfnzero/sol-trade-sdk-python/blob/main/examples/pumpfun_copy_trading.py) |
| PumpSwap trading operations | `python examples/pumpswap_trading.py` | [examples/pumpswap_trading.py](https://github.com/0xfnzero/sol-trade-sdk-python/blob/main/examples/pumpswap_trading.py) |
| PumpSwap direct trading (via RPC) | `python examples/pumpswap_direct_trading.py` | [examples/pumpswap_direct_trading.py](https://github.com/0xfnzero/sol-trade-sdk-python/blob/main/examples/pumpswap_direct_trading.py) |
| Raydium CPMM trading operations | `python examples/raydium_cpmm_trading.py` | [examples/raydium_cpmm_trading.py](https://github.com/0xfnzero/sol-trade-sdk-python/blob/main/examples/raydium_cpmm_trading.py) |
| Raydium AMM V4 trading operations | `python examples/raydium_amm_v4_trading.py` | [examples/raydium_amm_v4_trading.py](https://github.com/0xfnzero/sol-trade-sdk-python/blob/main/examples/raydium_amm_v4_trading.py) |
| Meteora DAMM V2 trading operations | `python examples/meteora_damm_v2_trading.py` | [examples/meteora_damm_v2_trading.py](https://github.com/0xfnzero/sol-trade-sdk-python/blob/main/examples/meteora_damm_v2_trading.py) |
| Bonk token sniping trading | `python examples/bonk_sniper_trading.py` | [examples/bonk_sniper_trading.py](https://github.com/0xfnzero/sol-trade-sdk-python/blob/main/examples/bonk_sniper_trading.py) |
| Bonk token copy trading | `python examples/bonk_copy_trading.py` | [examples/bonk_copy_trading.py](https://github.com/0xfnzero/sol-trade-sdk-python/blob/main/examples/bonk_copy_trading.py) |
| Custom instruction middleware example | `python examples/middleware_system.py` | [examples/middleware_system.py](https://github.com/0xfnzero/sol-trade-sdk-python/blob/main/examples/middleware_system.py) |
| Address lookup table example | `python examples/address_lookup.py` | [examples/address_lookup.py](https://github.com/0xfnzero/sol-trade-sdk-python/blob/main/examples/address_lookup.py) |
| Nonce cache (durable nonce) example | `python examples/nonce_cache.py` | [examples/nonce_cache.py](https://github.com/0xfnzero/sol-trade-sdk-python/blob/main/examples/nonce_cache.py) |
| Wrap/unwrap SOL to/from WSOL example | `python examples/wsol_wrapper.py` | [examples/wsol_wrapper.py](https://github.com/0xfnzero/sol-trade-sdk-python/blob/main/examples/wsol_wrapper.py) |
| Seed trading example | `python examples/seed_trading.py` | [examples/seed_trading.py](https://github.com/0xfnzero/sol-trade-sdk-python/blob/main/examples/seed_trading.py) |
| Gas fee strategy example | `python examples/gas_fee_strategy.py` | [examples/gas_fee_strategy.py](https://github.com/0xfnzero/sol-trade-sdk-python/blob/main/examples/gas_fee_strategy.py) |
| Hot path trading (zero-RPC) | `python examples/hot_path_trading.py` | [examples/hot_path_trading.py](https://github.com/0xfnzero/sol-trade-sdk-python/blob/main/examples/hot_path_trading.py) |

### ⚙️ SWQoS Service Configuration

When configuring SWQoS services, note the different parameter requirements for each service:

- **Jito**: The first parameter is UUID (if no UUID, pass an empty string `""`)
- **Other MEV services**: The first parameter is the API Token

#### Custom URL Support

Each SWQoS service supports an optional custom URL parameter:

```python
# Using custom URL
jito_config = SwqosConfig(
    type="Jito",
    uuid="your_uuid",
    region=SwqosRegion.FRANKFURT,
    custom_url="https://custom-jito-endpoint.com"
)

# Using default regional endpoint
bloxroute_config = SwqosConfig(
    type="Bloxroute",
    api_token="your_api_token",
    region=SwqosRegion.NEW_YORK
)
```

**URL Priority Logic**:
- If a custom URL is provided, it will be used instead of the regional endpoint
- If no custom URL is provided, the system will use the default endpoint for the specified region
- This allows for maximum flexibility while maintaining backward compatibility

When using multiple MEV services, you need to use `Durable Nonce`. You need to use the `fetch_nonce_info` function to get the latest `nonce` value, and use it as the `durable_nonce` when trading.

---

### 🔧 Middleware System

The SDK provides a powerful middleware system that allows you to modify, add, or remove instructions before transaction execution. Middleware executes in the order they are added:

```python
from sol_trade_sdk import MiddlewareManager

manager = MiddlewareManager() \
    .add_middleware(FirstMiddleware()) \
    .add_middleware(SecondMiddleware()) \
    .add_middleware(ThirdMiddleware())
```

### 🔍 Address Lookup Tables

Address Lookup Tables (ALT) allow you to optimize transaction size and reduce fees by storing frequently used addresses in a compact table format.

```python
from sol_trade_sdk import fetch_address_lookup_table_account, AddressLookupTableCache

# Fetch ALT from chain
alt = await fetch_address_lookup_table_account(rpc, alt_address)
print(f"ALT contains {len(alt.addresses)} addresses")

# Use cache for performance
cache = AddressLookupTableCache(rpc)
await cache.prefetch([alt_address1, alt_address2, alt_address3])
cached = cache.get(alt_address1)
```

### 🔍 Durable Nonce

Use Durable Nonce to implement transaction replay protection and optimize transaction processing.

```python
from sol_trade_sdk import fetch_nonce_info, NonceCache

# Fetch nonce info
nonce_info = await fetch_nonce_info(rpc, nonce_account)
```

## 💰 Cashback Support (PumpFun / PumpSwap)

PumpFun and PumpSwap support **cashback** for eligible tokens: part of the trading fee can be returned to the user. The SDK **must know** whether the token has cashback enabled so that buy/sell instructions include the correct accounts.

- **When params come from RPC**: If you use `PumpFunParams.from_mint_by_rpc` or `PumpSwapParams.from_pool_address_by_rpc`, the SDK reads `is_cashback_coin` from chain—no extra step.
- **When params come from decoded events**: If you build params from already-decoded trade events (for example from a parser service), you **must** pass the cashback flag into the SDK:
  - **PumpFun**: Set `is_cashback_coin` when building params from decoded events.
  - **PumpSwap**: Set `is_cashback_coin` field when constructing params manually.

## 🛡️ MEV Protection Services

You can apply for a key through the official website: [Community Website](https://fnzero.dev/swqos)

- **Jito**: High-performance block space
- **ZeroSlot**: Zero-latency transactions
- **Temporal**: Time-sensitive transactions
- **Bloxroute**: Blockchain network acceleration
- **FlashBlock**: High-speed transaction execution with API key authentication
- **BlockRazor**: High-speed transaction execution with API key authentication
- **Node1**: High-speed transaction execution with API key authentication
- **Astralane**: Blockchain network acceleration

## 📁 Project Structure

```
src/
├── common/           # Common functionality and tools
├── constants/        # Constant definitions
├── instruction/      # Instruction building
│   └── utils/        # Instruction utilities
├── swqos/            # MEV service clients
├── trading/          # Unified trading engine
│   ├── common/       # Common trading tools
│   ├── core/         # Core trading engine
│   ├── middleware/   # Middleware system
│   └── factory.py    # Trading factory
├── utils/            # Utility functions
│   ├── calc/         # Amount calculation utilities
│   └── price/        # Price calculation utilities
└── __init__.py       # Main library file
```

## 📄 License

MIT License

## 💬 Contact

- Official Website: https://fnzero.dev/
- Project Repository: https://github.com/0xfnzero/sol-trade-sdk-python
- Telegram Group: https://t.me/fnzero_group
- Discord: https://discord.gg/vuazbGkqQE

## ⚠️ Important Notes

1. Test thoroughly before using on mainnet
2. Properly configure private keys and API tokens
3. Pay attention to slippage settings to avoid transaction failures
4. Monitor balances and transaction fees
5. Comply with relevant laws and regulations
