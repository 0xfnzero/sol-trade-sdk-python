"""
Transaction serialization module.
Based on sol-trade-sdk Rust implementation with buffer pooling.
"""

import base64
import threading
from typing import List, Tuple, Optional
from enum import Enum
from collections import deque
import struct

# ===== Constants =====

SERIALIZER_POOL_SIZE = 10000
SERIALIZER_BUFFER_SIZE = 256 * 1024
SERIALIZER_PREWARM_BUFFERS = 64

# ===== Base58 Encoding =====

BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def encode_base58(data: bytes) -> str:
    """Encode bytes to base58 string"""
    # Count leading zeros
    leading_zeros = 0
    for b in data:
        if b == 0:
            leading_zeros += 1
        else:
            break

    # Convert to integer
    num = int.from_bytes(data, 'big')
    
    # Convert to base58
    result = []
    while num > 0:
        num, remainder = divmod(num, 58)
        result.append(BASE58_ALPHABET[remainder])
    
    # Add leading '1's for each leading zero byte
    result.extend(['1'] * leading_zeros)
    
    return ''.join(reversed(result))


def decode_base58(s: str) -> bytes:
    """Decode base58 string to bytes"""
    num = 0
    for char in s:
        num = num * 58 + BASE58_ALPHABET.index(char)
    
    # Count leading '1's
    leading_ones = 0
    for char in s:
        if char == '1':
            leading_ones += 1
        else:
            break
    
    # Convert to bytes
    result = []
    while num > 0:
        result.append(num & 0xFF)
        num >>= 8
    
    result.extend([0] * leading_ones)
    return bytes(reversed(result))


# ===== Transaction Encoding =====

class TransactionEncoding(Enum):
    BASE58 = "base58"
    BASE64 = "base64"


# ===== Zero-Allocation Serializer =====

class ZeroAllocSerializer:
    """
    Uses a buffer pool to avoid runtime allocation.
    Based on Rust's ZeroAllocSerializer pattern.
    """
    
    def __init__(self, pool_size: int = SERIALIZER_POOL_SIZE, 
                 buffer_size: int = SERIALIZER_BUFFER_SIZE,
                 prewarm_buffers: int = SERIALIZER_PREWARM_BUFFERS):
        self._buffer_size = buffer_size
        self._pool_size = pool_size
        self._lock = threading.Lock()
        self._pool: deque = deque(maxlen=pool_size)
        self._available = 0
        self._capacity = pool_size
        
        # Prewarm only a small hot set
        prewarm_count = min(prewarm_buffers, pool_size)
        for _ in range(prewarm_count):
            self._pool.append(bytearray(buffer_size))
            self._available += 1
    
    def serialize_zero_alloc(self, data: bytes) -> bytearray:
        """Serialize data using a pooled buffer"""
        with self._lock:
            if self._pool:
                buf = self._pool.popleft()
                self._available -= 1
            else:
                buf = bytearray(self._buffer_size)
        
        # Reset and copy data
        buf.clear()
        buf.extend(data)
        return buf
    
    def return_buffer(self, buf: bytearray) -> None:
        """Return a buffer to the pool"""
        with self._lock:
            buf.clear()
            if len(self._pool) < self._pool_size:
                self._pool.append(buf)
                self._available += 1

    # Alias for compatibility
    release_buffer = return_buffer

    def acquire_buffer(self) -> bytearray:
        """Acquire a buffer from the pool"""
        with self._lock:
            if self._pool:
                buf = self._pool.popleft()
                self._available -= 1
                return buf
            else:
                return bytearray(self._buffer_size)

    def serialize(self, data: dict) -> bytes:
        """Serialize dictionary to bytes (simplified)"""
        import json
        return json.dumps(data).encode('utf-8')

    def get_pool_stats(self) -> Tuple[int, int]:
        """Get pool statistics"""
        with self._lock:
            return self._available, self._capacity


# Global serializer instance
_global_serializer = ZeroAllocSerializer()


# ===== Base64 Encoder =====

class Base64Encoder:
    """Optimized base64 encoding"""
    
    @staticmethod
    def encode(data: bytes) -> str:
        """Encode data to base64"""
        return base64.b64encode(data).decode('ascii')
    
    @staticmethod
    def encode_fast(data: bytes) -> str:
        """Encode using pre-allocated buffer"""
        # Python's base64 is already optimized
        return base64.b64encode(data).decode('ascii')


# ===== PooledTxBufferGuard =====

class PooledTxBufferGuard:
    """
    Returns buffer to pool on release.
    Use as context manager for automatic cleanup.
    """
    
    def __init__(self, data: bytes, serializer: ZeroAllocSerializer = None):
        self._serializer = serializer or _global_serializer
        self._buffer = self._serializer.serialize_zero_alloc(data)
    
    @property
    def buffer(self) -> bytearray:
        return self._buffer
    
    def release(self) -> None:
        """Return buffer to pool"""
        if self._buffer is not None:
            self._serializer.return_buffer(self._buffer)
            self._buffer = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.release()


# ===== Transaction Serialization =====

def serialize_transaction_sync(transaction: bytes, 
                               encoding: TransactionEncoding) -> str:
    """
    Serialize a transaction using buffer pool.
    Returns encoded string.
    """
    serialized = _global_serializer.serialize_zero_alloc(transaction)
    try:
        if encoding == TransactionEncoding.BASE58:
            return encode_base58(bytes(serialized))
        elif encoding == TransactionEncoding.BASE64:
            return Base64Encoder.encode(bytes(serialized))
        else:
            raise ValueError(f"Unsupported encoding: {encoding}")
    finally:
        _global_serializer.return_buffer(serialized)


def serialize_transaction_batch_sync(
    transactions: List[bytes],
    encoding: TransactionEncoding
) -> List[str]:
    """Serialize multiple transactions"""
    return [serialize_transaction_sync(tx, encoding) for tx in transactions]


# ===== Get Statistics =====

def get_serializer_stats() -> Tuple[int, int]:
    """Get global serializer statistics"""
    return _global_serializer.get_pool_stats()
