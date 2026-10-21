<div align="center">
    <h1>Sol Trade SDK — Python</h1>
    <p>面向 Solana DEX 的 Python 交易 SDK</p>
    <a href="https://pypi.org/project/sol-trade-sdk/"><img src="https://img.shields.io/pypi/v/sol-trade-sdk.svg" alt="sol-trade-sdk"></a>
    <a href="#许可证"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT License"></a>
</div>

<p align="center">
    <a href="README.md">English</a> · <a href="README_CN.md">中文</a> ·
    <a href="examples/README.md">示例</a> ·
    <a href="docs/USAGE.md">文档</a> ·
    <a href="RELEASE_NOTES.md">发布与迁移</a> ·
    <a href="#sdk-版本与相关项目">相关 SDK</a>
</p>

提供交易构建、签名、多通道提交与缓存路由，支持 PumpFun、PumpSwap、Raydium 和 Meteora 等 DEX。各语言接口与支持边界见使用指南。

当前版本：**9.0.1**。升级前请阅读 [迁移说明](RELEASE_NOTES.md)；历史变更见 [版本记录](CHANGELOG_CN.md)。

## 目录

Pump.fun 全局默认 V3，可按单笔交易切换 V1/V2/V3；[版本配置、多跳示例和模拟限制](docs/PUMPFUN_VERSIONS.md)。

- [SDK 版本与相关项目](#sdk-版本与相关项目)
- [安装](#安装)
- [这个 SDK 适合什么场景](#这个-sdk-适合什么场景)
- [项目特性](#项目特性)
- [使用示例](#使用示例)
- [文档导航](#文档导航)
- [PumpSwap 缓存路由](#pumpswap-routes)

<a id="sdk-版本与相关项目"></a>

## 📦 SDK 版本与相关项目

各仓库版本独立，依赖兼容要求以对应 SDK 的安装说明为准。

| 语言 | 仓库 | 用途 | 版本 |
|----------|------------|-------------|---------|
| Rust | [sol-parser-sdk](https://github.com/0xfnzero/sol-parser-sdk) | DEX 交易与账户事件解析 | `v0.9.1` |
| Node.js | [sol-parser-sdk-nodejs](https://github.com/0xfnzero/sol-parser-sdk-nodejs) | DEX 交易与账户事件解析 | `v0.9.1` |
| Python | [sol-parser-sdk-python](https://github.com/0xfnzero/sol-parser-sdk-python) | DEX 交易与账户事件解析 | `v0.9.1` |
| Go | [sol-parser-sdk-golang](https://github.com/0xfnzero/sol-parser-sdk-golang) | DEX 交易与账户事件解析 | `v0.9.1` |
| Rust | [sol-trade-sdk](https://github.com/0xfnzero/sol-trade-sdk) | 交易构建、签名与多通道提交 | `v9.0.1` |
| Node.js | [sol-trade-sdk-nodejs](https://github.com/0xfnzero/sol-trade-sdk-nodejs) | 交易构建、签名与多通道提交 | `v9.0.1` |
| Python | [sol-trade-sdk-python](https://github.com/0xfnzero/sol-trade-sdk-python) | 交易构建、签名与多通道提交 | `v9.0.1` |
| Go | [sol-trade-sdk-golang](https://github.com/0xfnzero/sol-trade-sdk-golang) | 交易构建、签名与多通道提交 | `v9.0.1` |
| Rust | [sol-shred-sdk](https://github.com/0xfnzero/sol-shred-sdk) | 原始 Shred 解码与 ShredStream 指令事件 | `v6.0.1` |
| Rust | [solana-streamer](https://github.com/0xfnzero/solana-streamer) | gRPC / ShredStream 订阅与事件流封装 | `v5.0.0` |
| Rust | [sol-trade-router-sdk](https://github.com/0xfnzero/sol-trade-router-sdk) | 链上多跳 Router 与客户端 SDK | `v0.3.0` |

<a id="安装"></a>

## 安装

```sh
pip install sol-trade-sdk==9.0.1
```

运行仓库示例或参与开发时，再克隆源码：

```sh
git clone https://github.com/0xfnzero/sol-trade-sdk-python
cd sol-trade-sdk-python
pip install -e ".[dev]"
```

示例配置、离线回放与在线交易的区别见 [示例索引](examples/README.md)。

<a id="这个-sdk-适合什么场景"></a>

## 这个 SDK 适合什么场景

`sol-trade-sdk-python` 将 FnZero Solana 交易 SDK 带到 Python 生态，适合异步交易机器人、跟单管道、狙击机器人、研究自动化和后端服务，在保持 Rust SDK 行为对齐的同时提供低延迟 Solana DEX 交易构建能力。

| 方向 | 覆盖范围 |
|------|----------|
| DEX 协议 | PumpFun、PumpSwap、Bonk、Meteora DAMM v2、Raydium AMM v4、Raydium CPMM |
| 提交通道 | 默认 Solana RPC，以及 Jito、ZeroSlot、Temporal、Bloxroute、FlashBlock、BlockRazor、Node1、Astralane、Stellium、Lightspeed、Soyas、Speedlanding、Helius、Solami；NextBlock 默认仍按 Rust 黑名单跳过 |
| 交易流程 | `buy_simple` / `sell_simple`、旧版 buy/sell 参数、跟单交易、狙击交易、地址查找表、durable nonce、中间件、共享基础设施 |
| 运行环境 | Python 3.10+、异步服务、研究脚本和低延迟 Bot 基础设施 |

<a id="项目特性"></a>

## ✨ 项目特性

1. **PumpFun 交易**: 统一 `buy`、`sell`、`buy_exact_quote_in` 流程，自动按 SOL 或 USDC quote 池选择旧版或 V2 链上指令
2. **PumpSwap 交易**: 支持 PumpSwap 池的交易操作
3. **Bonk 交易**: 支持 Bonk 的交易操作
4. **Raydium CPMM 交易**: 支持 Raydium CPMM (Constant Product Market Maker) 的交易操作
5. **Raydium AMM V4 交易**: 支持 Raydium AMM V4 (Automated Market Maker) 的交易操作
6. **Meteora DAMM V2 交易**: 支持 Meteora DAMM V2 (Dynamic AMM) 的交易操作
7. **多种 MEV 保护**: 支持 Rust v5.0.2 SWQoS 集合，包括 Jito、ZeroSlot、Temporal、Bloxroute、FlashBlock、BlockRazor、Node1、Astralane、Stellium、Lightspeed、Soyas、Speedlanding、Helius、Solami、LunarLander、Glaive 和默认 RPC
8. **并发交易**: 所有已配置的 SWQoS 通道和默认 RPC 通道都会发出提交；首个成功只影响返回，较慢通道会继续提交
9. **统一交易接口**: 使用统一的交易协议类型进行交易操作，并支持 Rust 对齐的 `buy_simple` / `sell_simple` intent 参数
10. **中间件系统**: 支持自定义指令中间件，可在交易执行前对指令进行修改、添加或移除
11. **共享基础设施**: 多钱包可共享同一套 RPC 与 SWQoS 客户端，降低资源占用
12. **热路径 RPC 边界**: 交易执行使用调用方传入的 blockhash 或 durable nonce，不在热路径查询 blockhash、账户或余额

<a id="使用示例"></a>

## 🛠️ 使用示例

### 📋 交易流程

高层 intent API 可参考 [Simple Trading](examples/simple_trading.py)，示例展示 `SimpleBuyParams.new`、`BuyAmount.with_max_input`、`AccountPolicy.AUTO` 以及到旧版 `TradeBuyParams` 的转换。

#### 1. 创建 TradingClient 实例

您可以参考 [示例：创建 TradingClient 实例](examples/trading_client.py)。

**方法一：简单方式（单钱包）**
```python
import asyncio
from sol_trade_sdk import TradingClient, TradeConfig, SwqosConfig, SwqosRegion

async def main():
    # 钱包
    payer = Keypair.from_secret_key(/* 您的密钥 */)

    # RPC URL
    rpc_url = "https://mainnet.helius-rpc.com/?api-key=xxxxxx"

    # 可配置多个 SWQoS 服务
    swqos_configs = [
        SwqosConfig(type="Default", rpc_url=rpc_url),
        SwqosConfig(type="Jito", uuid="your_uuid", region=SwqosRegion.FRANKFURT),
        SwqosConfig(type="Bloxroute", api_token="your_api_token", region=SwqosRegion.FRANKFURT),
        SwqosConfig(type="Astralane", api_key="your_api_key", region=SwqosRegion.FRANKFURT),
    ]

    # 创建 TradeConfig 实例
    trade_config = TradeConfig(rpc_url, swqos_configs)

    # 创建 TradingClient
    client = TradingClient(payer, trade_config)

asyncio.run(main())
```

**方法二：共享基础设施（多钱包）**

对于多钱包场景，创建一次基础设施并在钱包间共享。
参见 [示例：共享基础设施](examples/shared_infrastructure.py)。

```python
from sol_trade_sdk import TradingInfrastructure, InfrastructureConfig

# 创建一次基础设施（开销大）
infra_config = InfrastructureConfig(rpc_url, swqos_configs)
infrastructure = TradingInfrastructure(infra_config)

# 创建多个客户端共享同一基础设施（快速）
client1 = TradingClient.from_infrastructure(payer1, infrastructure)
client2 = TradingClient.from_infrastructure(payer2, infrastructure)
```

#### 2. 配置 Gas 费策略

```python
from sol_trade_sdk import GasFeeStrategy

# 创建 GasFeeStrategy 实例
gas_fee_strategy = GasFeeStrategy()
# 设置全局策略
gas_fee_strategy.set_global_fee_strategy(150000, 150000, 500000, 500000, 0.001, 0.001)
```

#### 3. 构建交易参数

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

#### 4. 执行交易

```python
result = await client.buy(buy_params)
print(f"交易签名: {result.signature}")
```

### ⚡ 交易参数

关于所有交易参数（包括 `TradeBuyParams` 和 `TradeSellParams`）的详细信息，请参阅交易参数文档。

#### 关于 ShredStream

使用 shred 订阅事件时，由于 shred 的特性，您无法获取交易事件的完整信息。
在使用时，请确保您的交易逻辑所依赖的参数在 shred 中可用。

### 示例索引

完整示例、运行命令与配置要求见 [示例索引](examples/README.md)。

### ⚙️ SWQoS 服务配置说明

配置 SWQoS 服务时，请注意各服务的不同参数要求：

- **Jito**: 第一个参数是 UUID（如果没有 UUID，传空字符串 `""`）
- **其他 MEV 服务**: 第一个参数是 API Token

#### 自定义 URL 支持

每个 SWQoS 服务都支持可选的自定义 URL 参数：

```python
# 使用自定义 URL
jito_config = SwqosConfig(
    type="Jito",
    uuid="your_uuid",
    region=SwqosRegion.FRANKFURT,
    custom_url="https://custom-jito-endpoint.com"
)

# 使用默认区域端点
bloxroute_config = SwqosConfig(
    type="Bloxroute",
    api_token="your_api_token",
    region=SwqosRegion.NEW_YORK
)
```

**URL 优先级逻辑**:
- 如果提供了自定义 URL，将使用该 URL 而非区域端点
- 如果未提供自定义 URL，系统将使用指定区域的默认端点
- 这在保持向后兼容性的同时提供了最大的灵活性

使用多个 MEV 服务时，您需要使用 `Durable Nonce`。您需要使用 `fetch_nonce_info` 函数获取最新的 `nonce` 值，并在交易时将其作为 `durable_nonce` 使用。

---

### 🔧 中间件系统说明

SDK 提供了强大的中间件系统，允许您在交易执行前修改、添加或移除指令。中间件按添加顺序执行：

```python
from sol_trade_sdk import MiddlewareManager

manager = MiddlewareManager() \
    .add_middleware(FirstMiddleware()) \
    .add_middleware(SecondMiddleware()) \
    .add_middleware(ThirdMiddleware())
```

### 🔍 地址查找表

地址查找表（ALT）允许您通过以紧凑的表格格式存储常用地址来优化交易大小并降低费用。

```python
from sol_trade_sdk import fetch_address_lookup_table_account, AddressLookupTableCache

# 从链上获取 ALT
alt = await fetch_address_lookup_table_account(rpc, alt_address)
print(f"ALT 包含 {len(alt.addresses)} 个地址")

# 使用缓存提高性能
cache = AddressLookupTableCache(rpc)
await cache.prefetch([alt_address1, alt_address2, alt_address3])
cached = cache.get(alt_address1)
```

### 🔍 Nonce 缓存

使用持久 Nonce 实现交易重放保护并优化交易处理。

```python
from sol_trade_sdk import fetch_nonce_info, NonceCache

# 获取 nonce 信息
nonce_info = await fetch_nonce_info(rpc, nonce_account)
```

<a id="cashback-支持pumpfun-pumpswap"></a>

## 💰 Cashback 支持（PumpFun / PumpSwap）

PumpFun 和 PumpSwap 为符合条件的代币支持 **cashback**：部分交易费用可以返还给用户。SDK **必须知道**代币是否启用了 cashback，以便买/卖指令包含正确的账户。

- **当参数来自 RPC 时**: 如果您使用 `PumpFunParams.from_mint_by_rpc` 或 `PumpSwapParams.from_pool_address_by_rpc`，SDK 会从链上读取 `is_cashback_coin`——无需额外步骤。
- **当参数来自已解码事件时**: 如果您从已解码的交易事件构建参数（例如外部解析服务输出），您**必须**将 cashback 标志传递给 SDK：
  - **PumpFun**: 从解析的事件构建参数时设置 `is_cashback_coin`。
  - **PumpSwap**: 手动构建参数时设置 `is_cashback_coin` 字段。

<a id="mev-保护服务"></a>

## 🛡️ MEV 保护服务

您可以通过官网申请密钥：[社区网站](https://fnzero.dev/swqos)

- **Jito**: 高性能区块空间
- **ZeroSlot**: 零延迟交易
- **Temporal**: 时间敏感交易
- **Bloxroute**: 区块链网络加速
- **FlashBlock**: 高速交易执行（API 密钥认证）
- **BlockRazor**: 高速交易执行（API 密钥认证）
- **Node1**: 高速交易执行（API 密钥认证）
- **Astralane**: 区块链网络加速

<a id="项目结构"></a>

## 📁 项目结构

```
src/
├── common/           # 通用功能和工具
├── constants/        # 常量定义
├── instruction/      # 指令构建
│   └── utils/        # 指令工具
├── swqos/            # MEV 服务客户端
├── trading/          # 统一交易引擎
│   ├── common/       # 交易通用工具
│   ├── core/         # 核心交易引擎
│   ├── middleware/   # 中间件系统
│   └── factory.py    # 交易工厂
├── utils/            # 工具函数
│   ├── calc/         # 金额计算工具
│   └── price/        # 价格计算工具
└── __init__.py       # 主库文件
```

<a id="重要注意事项"></a>

## ⚠️ 重要注意事项

1. 在主网使用前请充分测试
2. 正确配置私钥和 API Token
3. 注意滑点设置以避免交易失败
4. 监控余额和交易费用
5. 遵守相关法律法规

<a id="pumpswap-routes"></a>

## PumpSwap 自定义报价币与缓存路由

直接交易按实际输入／输出 mint 选择方向，支持池内自定义报价币。SOL 与非 SOL 报价池之间的交易需要明确的兑换路径；缺失的 creator、vault、Token Program 等账户应先由已验证的池快照补齐。

缓存路径分别计算买入与卖出，后续跳只使用前一跳的受保护输出，并校验报价时效和费用上下文。准备与离线签名不调用 RPC；缺少有效池状态或必要费用信息时拒绝构建。详见 [缓存接入指南](docs/USAGE.md#grpc-cache) 和 [历史失败修复与验证](docs/PUMPSWAP_REPORTED_FAILURE.md)。

运行 [缓存准备示例](examples/pumpswap_cached_prepare.py) 可回放保存的池状态。离线程序执行与性能测试见 [示例索引](examples/README.md)，历史样本不代表实时价格或生产网络延迟。

<a id="api-兼容性"></a>

## API 兼容性

完整跨语言 API 对齐仍在进行；公开行为和支持边界见 [API 迁移说明](docs/USAGE.md#api-compatibility)，使用方法见 examples 目录。

<a id="文档导航"></a>

## 文档导航

- [发布与迁移](RELEASE_NOTES.md)
- [使用指南](docs/USAGE.md)
- [示例索引](examples/README.md)
- [跨语言功能与边界](docs/cross-language-sync.md)


<a id="许可证"></a>

## 📄 许可证

MIT License

<a id="联系方式"></a>

## 💬 联系方式

- 官方网站: https://fnzero.dev/
- 项目仓库: https://github.com/0xfnzero/sol-trade-sdk-python
- Telegram 群组: https://t.me/fnzero_group
- Discord: https://discord.gg/vuazbGkqQE


股票池同步：33 种官方股票/ETF、58 个股票池；配置扩展、USDC 起点、缓存选路与使用边界见 [11 SDK 同步说明](docs/STOCK_BRIDGE_SYNC.md)。
