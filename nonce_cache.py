"""
Durable Nonce cache for Solana transactions.

This module provides functionality to fetch and cache durable nonce information
for transaction replay protection.
"""

from typing import Optional, Dict
from dataclasses import dataclass
from solders.pubkey import Pubkey
from solders.hash import Hash
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment
import logging

logger = logging.getLogger(__name__)


@dataclass
class DurableNonceInfo:
    """Durable nonce information structure."""
    nonce_account: Optional[Pubkey] = None
    current_nonce: Optional[Hash] = None


async def fetch_nonce_info(
    rpc: AsyncClient,
    nonce_account: Pubkey,
    commitment: Optional[Commitment] = None,
) -> Optional[DurableNonceInfo]:
    """
    Fetch nonce information using RPC.

    Args:
        rpc: Solana RPC client
        nonce_account: The nonce account address
        commitment: Commitment level for the query

    Returns:
        DurableNonceInfo if successful, None otherwise
    """
    try:
        response = await rpc.get_account_info(
            nonce_account,
            commitment=commitment or Commitment("confirmed"),
        )

        if response.value is None:
            logger.error(f"Nonce account {nonce_account} not found")
            return None

        data = response.value.data

        # Parse nonce account data
        # Nonce account structure:
        # - Version (4 bytes)
        # - State (4 bytes) - 0 = Uninitialized, 1 = Initialized
        # - Authorized pubkey (32 bytes) - only if initialized
        # - Nonce hash (32 bytes) - only if initialized
        # - Fee calculator (8 bytes) - only if initialized

        if len(data) < 8:
            logger.error(f"Invalid nonce account data length: {len(data)}")
            return None

        # Check if initialized (state = 1)
        state = int.from_bytes(data[4:8], byteorder='little')
        if state != 1:
            logger.error(f"Nonce account not initialized, state: {state}")
            return None

        # Extract nonce hash (starts at offset 44: 8 + 32 + 4)
        if len(data) < 76:
            logger.error(f"Invalid nonce account data length for initialized state: {len(data)}")
            return None

        nonce_bytes = data[44:76]
        current_nonce = Hash.from_bytes(nonce_bytes)

        return DurableNonceInfo(
            nonce_account=nonce_account,
            current_nonce=current_nonce,
        )

    except Exception as e:
        logger.error(f"Failed to get nonce account information: {e}")
        return None


class NonceCache:
    """Cache for durable nonce information."""

    def __init__(self):
        self._cache: Dict[str, DurableNonceInfo] = {}

    async def get_nonce(
        self,
        rpc: AsyncClient,
        nonce_account: Pubkey,
        force_refresh: bool = False,
    ) -> Optional[DurableNonceInfo]:
        """
        Get nonce info from cache or fetch from RPC.

        Args:
            rpc: Solana RPC client
            nonce_account: The nonce account address
            force_refresh: Force refresh from RPC even if cached

        Returns:
            DurableNonceInfo if successful, None otherwise
        """
        key = str(nonce_account)

        if not force_refresh and key in self._cache:
            return self._cache[key]

        nonce_info = await fetch_nonce_info(rpc, nonce_account)

        if nonce_info:
            self._cache[key] = nonce_info

        return nonce_info

    def update_nonce(self, nonce_account: Pubkey, new_nonce: Hash) -> None:
        """Update the nonce value in cache."""
        key = str(nonce_account)
        if key in self._cache:
            self._cache[key].current_nonce = new_nonce

    def clear(self) -> None:
        """Clear the cache."""
        self._cache.clear()

    def remove(self, nonce_account: Pubkey) -> None:
        """Remove a specific nonce account from cache."""
        key = str(nonce_account)
        self._cache.pop(key, None)
