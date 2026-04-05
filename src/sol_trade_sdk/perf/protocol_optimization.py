"""
Solana protocol-level optimizations for trading.

Provides optimized transaction building, serialization, and
RPC communication for minimal latency.
"""

from __future__ import annotations

import base64
import hashlib
import struct
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union, Callable
import logging

logger = logging.getLogger(__name__)


@dataclass
class TransactionConfig:
    """Configuration for optimized transaction building."""
    compute_unit_limit: int = 1_400_000
    compute_unit_price: int = 0
    skip_preflight: bool = True
    max_retries: int = 0
    preflight_commitment: str = "processed"
    encoding: str = "base64"


@dataclass
class OptimizedInstruction:
    """Optimized instruction representation."""
    program_id: bytes  # 32 bytes
    accounts: List[Tuple[bytes, bool, bool]]  # (pubkey, is_signer, is_writable)
    data: bytes

    def serialize(self) -> bytes:
        """Serialize instruction to bytes."""
        # Program ID (32 bytes)
        result = self.program_id

        # Account count (1 byte)
        result += struct.pack("<B", len(self.accounts))

        # Accounts
        for pubkey, is_signer, is_writable in self.accounts:
            result += pubkey
            result += struct.pack("<BB", int(is_signer), int(is_writable))

        # Data length (2 bytes)
        result += struct.pack("<H", len(self.data))

        # Data
        result += self.data

        return result


@dataclass
class OptimizedTransaction:
    """Optimized transaction for minimal serialization overhead."""
    signatures: List[bytes]
    message: bytes
    instructions: List[OptimizedInstruction]
    recent_blockhash: bytes  # 32 bytes
    fee_payer: bytes  # 32 bytes

    def serialize(self) -> bytes:
        """Serialize transaction with minimal overhead."""
        # Signatures
        result = struct.pack("<B", len(self.signatures))
        for sig in self.signatures:
            result += struct.pack("<B", len(sig))
            result += sig

        # Message
        result += self.message

        return result

    def to_base64(self) -> str:
        """Convert to base64 for RPC."""
        return base64.b64encode(self.serialize()).decode('ascii')


class TransactionBuilder:
    """Optimized transaction builder with minimal allocations."""

    def __init__(self, config: Optional[TransactionConfig] = None):
        self.config = config or TransactionConfig()
        self._instructions: List[OptimizedInstruction] = []
        self._signers: Dict[bytes, bytes] = {}  # pubkey -> secret key

    def add_instruction(self, instruction: OptimizedInstruction) -> None:
        """Add instruction to transaction."""
        self._instructions.append(instruction)

    def add_signer(self, pubkey: bytes, secret_key: bytes) -> None:
        """Add signer keypair."""
        self._signers[pubkey] = secret_key

    def build(
        self,
        recent_blockhash: bytes,
        fee_payer: Optional[bytes] = None
    ) -> OptimizedTransaction:
        """Build optimized transaction."""
        if fee_payer is None:
            # Use first signer as fee payer
            fee_payer = next(iter(self._signers.keys()))

        # Build message
        message = self._build_message(recent_blockhash, fee_payer)

        # Sign message
        signatures = self._sign_message(message)

        return OptimizedTransaction(
            signatures=signatures,
            message=message,
            instructions=self._instructions,
            recent_blockhash=recent_blockhash,
            fee_payer=fee_payer
        )

    def _build_message(self, recent_blockhash: bytes, fee_payer: bytes) -> bytes:
        """Build transaction message."""
        # Version header
        message = b'\x00'  # Legacy transaction

        # Header
        num_required_signatures = len(self._signers)
        num_readonly_signed_accounts = 0
        num_readonly_unsigned_accounts = 0

        message += struct.pack(
            "<BBB",
            num_required_signatures,
            num_readonly_signed_accounts,
            num_readonly_unsigned_accounts
        )

        # Account keys
        account_keys = [fee_payer]
        for inst in self._instructions:
            if inst.program_id not in account_keys:
                account_keys.append(inst.program_id)
            for pubkey, _, _ in inst.accounts:
                if pubkey not in account_keys:
                    account_keys.append(pubkey)

        message += struct.pack("<H", len(account_keys))
        for key in account_keys:
            message += key

        # Recent blockhash
        message += recent_blockhash

        # Instructions
        message += struct.pack("<H", len(self._instructions))
        for inst in self._instructions:
            # Program ID index
            program_id_index = account_keys.index(inst.program_id)
            message += struct.pack("<B", program_id_index)

            # Account indices
            account_indices = []
            for pubkey, is_signer, is_writable in inst.accounts:
                idx = account_keys.index(pubkey)
                account_indices.append(idx)

            message += struct.pack("<B", len(account_indices))
            for idx in account_indices:
                message += struct.pack("<B", idx)

            # Data
            message += struct.pack("<H", len(inst.data))
            message += inst.data

        return message

    def _sign_message(self, message: bytes) -> List[bytes]:
        """Sign message with all signers."""
        signatures = []

        for pubkey, secret_key in self._signers.items():
            # In real implementation, use ed25519 signing
            # This is a placeholder
            signature = hashlib.sha256(message + secret_key).digest()[:64]
            signatures.append(signature)

        return signatures


class RPCOptimizer:
    """Optimize RPC calls for minimal latency."""

    def __init__(self):
        self._connection_pool: List[Any] = []
        self._batch_queue: List[Dict] = []
        self._batch_size = 10
        self._batch_timeout_ms = 10

    def create_optimized_request(
        self,
        method: str,
        params: List[Any],
        commitment: str = "processed"
    ) -> Dict:
        """Create optimized RPC request."""
        # Use processed commitment for speed
        if commitment in ("confirmed", "finalized"):
            commitment = "processed"

        return {
            "jsonrpc": "2.0",
            "id": int(time.time() * 1000) % 1000000,
            "method": method,
            "params": params
        }

    def batch_requests(self, requests: List[Dict]) -> bytes:
        """Batch multiple requests into single payload."""
        import json

        batch = []
        for i, req in enumerate(requests):
            req_copy = req.copy()
            req_copy["id"] = i
            batch.append(req_copy)

        return json.dumps(batch).encode()

    def parse_batch_response(self, data: bytes) -> List[Dict]:
        """Parse batched RPC response."""
        import json

        try:
            responses = json.loads(data.decode())
            if not isinstance(responses, list):
                responses = [responses]
            return responses
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse batch response: {e}")
            return []


class ComputeBudgetOptimizer:
    """Optimize compute budget instructions."""

    # Compute budget program ID
    PROGRAM_ID = bytes([
        0x06, 0xa1, 0xfc, 0xf1, 0x91, 0x9c, 0x05, 0xeb,
        0xba, 0x07, 0x9a, 0x22, 0xa6, 0x4e, 0x8e, 0x5f,
        0x6d, 0x97, 0x89, 0x0d, 0xec, 0x90, 0x91, 0x27,
        0xac, 0x8d, 0x47, 0x16, 0x42, 0xad, 0x04, 0x08
    ])

    # Instruction discriminators
    REQUEST_UNITS = 0
    REQUEST_HEAP_FRAME = 1
    SET_COMPUTE_UNIT_LIMIT = 2
    SET_COMPUTE_UNIT_PRICE = 3

    @classmethod
    def set_compute_unit_limit(cls, units: int) -> OptimizedInstruction:
        """Create compute unit limit instruction."""
        data = struct.pack("<BQ", cls.SET_COMPUTE_UNIT_LIMIT, units)

        return OptimizedInstruction(
            program_id=cls.PROGRAM_ID,
            accounts=[],
            data=data
        )

    @classmethod
    def set_compute_unit_price(cls, micro_lamports: int) -> OptimizedInstruction:
        """Create compute unit price (priority fee) instruction."""
        data = struct.pack("<BQ", cls.SET_COMPUTE_UNIT_PRICE, micro_lamports)

        return OptimizedInstruction(
            program_id=cls.PROGRAM_ID,
            accounts=[],
            data=data
        )

    @classmethod
    def request_heap_frame(cls, bytes_size: int) -> OptimizedInstruction:
        """Create heap frame request instruction."""
        data = struct.pack("<BI", cls.REQUEST_HEAP_FRAME, bytes_size)

        return OptimizedInstruction(
            program_id=cls.PROGRAM_ID,
            accounts=[],
            data=data
        )


class SerializationOptimizer:
    """Optimize binary serialization for Solana types."""

    @staticmethod
    def encode_u64(value: int) -> bytes:
        """Encode u64 efficiently."""
        return struct.pack("<Q", value)

    @staticmethod
    def encode_u128(value: int) -> bytes:
        """Encode u128 as little-endian bytes."""
        return value.to_bytes(16, 'little')

    @staticmethod
    def encode_compact_u16(value: int) -> bytes:
        """Encode compact u16 (variable length)."""
        if value < 0x80:
            return bytes([value])
        elif value < 0x4000:
            return bytes([value & 0x7F | 0x80, value >> 7])
        else:
            return bytes([
                value & 0x7F | 0x80,
                (value >> 7) & 0x7F | 0x80,
                value >> 14
            ])

    @staticmethod
    def decode_compact_u16(data: bytes, offset: int = 0) -> Tuple[int, int]:
        """Decode compact u16, returns (value, bytes_consumed)."""
        value = 0
        shift = 0
        bytes_consumed = 0

        while True:
            if offset + bytes_consumed >= len(data):
                raise ValueError("Incomplete compact u16")

            byte = data[offset + bytes_consumed]
            bytes_consumed += 1

            value |= (byte & 0x7F) << shift

            if (byte & 0x80) == 0:
                break

            shift += 7
            if shift > 14:
                raise ValueError("Compact u16 overflow")

        return value, bytes_consumed


class NetworkOptimizer:
    """Network-level optimizations for Solana communication."""

    def __init__(self):
        self._endpoint_weights: Dict[str, float] = {}
        self._endpoint_latencies: Dict[str, List[float]] = {}

    def record_latency(self, endpoint: str, latency_ms: float) -> None:
        """Record endpoint latency for load balancing."""
        if endpoint not in self._endpoint_latencies:
            self._endpoint_latencies[endpoint] = []

        latencies = self._endpoint_latencies[endpoint]
        latencies.append(latency_ms)

        # Keep last 100 measurements
        if len(latencies) > 100:
            latencies.pop(0)

        # Update weight based on average latency
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            # Higher weight = lower latency
            self._endpoint_weights[endpoint] = 1000.0 / (avg_latency + 1)

    def select_endpoint(self, endpoints: List[str]) -> str:
        """Select best endpoint based on recorded latencies."""
        if not endpoints:
            raise ValueError("No endpoints provided")

        if len(endpoints) == 1:
            return endpoints[0]

        # Weighted random selection
        import random

        weights = []
        for ep in endpoints:
            weight = self._endpoint_weights.get(ep, 1.0)
            weights.append(weight)

        total = sum(weights)
        if total == 0:
            return random.choice(endpoints)

        r = random.uniform(0, total)
        cumulative = 0
        for ep, weight in zip(endpoints, weights):
            cumulative += weight
            if r <= cumulative:
                return ep

        return endpoints[-1]


class HotPathOptimizer:
    """Optimize hot paths in trading operations."""

    def __init__(self):
        self._cached_accounts: Dict[str, Any] = {}
        self._cache_ttl_ms = 100

    def cache_account(self, address: str, data: Any) -> None:
        """Cache account data with TTL."""
        self._cached_accounts[address] = {
            'data': data,
            'timestamp': time.time() * 1000
        }

    def get_cached_account(self, address: str) -> Optional[Any]:
        """Get cached account if not expired."""
        entry = self._cached_accounts.get(address)
        if entry is None:
            return None

        age_ms = time.time() * 1000 - entry['timestamp']
        if age_ms > self._cache_ttl_ms:
            del self._cached_accounts[address]
            return None

        return entry['data']

    def optimize_instruction_order(
        self,
        instructions: List[OptimizedInstruction]
    ) -> List[OptimizedInstruction]:
        """
        Reorder instructions for optimal execution.

        Prioritizes:
        1. Compute budget instructions first
        2. Instructions with fewer account dependencies
        """
        def priority(inst: OptimizedInstruction) -> int:
            # Compute budget instructions first
            if inst.program_id == ComputeBudgetOptimizer.PROGRAM_ID:
                return 0
            # Then by number of accounts (fewer = higher priority)
            return len(inst.accounts)

        return sorted(instructions, key=priority)


# Global optimizer instances
_builder: Optional[TransactionBuilder] = None
_rpc_optimizer: Optional[RPCOptimizer] = None
_network_optimizer: Optional[NetworkOptimizer] = None


def get_transaction_builder(config: Optional[TransactionConfig] = None) -> TransactionBuilder:
    """Get or create global transaction builder."""
    global _builder
    if _builder is None:
        _builder = TransactionBuilder(config)
    return _builder


def get_rpc_optimizer() -> RPCOptimizer:
    """Get or create global RPC optimizer."""
    global _rpc_optimizer
    if _rpc_optimizer is None:
        _rpc_optimizer = RPCOptimizer()
    return _rpc_optimizer


def get_network_optimizer() -> NetworkOptimizer:
    """Get or create global network optimizer."""
    global _network_optimizer
    if _network_optimizer is None:
        _network_optimizer = NetworkOptimizer()
    return _network_optimizer
