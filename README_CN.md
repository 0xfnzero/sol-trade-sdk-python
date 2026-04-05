# Sol Trade SDK for Python

<p align="center">
    <strong>高性能 Python SDK，用于低延迟 Solana DEX 交易</strong>
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
    <a href="README.md">English</a> |
    <a href="https://fnzero.dev/">官网</a> |
    <a href="https://t.me/fnzero_group">Telegram</a> |
    <a href="https://discord.gg/vuazbGkqQE">Discord</a>
</p>

---

## 📦 SDK 版本

本 SDK 提供多种语言版本：

| 语言 | 仓库 | 描述 |
|------|------|------|
| **Rust** | [sol-trade-sdk](https://github.com/0xfnzero/sol-trade-sdk) | 超低延迟，零拷贝优化 |
| **Node.js** | [sol-trade-sdk-nodejs](https://github.com/0xfnzero/sol-trade-sdk-nodejs) | TypeScript/JavaScript，Node.js 支持 |
| **Python** | [sol-trade-sdk-python](https://github.com/0xfnzero/sol-trade-sdk-python) | 原生 async/await 支持 |
| **Go** | [sol-trade-sdk-golang](https://github.com/0xfnzero/sol-trade-sdk-golang) | 并发安全，goroutine 支持 |

---

一个全面的高性能 Python SDK，用于 Solana DEX 交易，支持多种协议和 MEV 提供商。

## 特性

- **多 DEX 支持**: PumpFun、PumpSwap、Bonk、Raydium AMM V4、Raydium CPMM、Meteora DAMM V2
- **SWQoS 集成**: 多个 MEV 提供商用于交易提交
- **高性能**: LRU/TTL/分片缓存、连接池、并行执行
- **低延迟**: 针对亚秒级交易执行优化
- **安全优先**: 整数溢出保护、安全密钥存储、输入验证
- **零-RPC 热路径**: 所有 RPC 调用在交易执行前完成
- **模块化设计**: 按需使用

## 安装

```bash
pip install sol-trade-sdk
```

## 快速开始

### 基本交易

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
    # 创建 Gas 策略
    gas_strategy = create_gas_fee_strategy()

    # 创建交易执行器
    config = TradeConfig(
        rpc_url="https://api.mainnet-beta.solana.com",
        swqos_configs=[{"type": SwqosType.JITO}],
        gas_fee_strategy=gas_strategy,
    )

    executor = TradeExecutor(config)

    # 执行交易
    result = await executor.execute(
        trade_type=TradeType.BUY,
        transaction=serialized_tx,
    )
    print(f"交易签名: {result.signature}")

asyncio.run(main())
```

### PumpFun 交易

```python
from sol_trade_sdk.instruction.pumpfun import PumpFunInstructionBuilder
from sol_trade_sdk.calc.pumpfun import getBuyTokenAmountFromSolAmount

# 计算输入 SOL 可获得的代币数量
tokens = getBuyTokenAmountFromSolAmount(
    virtual_token_reserves=1_073_000_000_000_000,
    virtual_sol_reserves=30_000_000_000,
    real_token_reserves=793_000_000_000_000,
    has_creator=True,
    amount=1_000_000_000,  # 1 SOL
)

# 构建买入指令
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

### 热路径执行（零-RPC 交易）

```python
from sol_trade_sdk.hotpath.executor import HotPathExecutor
from sol_trade_sdk.hotpath.state import HotPathState

# 使用预取数据初始化热路径状态
state = HotPathState()
await state.prefetch_blockhash(rpc_client)
await state.cache_account(token_account_pubkey)

# 在交易期间无需任何 RPC 调用即可执行
executor = HotPathExecutor(state)
result = await executor.execute_trade(transaction)
```

## 安全特性

```python
from sol_trade_sdk.security import SecureKeyStorage, validate_rpc_url, validate_amount

# 带内存加密的安全密钥存储
storage = SecureKeyStorage.from_keypair(keypair, password="可选密码")
with storage.unlock() as kp:
    signature = kp.sign(message)

# 输入验证
validate_rpc_url("https://api.mainnet-beta.solana.com")
validate_amount(1_000_000_000, "amount", allow_zero=False)
```

## 地址查找表

```python
from sol_trade_sdk.address_lookup import fetch_address_lookup_table_account

# 从链上获取 ALT
alt = await fetch_address_lookup_table_account(rpc, alt_address)
print(f"ALT 包含 {len(alt.addresses)} 个地址")
```

## 架构

| 模块 | 描述 |
|------|------|
| `cache` | LRU、TTL 和分片缓存 |
| `calc` | 所有 DEX 的 AMM 计算 |
| `common` | 核心类型、Gas 策略、联合曲线 |
| `execution` | 分支优化、预取 |
| `hotpath` | 零-RPC 热路径执行 |
| `instruction` | 所有 DEX 的指令构建器 |
| `middleware` | 指令中间件系统 |
| `perf` | 性能优化（SIMD、内核绕过等） |
| `pool` | 连接池和工作池 |
| `rpc` | 高性能 RPC 客户端 |
| `security` | 安全密钥存储、验证器 |
| `seed` | 所有协议的 PDA 派生 |
| `swqos` | MEV 提供商客户端 |
| `trading` | 高性能交易执行器 |

## 性能优化

### SIMD 向量化
```python
from sol_trade_sdk.perf.simd import vectorized_hash
hashes = vectorized_hash(data_list)
```

### 内核绕过（Linux io_uring）
```python
from sol_trade_sdk.perf.kernel_bypass import AsyncIOUring
uring = AsyncIOUring(queue_depth=256)
```

### 零拷贝 I/O
```python
from sol_trade_sdk.perf.zero_copy_io import ZeroCopyBuffer
buffer = ZeroCopyBuffer.allocate(1024)
```

## 支持的协议

### PumpFun
- 带创建者费用支持的联合曲线计算
- 买卖指令构建
- 联合曲线和关联账户的 PDA 派生

### PumpSwap
- 带 LP/协议/创建者费用的池计算
- 买卖指令构建
- Mayhem 模式支持

### Bonk
- 虚拟/真实储备计算
- 协议费用处理

### Raydium
- 恒定乘积的 AMM V4 计算
- CPMM 计算
- 权限 PDA 派生

### Meteora
- DAMM V2 交换计算
- 池 PDA 派生

## 中间件系统

```python
from sol_trade_sdk.middleware import MiddlewareManager, LoggingMiddleware, ValidationMiddleware

manager = MiddlewareManager()
manager.add_middleware(ValidationMiddleware(max_instructions=100))
manager.add_middleware(LoggingMiddleware())

# 将中间件应用于指令
processed = manager.apply_middlewares_process_protocol_instructions(
    instructions, "PumpFun", is_buy=True
)
```

## 环境要求

- Python >= 3.9
- solders >= 0.18.0
- solana >= 0.30.0
- aiohttp >= 3.8.0

## 许可证

MIT License

## 联系方式

- 官方网站: https://fnzero.dev/
- 项目仓库: https://github.com/0xfnzero/sol-trade-sdk-python
- Telegram 群组: https://t.me/fnzero_group
- Discord: https://discord.gg/vuazbGkqQE
