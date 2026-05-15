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

    nonce_account: Pubkey
    authority: Pubkey
    nonce_hash: str
    recent_blockhash: str

    @property
    def current_nonce(self) -> Hash:
        """Backward-compatible view of the nonce hash."""
        return Hash.from_string(self.nonce_hash)

    @current_nonce.setter
    def current_nonce(self, value: Hash) -> None:
        nonce_hash = str(value)
        self.nonce_hash = nonce_hash
        self.recent_blockhash = nonce_hash


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

        if len(data) < 72:
            logger.error(f"Invalid nonce account data length: {len(data)}")
            return None

        authority = Pubkey.from_bytes(data[8:40])
        nonce_hash = str(Hash.from_bytes(data[40:72]))

        return DurableNonceInfo(
            nonce_account=nonce_account,
            authority=authority,
            nonce_hash=nonce_hash,
            recent_blockhash=nonce_hash,
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
