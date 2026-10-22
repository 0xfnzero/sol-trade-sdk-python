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
    <a href="#license">
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

Current version: **9.0.1**. Read the [migration notes](RELEASE_NOTES.md) before upgrading; see the [changelog](CHANGELOG.md) for historical changes.

## Contents

Pump.fun defaults to V3 with per-request V1/V2/V3 overrides. See [version configuration, multi-hop examples and simulation limits](docs/PUMPFUN_VERSIONS.md).

- [SDK Versions and Related SDKs](#sdk-versions-and-related-sdks)
- [Installation](#installation)
- [What This SDK Is For](#what-this-sdk-is-for)
- [Features](#features)
- [Usage Examples](#usage-examples)
- [Documentation](#documentation)
- [PumpSwap cached routes](#pumpswap-routes)

<a id="sdk-versions-and-related-sdks"></a>

## 📦 SDK Versions and Related SDKs

Repositories are versioned independently; follow each SDK’s installation guide for compatible dependencies.

| Language | Repository | Purpose | Version |
|----------|------------|-------------|---------|
| Rust | [sol-parser-sdk](https://github.com/0xfnzero/sol-parser-sdk) | DEX transaction and account event parsing | `v0.9.1` |
| Node.js | [sol-parser-sdk-nodejs](https://github.com/0xfnzero/sol-parser-sdk-nodejs) | DEX transaction and account event parsing | `v0.9.1` |
| Python | [sol-parser-sdk-python](https://github.com/0xfnzero/sol-parser-sdk-python) | DEX transaction and account event parsing | `v0.9.1` |
| Go | [sol-parser-sdk-golang](https://github.com/0xfnzero/sol-parser-sdk-golang) | DEX transaction and account event parsing | `v0.9.1` |
| Rust | [sol-trade-sdk](https://github.com/0xfnzero/sol-trade-sdk) | Transaction building, signing and multi-channel submission | `v9.0.1` |
| Node.js | [sol-trade-sdk-nodejs](https://github.com/0xfnzero/sol-trade-sdk-nodejs) | Transaction building, signing and multi-channel submission | `v9.0.1` |
| Python | [sol-trade-sdk-python](https://github.com/0xfnzero/sol-trade-sdk-python) | Transaction building, signing and multi-channel submission | `v9.0.1` |
| Go | [sol-trade-sdk-golang](https://github.com/0xfnzero/sol-trade-sdk-golang) | Transaction building, signing and multi-channel submission | `v9.0.1` |
| Rust | [sol-shred-sdk](https://github.com/0xfnzero/sol-shred-sdk) | Raw shred decoding and ShredStream instruction events | `v6.0.1` |
| Rust | [solana-streamer](https://github.com/0xfnzero/solana-streamer) | gRPC / ShredStream subscriptions and event streaming | `v5.0.0` |
| Rust | [sol-trade-router-sdk](https://github.com/0xfnzero/sol-trade-router-sdk) | On-chain multi-hop router and client SDK | `v0.3.0` |

<a id="installation"></a>

## Installation

```sh
pip install sol-trade-sdk==9.0.1
```

To run repository examples or contribute, clone the source:

```sh
git clone https://github.com/0xfnzero/sol-trade-sdk-python
cd sol-trade-sdk-python
pip install -e ".[dev]"
```

See [the example index](examples/README.md) for configuration and offline versus live workflows.

<a id="what-this-sdk-is-for"></a>

## What This SDK Is For

`sol-trade-sdk-python` brings the FnZero Solana trading SDK to Python. It is built for async trading bots, copy-trading pipelines, sniper bots, research automation, and backend services that need low-latency Solana DEX trade construction with Rust SDK behavior parity.

| Area | Coverage |
|------|----------|
| DEX protocols | PumpFun, PumpSwap, Bonk, Meteora DAMM v2, Raydium AMM v4, Raydium CPMM |
| Submit lanes | Default Solana RPC plus Jito, ZeroSlot, Temporal, Bloxroute, FlashBlock, BlockRazor, Astralane, Stellium, Lightspeed, Soyas, Speedlanding, Helius, and Solami; NextBlock remains Rust-blacklisted by default |
| Trading workflows | `buy_simple` / `sell_simple`, legacy buy/sell params, copy trading, sniper trading, address lookup tables, durable nonce, middleware, shared infrastructure |
| Runtime | Python 3.10+, async services, research scripts, and latency-sensitive bot infrastructure |

<a id="features"></a>

## ✨ Features

1. **PumpFun Trading**: Unified `buy`, `sell`, and `buy_exact_quote_in` flow with automatic legacy or V2 instruction selection for SOL and USDC quote pools
2. **PumpSwap Trading**: Support for PumpSwap pool trading operations
3. **Bonk Trading**: Support for Bonk trading operations
4. **Raydium CPMM Trading**: Support for Raydium CPMM (Constant Product Market Maker) trading operations
5. **Raydium AMM V4 Trading**: Support for Raydium AMM V4 (Automated Market Maker) trading operations
6. **Meteora DAMM V2 Trading**: Support for Meteora DAMM V2 (Dynamic AMM) trading operations
7. **Multiple MEV Protection**: Support for the Rust v5.0.2 SWQoS set, including Jito, ZeroSlot, Temporal, Bloxroute, FlashBlock, BlockRazor, Astralane, Stellium, Lightspeed, Soyas, Speedlanding, Helius, Solami, LunarLander, Glaive, and Default RPC
8. **Concurrent Trading**: Submit through every configured SWQoS provider plus the default RPC lane; the first accepted result can return early while slower routes continue submitting
9. **Unified Trading Interface**: Use unified trading protocol types for trading operations, including Rust-parity `buy_simple` / `sell_simple` intent params
10. **Middleware System**: Support for custom instruction middleware to modify, add, or remove instructions before transaction execution
11. **Shared Infrastructure**: Share expensive RPC and SWQoS clients across multiple wallets for reduced resource usage
12. **Hot-Path RPC Boundary**: Trade execution uses caller-supplied blockhash or durable nonce and never queries RPC for blockhash, account, or balance data

<a id="usage-examples"></a>

## 🛠️ Usage Examples

### 📋 Trading workflow

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

Temporal uses HTTP/3 QUIC first and Binary Batch HTTP as its default fallback. BlockRazor uses gRPC `SendBinaryTransaction` first and JSON HTTP as fallback. Astralane uses persistent QUIC first and Binary HTTP as fallback. Explicit transport settings force one protocol; a custom URL without a transport remains an explicit HTTP route.

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

### Example index

See the [example index](examples/README.md) for workflows, commands and configuration requirements.

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

<a id="cashback-support-pumpfun-pumpswap"></a>

## 💰 Cashback Support (PumpFun / PumpSwap)

PumpFun and PumpSwap support **cashback** for eligible tokens: part of the trading fee can be returned to the user. The SDK **must know** whether the token has cashback enabled so that buy/sell instructions include the correct accounts.

- **When params come from RPC**: If you use `PumpFunParams.from_mint_by_rpc` or `PumpSwapParams.from_pool_address_by_rpc`, the SDK reads `is_cashback_coin` from chain—no extra step.
- **When params come from decoded events**: If you build params from already-decoded trade events (for example from a parser service), you **must** pass the cashback flag into the SDK:
  - **PumpFun**: Set `is_cashback_coin` when building params from decoded events.
  - **PumpSwap**: Set `is_cashback_coin` field when constructing params manually.

<a id="mev-protection-services"></a>

## 🛡️ MEV Protection Services

You can apply for a key through the official website: [Community Website](https://fnzero.dev/swqos)

- **Jito**: High-performance block space
- **ZeroSlot**: Zero-latency transactions
- **Temporal**: Time-sensitive transactions
- **Bloxroute**: Blockchain network acceleration
- **FlashBlock**: High-speed transaction execution with API key authentication
- **BlockRazor**: High-speed transaction execution with API key authentication
- **Astralane**: Blockchain network acceleration

<a id="project-structure"></a>

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

<a id="important-notes"></a>

## ⚠️ Important Notes

1. Test thoroughly before using on mainnet
2. Properly configure private keys and API tokens
3. Pay attention to slippage settings to avoid transaction failures
4. Monitor balances and transaction fees
5. Comply with relevant laws and regulations

<a id="api-compatibility"></a>

## API compatibility

Full cross-language API parity is still in progress. See the [API migration guide](docs/USAGE.md#api-compatibility) for public behavior and support boundaries, and the examples directory for usage.


Live parser-to-trade integration uses Yellowstone **gRPC**. See [gRPC cache integration and language examples](docs/USAGE.md#grpc-cache). Quoting and construction read cached state without hot-path RPC.


See [cached_damm_v2](examples/cached_damm_v2.py) for single-hop DAMM v2 cached preparation and explicit simulation. Callers supply a minimum output; expected net receipts remain unknown. Native SOL and existing WSOL settle through different accounts. Reading PumpFun configuration alone does not provide complete fee quotes or a cached factory.

<a id="pumpswap-routes"></a>

## PumpSwap custom quote tokens and offline routes

See [reported 3007 failure and synchronized fixes](docs/PUMPSWAP_REPORTED_FAILURE.md)
for creator validation, explicit fee recipients and readonly volume accounts.

Direct PumpSwap builders support arbitrary pool quote mints, including ordinary
Token-2022 mints. `BuildBuyParams` / `BuildSellParams` accept optional
`input_mint`, `output_mint`, `input_token_program`, and `output_token_program`.
The actual mint direction selects `buy_exact_quote_in` or `sell`; mismatched
funding assets require an explicit conversion route. Amounts use raw mint units.
`PumpSwapParams.validate_accounts()` checks complete execution accounts and the
creator vault authority/ATA against the actual quote mint/program, without RPC.
Incomplete log events must first be enriched from verified subscription state.

`AccountCacheSnapshot.prepare_pumpswap_trade(...)` prepares an explicit complete
route. `prepare_best_pumpswap_trade(snapshot, search, request, context, is_buy)`
uses `PumpSwapRouteSearch` to order caller-supplied conversion pools and select
the highest protected final output. Buy and sell are quoted independently;
each next hop spends only the preceding protected minimum. Ties prefer fewer
hops, then pool pubkey bytes. Reversed duplicate hints collapse; conflicting
identities fail. Defaults are two conversion hops and 128 visited search nodes;
limits are 32 candidate hints, three conversion hops, and 4,096 nodes. Every
partial/dead-end path consumes budget; exhaustion fails the entire search.
Rejected stale/unsupported paths are returned with reasons. No market discovery
or RPC occurs on this path.

The prepared value binds the payer, endpoints, amount, slippage, and context.
`validate_freshness(current_context)` rejects future preparation slots, epoch
changes, and age beyond the smaller original/current allowance. This does not
refresh source accounts or prices: reprepare from coherent current subscription
data before trading. Cached PumpSwap preparation rejects active transfer fees,
unsupported extensions, and cashback pools with no verified cashback rate.

`prepared.build_transaction(signer, current_context, PumpSwapBuildOptions(...))`
builds and signs locally with explicit `v0` or `v1`, retaining caller blockhash
or a complete durable nonce pair, tip, compute settings and V0 ALTs.
`create_associated_accounts=False` assumes the route ATAs already exist; native
SOL still uses its separate temporary account. V0 enforces
1,232 signed bytes; V1 enforces 4,096 bytes and rejects ALTs. It never switches
versions or submits. Optional protocol/full transaction middleware must remain
offline if a fully offline build is required. Nonce authority/state and
blockhash validity remain caller responsibilities. Native SOL endpoints use
`So11111111111111111111111111111111111111111`; pool legs use WSOL. Supply a unique
`temporary_wsol_seed` and current `rent_lamports` from cold initialization for
native settlement. The temporary account is closed while existing WSOL balances
are preserved; plain WSOL endpoints spend/receive existing WSOL.

Run native examples and repeatable signed-wire tests from this checkout:

```bash
python -m examples.pumpswap_cached_prepare buy 10000
python -m examples.pumpswap_cached_prepare sell 1000000000
python -m examples.pumpswap_cached_prepare buy 1000000 tests/fixtures/pumpswap_ttwo_route_accounts.json v1
python -m examples.pumpswap_cached_prepare sell 1000000000 tests/fixtures/pumpswap_ttwo_route_accounts.json v1
python -m pytest -q tests/test_pumpswap_preparation.py
```

These examples use captured historical TTWO accounts, ephemeral signers and
synthetic blockhashes. Tests verify actual Ed25519 signatures, decode V0/V1
wire, and cover native settlement, nonce, tips, synthetic ALT compilation,
freshness and bounded route ranking. Synthetic ALTs cannot be used on chain.
This is offline preparation/signing validation, not a new bank/mainnet simulation
or a production latency measurement. A three-hop V0 route without ALTs can fail
the packet limit; choose V1 explicitly or provide actual on-chain ALTs.

### Offline deployed-program execution (Python)

```bash
python -m examples.pumpswap_bank_replay
python -m pytest -q tests/test_pumpswap_bank_replay.py
```

This native Python example uses `solders.litesvm` (install `solders>=0.26`)
to execute newly prepared, Ed25519-signed V0 buy/sell transactions with static
accounts and a local ALT. It repeats fresh-bank executions, checks exact pinned
token deltas, protected output, simulation/commit agreement, slippage failures,
rollback, transaction fees, and invalid-signature rejection. Replay performs no
RPC calls or broadcasts. Resources and SHA-256 manifests are under
`examples/pumpswap_bank/`; the snapshot contains the captured account lamports
and bytes, including Token2022 extensions.

Programs were captured October 8–9, 2026; pool/account snapshots October 18.
This is a mixed historical fixture, not an atomic mainnet fork. Wallet funding,
local ALT, and user/fee token accounts are synthetic; token account extensions
are preserved from their respective captured vaults. ATA creation is disabled
in this replay to isolate swap execution. The deployed-program bank test covers
the direct TTWO PumpSwap leg and the three-leg AMMv4 → DLMM → PumpSwap
buy/reverse sell route with V0+ALT. Impossible final-leg output also verifies
rollback of earlier successful program calls. `config.json` controls fresh-bank
repetitions and local CPU benchmark iterations (zero disables benchmarking);
preparation and build/sign percentiles exclude fixture I/O and SBF execution.
V1, nonce and middleware additionally have signing/decoding tests. These tests
do not establish production latency or the latest deployed-program behavior.

For repeatable CPU measurements, run `python -m examples.hot_path_benchmark`.
`examples/hot_path_benchmark.json` fixes the iteration count; the workload warms
up before measuring cached preparation and V0 build/sign separately. Fixture I/O,
RPC, and local-bank execution are outside timed loops. Pure PDA results and
validated fee configurations use bounded caches; account freshness/continuity
checks still run for every preparation. These local timings do not measure
production network latency.

<a id="documentation"></a>

## Documentation

- [Release and migration](RELEASE_NOTES.md)
- [Usage guide](docs/USAGE.md)
- [Examples](examples/README.md)
- [Cross-language support and boundaries](docs/cross-language-sync.md)


<a id="license"></a>

## 📄 License

MIT License

<a id="contact"></a>

## 💬 Contact

- Official Website: https://fnzero.dev/
- Project Repository: https://github.com/0xfnzero/sol-trade-sdk-python
- Telegram Group: https://t.me/fnzero_group
- Discord: https://discord.gg/vuazbGkqQE


Shared stock bridges: 33 official stock/ETF mints and 58 pools. See [eleven-SDK catalog and routing alignment](docs/STOCK_BRIDGE_SYNC.md) for configuration, USDC routing and cache-only boundaries.
