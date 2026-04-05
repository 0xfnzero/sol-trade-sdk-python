"""
Serialization Module for Sol Trade SDK

Provides optimized transaction serialization based on Rust sol-trade-sdk:
- Zero-allocation buffer pooling
- Base58/Base64 encoding
- Pooled buffer guards
"""

from .serialization import (
    # Constants
    SERIALIZER_POOL_SIZE,
    SERIALIZER_BUFFER_SIZE,
    SERIALIZER_PREWARM_BUFFERS,
    
    # Base58
    encode_base58,
    decode_base58,
    
    # Transaction encoding
    TransactionEncoding,
    
    # Serializer
    ZeroAllocSerializer,
    Base64Encoder,
    PooledTxBufferGuard,
    
    # Functions
    serialize_transaction_sync,
    serialize_transaction_batch_sync,
    get_serializer_stats,
)

__all__ = [
    # Constants
    'SERIALIZER_POOL_SIZE',
    'SERIALIZER_BUFFER_SIZE',
    'SERIALIZER_PREWARM_BUFFERS',
    
    # Base58
    'encode_base58',
    'decode_base58',
    
    # Transaction encoding
    'TransactionEncoding',
    
    # Serializer
    'ZeroAllocSerializer',
    'Base64Encoder',
    'PooledTxBufferGuard',
    
    # Functions
    'serialize_transaction_sync',
    'serialize_transaction_batch_sync',
    'get_serializer_stats',
]
