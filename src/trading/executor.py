"""
Trading Executor for Sol Trade SDK
Implements the core trading execution with parallel SWQOS submissions.
"""

import asyncio
import base64
import json
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Callable
from concurrent.futures import ThreadPoolExecutor
import time

from ..common.types import (
    GasFeeStrategy,
    GasFeeStrategyType,
    TradeType,
    SwqosType,
)
from solders.hash import Hash
from solders.instruction import Instruction
from solders.keypair import Keypair
from solders.message import Message
from solders.pubkey import Pubkey
from solders.transaction import Transaction

from ..swqos.clients import (
    SwqosClient,
    ClientFactory,
    SwqosConfig,
    TradeError,
)


# ===== Types =====

@dataclass
class TradeResult:
    """Result of a trade execution"""
    signature: str
    success: bool
    error: Optional[str] = None
    confirmation_time_ms: Optional[int] = None


@dataclass
class TradeConfig:
    """Configuration for trade execution"""
    swqos_configs: List[SwqosConfig] = field(default_factory=list)
    rpc_url: str = ""
    gas_fee_strategy: Optional[GasFeeStrategy] = None
    max_retries: int = 3
    retry_delay_ms: int = 100
    confirmation_timeout_ms: int = 30000
    parallel_submissions: bool = True


@dataclass
class TransactionContext:
    """Context for building and sending transactions"""
    payer: bytes
    recent_blockhash: str
    instructions: List[Instruction] = field(default_factory=list)
    signers: List[bytes] = field(default_factory=list)


# ===== Transaction Builder =====

class TransactionBuilder:
    """Builder for Solana transactions"""

    def __init__(self, payer: bytes, recent_blockhash: str):
        self.payer = payer
        self.recent_blockhash = recent_blockhash
        self.instructions: List[Instruction] = []
        self.signers: List[bytes] = []

    def add_instruction(self, instruction: Instruction) -> "TransactionBuilder":
        """Add an instruction to the transaction"""
        self.instructions.append(instruction)
        return self

    def add_signer(self, signer: bytes) -> "TransactionBuilder":
        """Add a signer to the transaction"""
        self.signers.append(signer)
        return self

    def build(self) -> bytes:
        """
        序列化为链上 wire 格式（legacy `Transaction`，与 `TradingClient` / `trading_utils` 一致）。

        - `payer`：32 字节 fee payer 公钥。
        - `recent_blockhash`：Base58 区块哈希字符串。
        - `signers`：每项为 64 字节 `Keypair.to_bytes()`；若为空则返回**未签名**交易（需自行签名后再发）。
        - 含签名时，`signers` 中必须至少包含与 `payer` 公钥匹配的 fee payer 密钥对。
        """
        if len(self.payer) != 32:
            raise ValueError("payer 必须为 32 字节公钥（Pubkey）")
        if not self.instructions:
            raise ValueError("至少需要一条 instruction")

        payer_pk = Pubkey.from_bytes(bytes(self.payer))
        bh = Hash.from_string(self.recent_blockhash.strip())

        if self.signers:
            keypairs: List[Keypair] = []
            for i, s in enumerate(self.signers):
                if len(s) != 64:
                    raise ValueError(
                        f"signer[{i}] 须为 64 字节（Keypair.to_bytes()），当前长度 {len(s)}"
                    )
                keypairs.append(Keypair.from_bytes(bytes(s)))
            if not any(k.pubkey() == payer_pk for k in keypairs):
                raise ValueError("signers 中须包含与 payer 公钥一致的 fee payer Keypair")
            tx = Transaction.new_signed_with_payer(
                self.instructions,
                payer_pk,
                keypairs,
                bh,
            )
        else:
            msg = Message.new_with_blockhash(self.instructions, payer_pk, bh)
            tx = Transaction.new_unsigned(msg)

        return bytes(tx)


# ===== Trade Executor =====

class TradeExecutor:
    """
    Core trading executor with parallel SWQOS submission support.
    
    This executor can submit transactions to multiple SWQOS providers
    in parallel to maximize the chance of transaction inclusion.
    """

    def __init__(self, config: TradeConfig):
        self.config = config
        self._clients: Dict[SwqosType, SwqosClient] = {}
        self._gas_strategy = config.gas_fee_strategy or GasFeeStrategy()
        self._executor = ThreadPoolExecutor(max_workers=10)

    def initialize(self) -> None:
        """Initialize SWQOS clients from configuration"""
        for swqos_config in self.config.swqos_configs:
            client = ClientFactory.create_client(
                swqos_config, self.config.rpc_url
            )
            self._clients[swqos_config.type] = client

    def get_client(self, swqos_type: SwqosType) -> Optional[SwqosClient]:
        """Get a SWQOS client by type"""
        return self._clients.get(swqos_type)

    async def execute_trade(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        wait_confirmation: bool = True,
        strategy_type: GasFeeStrategyType = GasFeeStrategyType.NORMAL,
    ) -> List[TradeResult]:
        """
        Execute a trade by submitting transactions to SWQOS providers.
        
        Args:
            trade_type: Type of trade (buy/sell)
            transactions: List of serialized transaction bytes
            wait_confirmation: Whether to wait for transaction confirmation
            strategy_type: Gas fee strategy to use
        
        Returns:
            List of trade results for each transaction
        """
        if not self._clients:
            self.initialize()

        results: List[TradeResult] = []

        # Get all clients sorted by priority
        clients = list(self._clients.values())

        if not clients:
            raise TradeError(code=500, message="No SWQOS clients configured")

        for tx in transactions:
            result = await self._submit_with_retries(
                clients, trade_type, tx, wait_confirmation, strategy_type
            )
            results.append(result)

        return results

    async def execute_parallel(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        wait_confirmation: bool = True,
        strategy_type: GasFeeStrategyType = GasFeeStrategyType.NORMAL,
    ) -> List[TradeResult]:
        """
        Execute trades in parallel across multiple SWQOS providers.
        
        Submits to all providers simultaneously and returns first successful result.
        """
        if not self._clients:
            self.initialize()

        clients = list(self._clients.values())

        if not clients:
            raise TradeError(code=500, message="No SWQOS clients configured")

        results: List[TradeResult] = []

        for tx in transactions:
            # Create tasks for all clients
            tasks = [
                self._submit_single(client, trade_type, tx, wait_confirmation)
                for client in clients
            ]

            # Run all tasks concurrently and get first successful result
            done, pending = await asyncio.wait(
                tasks,
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel pending tasks
            for task in pending:
                task.cancel()

            # Get result from completed task
            for task in done:
                try:
                    result = task.result()
                    if result.success:
                        results.append(result)
                        break
                except Exception as e:
                    continue

            if len(results) < len(transactions):
                results.append(TradeResult(
                    signature="",
                    success=False,
                    error="All parallel submissions failed",
                ))

        return results

    async def _submit_with_retries(
        self,
        clients: List[SwqosClient],
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool,
        strategy_type: GasFeeStrategyType,
    ) -> TradeResult:
        """Submit transaction with retries across multiple clients"""
        last_error = None

        for attempt in range(self.config.max_retries):
            for client in clients:
                try:
                    start_time = time.time()
                    signature = await client.send_transaction(
                        trade_type, transaction, wait_confirmation
                    )
                    elapsed = int((time.time() - start_time) * 1000)

                    return TradeResult(
                        signature=signature,
                        success=True,
                        confirmation_time_ms=elapsed,
                    )
                except TradeError as e:
                    last_error = str(e)
                    continue
                except Exception as e:
                    last_error = str(e)
                    continue

            # Wait before retry
            if attempt < self.config.max_retries - 1:
                await asyncio.sleep(self.config.retry_delay_ms / 1000)

        return TradeResult(
            signature="",
            success=False,
            error=last_error or "All submission attempts failed",
        )

    async def _submit_single(
        self,
        client: SwqosClient,
        trade_type: TradeType,
        transaction: bytes,
        wait_confirmation: bool,
    ) -> TradeResult:
        """Submit transaction to a single client"""
        try:
            start_time = time.time()
            signature = await client.send_transaction(
                trade_type, transaction, wait_confirmation
            )
            elapsed = int((time.time() - start_time) * 1000)

            return TradeResult(
                signature=signature,
                success=True,
                confirmation_time_ms=elapsed,
            )
        except Exception as e:
            return TradeResult(
                signature="",
                success=False,
                error=str(e),
            )

    def update_gas_strategy(self, gas_strategy: GasFeeStrategy) -> None:
        """Update the gas fee strategy"""
        self._gas_strategy = gas_strategy

    def get_gas_value(
        self,
        swqos_type: SwqosType,
        trade_type: TradeType,
        strategy_type: GasFeeStrategyType,
    ):
        """Get gas fee value for a specific configuration"""
        return self._gas_strategy.get(swqos_type, trade_type, strategy_type)

    def add_swqos_client(self, config: SwqosConfig) -> None:
        """Add a new SWQOS client"""
        client = ClientFactory.create_client(config, self.config.rpc_url)
        self._clients[config.type] = client

    def remove_swqos_client(self, swqos_type: SwqosType) -> None:
        """Remove a SWQOS client"""
        self._clients.pop(swqos_type, None)

    def close(self) -> None:
        """Close all clients and cleanup resources"""
        self._executor.shutdown(wait=False)


# ===== Convenience Functions =====

def create_trade_executor(
    rpc_url: str,
    swqos_types: List[SwqosType],
    api_keys: Optional[Dict[SwqosType, str]] = None,
) -> TradeExecutor:
    """
    Create a trade executor with specified SWQOS types.
    
    Args:
        rpc_url: Solana RPC URL
        swqos_types: List of SWQOS provider types to use
        api_keys: Optional API keys for each SWQOS type
    
    Returns:
        Configured TradeExecutor instance
    """
    api_keys = api_keys or {}
    
    configs = [
        SwqosConfig(
            type=swqos_type,
            api_key=api_keys.get(swqos_type),
        )
        for swqos_type in swqos_types
    ]

    config = TradeConfig(
        rpc_url=rpc_url,
        swqos_configs=configs,
    )

    return TradeExecutor(config)


# ===== Confirmation Polling =====

async def poll_for_confirmation(
    rpc_url: str,
    signature: str,
    timeout_ms: int = 30000,
    poll_interval_ms: int = 1000,
) -> bool:
    """
    Poll for transaction confirmation.
    
    Args:
        rpc_url: Solana RPC URL
        signature: Transaction signature to poll
        timeout_ms: Timeout in milliseconds
        poll_interval_ms: Polling interval in milliseconds
    
    Returns:
        True if transaction was confirmed, False otherwise
    """
    import aiohttp

    start_time = time.time()
    timeout_sec = timeout_ms / 1000
    poll_interval_sec = poll_interval_ms / 1000

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getSignatureStatuses",
        "params": [[signature]],
    }

    async with aiohttp.ClientSession() as session:
        while time.time() - start_time < timeout_sec:
            try:
                async with session.post(
                    rpc_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                ) as resp:
                    data = await resp.json()

                if "result" in data and data["result"]["value"]:
                    status = data["result"]["value"][0]
                    if status and status.get("confirmationStatus") == "finalized":
                        return True
                    if status and status.get("err"):
                        return False

            except Exception:
                pass

            await asyncio.sleep(poll_interval_sec)

    return False


__all__ = [
    "TradeResult",
    "TradeConfig",
    "TransactionContext",
    "TransactionBuilder",
    "TradeExecutor",
    "create_trade_executor",
    "poll_for_confirmation",
]
